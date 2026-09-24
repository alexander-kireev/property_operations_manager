from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from config.form_state import (
    deserialise_form_data,
    pop_form_state,
    serialise_form_data,
    store_form_state,
)

from .forms import PropertyForm
from .models import Property
from .selectors import (
    PROPERTY_SORT_OPTIONS,
    filtered_properties_for_user,
    properties_for_user,
    with_work_summary,
)
from .services import (
    create_property,
    deactivate_property,
    delete_property,
    reactivate_property,
    update_property,
)
from .navigation import created_record_property_url


PROPERTIES_PER_PAGE = 20


def _property_record_forms(request, property_record, *, data=None, kind=None):
    """The three add forms share the property page, not the My work workspace."""
    from event.forms import EventContactForm, EventForm
    from issue.forms import IssueForm
    from task.forms import TaskForm

    def form_data(form_kind):
        return data if kind == form_kind else None

    return {
        "property_add_task_form": TaskForm(
            form_data("task"), user=request.user, auto_id="property_add_task_%s",
            initial={"property": property_record.pk},
        ),
        "property_add_issue_form": IssueForm(
            form_data("issue"), user=request.user, auto_id="property_add_issue_%s",
            initial={"property": property_record.pk},
        ),
        "property_add_event_form": EventForm(
            form_data("event"), user=request.user, auto_id="property_add_event_%s",
            initial={"property": property_record.pk},
        ),
        "property_event_contacts_form": EventContactForm(
            form_data("event"), user=request.user, auto_id="property_event_contacts_%s",
        ),
    }
RELATED_RECORDS_PER_PAGE = 25


def _normalised_list_values(request):
    search = request.GET.get("search", "").strip()
    state = request.GET.get("state", "")
    sort = request.GET.get("sort", "name")

    if state not in (*Property.State.values, "all"):
        state = ""

    if sort not in PROPERTY_SORT_OPTIONS:
        sort = "name"

    return {"search": search, "state": state, "sort": sort}


def _list_query_parameters(values):
    parameters = {}
    for name in ("search", "state"):
        if values[name]:
            parameters[name] = values[name]
    if values["sort"] != "name":
        parameters["sort"] = values["sort"]
    return parameters


def _property_list_url(request, *, form_state=None):
    parameters = _list_query_parameters(_normalised_list_values(request))
    page = request.GET.get("page", "")
    if page.isdigit() and int(page) > 1:
        parameters["page"] = page
    if form_state is not None:
        parameters["form_state"] = form_state

    url = reverse("property:properties")
    return f"{url}?{urlencode(parameters)}" if parameters else url


def _property_detail_url(property_record, *, form_state=None):
    url = reverse(
        "property:property_detail",
        kwargs={"property_id": property_record.pk},
    )
    return f"{url}?{urlencode({'form_state': form_state})}" if form_state else url


def _redirect_with_property_form_state(
    request,
    *,
    action,
    property_record=None,
):
    token = store_form_state(request, {
        "action": action,
        "property_id": property_record.pk if property_record else None,
        "data": serialise_form_data(request.POST),
    })
    if property_record is not None and request.GET.get("return_to") != "list":
        return redirect(_property_detail_url(property_record, form_state=token))
    return redirect(_property_list_url(request, form_state=token))


def _restore_add_property_form(request, state):
    return PropertyForm(
        deserialise_form_data(state.get("data", {})),
        user=request.user,
        auto_id="add_property_%s",
    )


def _restore_edit_property_form(request, state, property_record):
    if (
        state.get("property_id") != property_record.pk
        or property_record.state != Property.State.ACTIVE
    ):
        return None
    return PropertyForm(
        deserialise_form_data(state.get("data", {})),
        user=request.user,
        instance=property_record,
        auto_id="edit_property_%s",
    )


