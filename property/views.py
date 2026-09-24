from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
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


PROPERTIES_PER_PAGE = 20
PROPERTY_SECTIONS = (
    {"name": "overview", "label": "Overview"},
    {"name": "work", "label": "Work"},
    {"name": "schedule", "label": "Schedule"},
    {"name": "history", "label": "History"},
)


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
        "property_sections": PROPERTY_SECTIONS,
        "active_section": request.GET.get("tab") if request.GET.get("tab") in ("overview", "work", "schedule", "history") else "overview",
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

    open_issues = Issue.objects.filter(
        user=request.user,
        property=property_record,
        state=Issue.State.ACTIVE,
        deleted_at__isnull=True,
    ).order_by("resolution_deadline", "pk")
    open_tasks = Task.objects.filter(
        user=request.user,
        state=Task.State.ACTIVE,
        deleted_at__isnull=True,
    ).filter(
        Q(property=property_record)
        | Q(issue__property=property_record, issue__deleted_at__isnull=True)
    ).select_related("issue").order_by("completion_deadline", "pk").distinct()
    next_events = Event.objects.filter(
        user=request.user,
        property=property_record,
        state=Event.State.SCHEDULED,
        deleted_at__isnull=True,
        scheduled_date__gte=timezone.localdate(),
    ).order_by("scheduled_date", "start_time", "pk")

    context = list_context or _property_list_context(request)
    context.update({
        "property": property_record,
        "selected_property": property_record,
        "selected_in_page": any(item.pk == property_record.pk for item in context["page_obj"].object_list),
        "is_detail_route": list_context is None,
        "open_issues": open_issues,
        "open_tasks": open_tasks,
        "next_events": next_events,
        "history": _property_history(request, property_record),
        "edit_property_form": (
            edit_property_form
            if edit_property_form is not None
            else PropertyForm(user=request.user, instance=property_record, auto_id="edit_property_%s")
        ),
    })
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

    return render(
        request,
        "property/property_detail.html",
        _property_detail_context(
            request,
            property_record,
            edit_property_form=edit_property_form,
        ),
    )


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