def _property_list_context(request, *, add_property_form=None, edit_property_form=None, edit_property_record=None):
    values = _normalised_list_values(request)
    properties = filtered_properties_for_user(
        user=request.user,
        **{**values, "state": values["state"] or Property.State.ACTIVE},
    )

    paginator = Paginator(with_work_summary(properties), PROPERTIES_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_parameters = _list_query_parameters(values)
    return_parameters = query_parameters.copy()
    return_parameters["return_to"] = "list"
    if page_obj.number > 1:
        return_parameters["page"] = page_obj.number
    navigation_parameters = query_parameters.copy()
    if page_obj.number > 1:
        navigation_parameters["page"] = page_obj.number

    selected_property = edit_property_record or next(iter(page_obj.object_list), None)
    return {
        "add_property_form": (
            add_property_form
            if add_property_form is not None
            else PropertyForm(user=request.user, auto_id="add_property_%s")
        ),
        "page_obj": page_obj,
        "list_edit_form": edit_property_form or PropertyForm(user=request.user, auto_id="list_edit_%s"),
        "list_return_query": urlencode(return_parameters),
        "navigation_query": urlencode(navigation_parameters),
        "search": values["search"],
        "state": values["state"],
        "sort": values["sort"],
        "list_query": urlencode(query_parameters),
        "has_filters": bool(values["search"] or values["state"]),
        "property_count": properties_for_user(user=request.user).count(),
        "selected_property": selected_property,
        "selected_in_page": True,
        "is_detail_route": False,
    }


def _property_history(request, property_record):
    from event.models import Event
    from issue.models import Issue
    from task.models import Task

    history = []
    finished_issues = Issue.objects.filter(
        user=request.user,
        property=property_record,
        state__in=(Issue.State.RESOLVED, Issue.State.DISMISSED),
        deleted_at__isnull=True,
        terminated_at__isnull=False,
    )
    for issue in finished_issues:
        history.append({"kind": "issue", "label": issue.get_state_display(), "item": issue, "date": issue.terminated_at})

    finished_tasks = Task.objects.filter(
        user=request.user,
        state__in=(Task.State.COMPLETED, Task.State.DISMISSED),
        deleted_at__isnull=True,
        terminated_at__isnull=False,
    ).filter(
        Q(property=property_record)
        | Q(issue__property=property_record, issue__deleted_at__isnull=True)
    ).distinct()
    for task in finished_tasks:
        history.append({"kind": "task", "label": task.get_state_display(), "item": task, "date": task.terminated_at})

    finished_events = Event.objects.filter(
        user=request.user,
        property=property_record,
        state__in=(Event.State.OCCURRED, Event.State.CANCELLED),
        deleted_at__isnull=True,
        terminated_at__isnull=False,
    )
    for event in finished_events:
        history.append({"kind": "event", "label": event.get_state_display(), "item": event, "date": event.terminated_at})

    history.sort(key=lambda entry: entry["date"], reverse=True)
    return history


def _property_detail_context(request, property_record, *, edit_property_form=None, list_context=None):
    from event.models import Event
    from issue.models import Issue
    from task.models import Task

    issues = Issue.objects.filter(
        user=request.user,
        property=property_record,
        deleted_at__isnull=True,
    )
    tasks = Task.objects.filter(
        user=request.user,
        deleted_at__isnull=True,
    ).filter(
        Q(property=property_record)
        | Q(issue__property=property_record, issue__deleted_at__isnull=True)
    ).select_related("issue").distinct()
    events = Event.objects.filter(
        user=request.user,
        property=property_record,
        deleted_at__isnull=True,
    )

    record_type = request.GET.get("records_type", "all")
    if record_type not in ("all", "issue", "task", "event"):
        record_type = "all"
    record_scope = request.GET.get("records_scope", "current")
    if record_scope not in ("current", "past", "all"):
        record_scope = "current"
    record_sort = request.GET.get("records_sort", "date")
    if record_sort not in ("date", "recent", "title"):
        record_sort = "date"
    record_search = request.GET.get("records_search", "").strip()

    records = []
    for kind, queryset, active_state in (
        ("issue", issues, Issue.State.ACTIVE),
        ("task", tasks, Task.State.ACTIVE),
        ("event", events, Event.State.SCHEDULED),
    ):
        if record_type not in ("all", kind):
            continue
        if record_scope == "current":
            queryset = queryset.filter(state=active_state)
        elif record_scope == "past":
            queryset = queryset.exclude(state=active_state)
        if record_search:
            queryset = queryset.filter(Q(title__icontains=record_search) | Q(description__icontains=record_search))
        for item in queryset:
            current = item.state == active_state
            date = (item.resolution_deadline if kind == "issue" else
                    item.completion_deadline if kind == "task" else item.scheduled_date)
            records.append({"kind": kind, "item": item, "current": current, "date": date})

    if record_sort == "title":
        records.sort(key=lambda entry: (entry["item"].title.casefold(), entry["kind"], entry["item"].pk))
    elif record_sort == "recent" or record_scope == "past":
        records.sort(key=lambda entry: (entry["item"].terminated_at or entry["item"].created_at, entry["item"].pk), reverse=True)
    else:
        records.sort(key=lambda entry: (entry["date"] is None, entry["date"] or timezone.localdate(), entry["kind"], entry["item"].pk))

    record_parameters = {
        "records_type": record_type,
        "records_scope": record_scope,
        "records_sort": record_sort,
    }
    if record_search:
        record_parameters["records_search"] = record_search
    record_page = Paginator(records, RELATED_RECORDS_PER_PAGE).get_page(request.GET.get("records_page"))

    context = list_context or _property_list_context(request)
    context.update({
        "property": property_record,
        "selected_property": property_record,
        "selected_in_page": any(item.pk == property_record.pk for item in context["page_obj"].object_list),
        "is_detail_route": list_context is None,
        "related_page": record_page,
        "related_type": record_type,
        "related_scope": record_scope,
        "related_sort": record_sort,
        "related_search": record_search,
        "related_query": urlencode(record_parameters),
        "edit_property_form": (
            edit_property_form
            if edit_property_form is not None
            else PropertyForm(user=request.user, instance=property_record, auto_id="edit_property_%s")
        ),
    })
    if property_record.state == Property.State.ACTIVE:
        context.update(_property_record_forms(request, property_record))
    return context


@login_required
@require_GET
def properties_view(request):
    add_property_form = None
    edit_property_form = None
    edit_property_record = None
    state = pop_form_state(request)
    if isinstance(state, dict) and state.get("action") == "add_property":
        add_property_form = _restore_add_property_form(request, state)
    elif isinstance(state, dict) and state.get("action") == "edit_property":
        edit_property_record = properties_for_user(user=request.user).filter(pk=state.get("property_id"), state=Property.State.ACTIVE).first()
        if edit_property_record:
            edit_property_form = _restore_edit_property_form(request, state, edit_property_record)

    context = _property_list_context(request, add_property_form=add_property_form, edit_property_form=edit_property_form, edit_property_record=edit_property_record)
    if context["selected_property"] is not None:
        context = _property_detail_context(request, context["selected_property"], list_context=context)
        if edit_property_form is None:
            context["list_edit_form"] = PropertyForm(
                user=request.user,
                instance=context["selected_property"],
                auto_id="list_edit_%s",
            )
    return render(
        request,
        "property/properties.html",
        context,
    )


@login_required
@require_POST
def add_property_view(request):
    form = PropertyForm(request.POST, user=request.user)

    if form.is_valid():
        property_record = create_property(
            user=request.user,
            **form.cleaned_data,
        )

        if request.GET.get("return_to") == "list":
            return redirect(_property_list_url(request))
        return redirect("property:property_detail", property_id=property_record.pk)

    return _redirect_with_property_form_state(
        request,
        action="add_property",
    )


@login_required
@require_GET
def property_detail_view(request, property_id):
    property_record = get_object_or_404(
        properties_for_user(user=request.user),
        pk=property_id,
    )

    edit_property_form = None
    state = pop_form_state(request)
    if isinstance(state, dict) and state.get("action") == "edit_property":
        edit_property_form = _restore_edit_property_form(
            request,
            state,
            property_record,
        )

    context = _property_detail_context(
        request,
        property_record,
        edit_property_form=edit_property_form,
    )
    if (
        isinstance(state, dict)
        and state.get("action") == "property_add_record"
        and state.get("property_id") == property_record.pk
        and state.get("kind") in ("task", "issue", "event")
        and property_record.state == Property.State.ACTIVE
    ):
        kind = state["kind"]
        context.update(_property_record_forms(
            request, property_record,
            data=deserialise_form_data(state.get("data", {})), kind=kind,
        ))
        context["property_record_modal"] = {
            "task": "propertyAddTaskModal",
            "issue": "propertyAddIssueModal",
            "event": "propertyAddEventModal",
        }[kind]

    return render(
        request,
        "property/property_detail.html",
        context,
    )


@login_required
@require_POST
def add_property_record_view(request, property_id, kind):
    """Create a work item in property context and return to the same property."""
    if kind not in ("task", "issue", "event"):
        raise Http404
    property_record = get_object_or_404(
        properties_for_user(user=request.user),
        pk=property_id, state=Property.State.ACTIVE,
    )

    # The URL, not a hidden field, decides which property owns the new record.
    data = request.POST.copy()
    data["property"] = str(property_record.pk)
    if kind == "task":
        data["relationship_type"] = "property"
        data["issue"] = ""
    forms = _property_record_forms(request, property_record, data=data, kind=kind)
    form = forms[f"property_add_{kind}_form"]
    valid = form.is_valid()
    contacts_form = forms["property_event_contacts_form"]
    if kind == "event":
        valid = contacts_form.is_valid() and valid

    if valid:
        if kind == "task":
            from task.services import create_task
            record = create_task(user=request.user, **form.cleaned_data)
        elif kind == "issue":
            from issue.services import create_issue
            record = create_issue(user=request.user, **form.cleaned_data)
        else:
            from event.services import create_event
            record = create_event(
                user=request.user,
                contacts=contacts_form.cleaned_data["contacts"],
                **form.cleaned_data,
            )
        return redirect(created_record_property_url(record, property_record.pk, kind))

    token = store_form_state(request, {
        "action": "property_add_record",
        "property_id": property_record.pk,
        "kind": kind,
        "data": serialise_form_data(data),
    })
    detail_url = reverse("property:property_detail", args=[property_record.pk])
    return redirect(f"{detail_url}?{urlencode({'form_state': token})}")


@login_required
@require_POST
def edit_property_view(request, property_id):
    property_record = get_object_or_404(
        properties_for_user(user=request.user),
        pk=property_id,
        state=Property.State.ACTIVE,
    )
    form = PropertyForm(
        request.POST,
        user=request.user,
        instance=property_record,
    )

    if form.is_valid():
        update_property(
            property_record=property_record,
            **form.cleaned_data,
        )
        if request.GET.get("return_to") == "list":
            return redirect(_property_list_url(request))
        return redirect("property:property_detail", property_id=property_record.pk)

    return _redirect_with_property_form_state(
        request,
        action="edit_property",
        property_record=property_record,
    )


@login_required
@require_POST
def deactivate_property_view(request, property_id):
    property_record = get_object_or_404(
        properties_for_user(user=request.user),
        pk=property_id,
        state=Property.State.ACTIVE,
    )
    deactivate_property(property_record=property_record)
    if request.GET.get("return_to") == "list":
        return redirect(_property_list_url(request))
    return redirect("property:property_detail", property_id=property_record.pk)


@login_required
@require_POST
def reactivate_property_view(request, property_id):
    property_record = get_object_or_404(
        properties_for_user(user=request.user),
        pk=property_id,
        state=Property.State.DEACTIVATED,
    )
    reactivate_property(property_record=property_record)
    if request.GET.get("return_to") == "list":
        return redirect(_property_list_url(request))
    return redirect("property:property_detail", property_id=property_record.pk)


@login_required
@require_POST
def delete_property_view(request, property_id):
    property_record = get_object_or_404(
        properties_for_user(user=request.user),
        pk=property_id,
    )
    delete_property(property_record=property_record)

    if request.GET.get("return_to") == "list":
        return redirect(_property_list_url(request))
    return redirect("property:properties")
