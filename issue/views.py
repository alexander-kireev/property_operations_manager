from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
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

from property.selectors import properties_for_user
from property.navigation import active_property_for_user, created_record_property_url
from event.selectors import events_for_user
from task.forms import TaskForm
from task.models import Task
from task.selectors import tasks_for_issue, tasks_for_user
from task.services import create_task, update_task

from .forms import IssueForm
from .models import Issue
from .selectors import (
    ISSUE_DEADLINE_PERIOD_OPTIONS,
    ISSUE_SORT_OPTIONS,
    filtered_issues_for_user,
    issues_for_user,
)
from .services import (
    create_issue,
    delete_issue,
    dismiss_issue,
    reactivate_issue,
    resolve_issue,
    update_issue,
)


ISSUES_PER_PAGE = 20


def _normalised_list_values(request):
    search = request.GET.get("search", "").strip()
    state = request.GET.get("state", "")
    sort = request.GET.get("sort", "resolution_deadline")
    priority_value = request.GET.get("priority", "")
    property_value = request.GET.get("property", "")
    deadline_period = request.GET.get("deadline_period", "")

    if state not in (*Issue.State.values, "all"):
        state = ""
    if sort not in ISSUE_SORT_OPTIONS:
        sort = "resolution_deadline"
    if deadline_period not in ISSUE_DEADLINE_PERIOD_OPTIONS:
        deadline_period = ""

    try:
        priority = int(priority_value)
    except (TypeError, ValueError):
        priority = ""
    if priority not in Issue.Priority.values:
        priority = ""

    try:
        property_id = int(property_value)
    except (TypeError, ValueError):
        property_id = ""

    return {
        "search": search,
        "state": state,
        "priority": priority,
        "property_id": property_id,
        "deadline_period": deadline_period,
        "sort": sort,
    }


def _list_query_parameters(values):
    parameters = {}
    for name in ("search", "state", "priority", "deadline_period"):
        if values[name]:
            parameters[name] = values[name]
    if values["property_id"]:
        parameters["property"] = values["property_id"]
    if values["sort"] != "resolution_deadline":
        parameters["sort"] = values["sort"]
    return parameters


def _issue_workspace_url(
    request,
    *,
    issue_id=None,
    tab="details",
    form_state=None,
):
    parameters = _list_query_parameters(_normalised_list_values(request))
    page = request.GET.get("page", "")
    if page.isdigit() and int(page) > 1:
        parameters["page"] = page
    if issue_id is not None:
        parameters["selected"] = issue_id
    if tab == "tasks":
        parameters["tab"] = "tasks"
    if form_state is not None:
        parameters["form_state"] = form_state

    url = reverse("issue:issues")
    return f"{url}?{urlencode(parameters)}" if parameters else url


def _active_issue_from_form_state(request, state):
    return issues_for_user(user=request.user).filter(
        pk=state.get("issue_id"),
        state=Issue.State.ACTIVE,
    ).first()


def _restore_add_issue_form(request, state):
    return {
        "add_issue_form": IssueForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            auto_id="add_issue_%s",
        ),
        "open_modal": "addIssueModal",
    }


def _restore_edit_issue_form(request, state):
    issue = _active_issue_from_form_state(request, state)
    if issue is None:
        return {}
    return {
        "selected_issue": issue,
        "edit_issue_form": IssueForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            instance=issue,
            auto_id="edit_issue_%s",
        ),
        "active_tab": "details",
        "open_modal": "editIssueModal",
    }


def _restore_add_issue_task_form(request, state):
    issue = _active_issue_from_form_state(request, state)
    if issue is None:
        return {}
    return {
        "selected_issue": issue,
        "add_task_form": TaskForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            parent_issue=issue,
            auto_id="add_issue_task_%s",
        ),
        "active_tab": "tasks",
        "open_modal": "addIssueTaskModal",
    }


def _restore_edit_issue_task_form(request, state):
    issue = _active_issue_from_form_state(request, state)
    if issue is None:
        return {}
    task = tasks_for_issue(user=request.user, issue=issue).filter(
        pk=state.get("object_id"),
        state=Task.State.ACTIVE,
    ).first()
    if task is None:
        return {}
    return {
        "selected_issue": issue,
        "edit_task_form": TaskForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            instance=task,
            auto_id="edit_issue_task_%s",
        ),
        "edit_task": task,
        "active_tab": "tasks",
        "open_modal": "editIssueTaskModal",
    }


ISSUE_FORM_STATE_RESTORERS = {
    "add_issue": _restore_add_issue_form,
    "edit_issue": _restore_edit_issue_form,
    "add_issue_task": _restore_add_issue_task_form,
    "edit_issue_task": _restore_edit_issue_task_form,
}


def _restore_issue_form_context(request):
    state = pop_form_state(request)
    if not isinstance(state, dict):
        return {}
    restorer = ISSUE_FORM_STATE_RESTORERS.get(state.get("action"))
    return restorer(request, state) if restorer is not None else {}


def _redirect_with_issue_form_state(
    request,
    *,
    action,
    issue_id=None,
    object_id=None,
    tab="details",
):
    token = store_form_state(request, {
        "action": action,
        "issue_id": issue_id,
        "object_id": object_id,
        "data": serialise_form_data(request.POST),
    })
    return redirect(
        _issue_workspace_url(
            request,
            issue_id=issue_id,
            tab=tab,
            form_state=token,
        )
    )


def _issue_list_context(
    request,
    *,
    selected_issue=None,
    add_issue_form=None,
    edit_issue_form=None,
    add_task_form=None,
    edit_task_form=None,
    edit_task=None,
    active_tab=None,
    open_modal=None,
):
    values = _normalised_list_values(request)
    issues = filtered_issues_for_user(
        user=request.user,
        **{**values, "state": values["state"] or Issue.State.ACTIVE},
    )
    paginator = Paginator(issues, ISSUES_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))

    if selected_issue is None:
        try:
            selected_id = int(request.GET.get("selected", ""))
        except (TypeError, ValueError):
            selected_id = None
        selected_issue = next(
            (issue for issue in page_obj if issue.pk == selected_id),
            None,
        )
        if selected_issue is None and selected_id is not None and request.GET.get("open") in ("detail", "edit"):
            selected_issue = issues_for_user(user=request.user).filter(pk=selected_id).first()

    if selected_issue is None and page_obj.object_list:
        selected_issue = page_obj.object_list[0]

    selected_tasks = (
        tasks_for_issue(user=request.user, issue=selected_issue)
        if selected_issue is not None
        else Task.objects.none()
    )

    requested_tab = active_tab or request.GET.get("tab", "details")
    if requested_tab not in ("details", "tasks"):
        requested_tab = "details"

    list_parameters = _list_query_parameters(values)
    navigation_parameters = dict(list_parameters)
    if page_obj.number > 1:
        navigation_parameters["page"] = page_obj.number

    properties = properties_for_user(user=request.user).order_by("name", "pk")
    return {
        "page_obj": page_obj,
        "selected_issue": selected_issue,
        "selected_tasks": selected_tasks,
        "active_task_count": selected_tasks.filter(state=Task.State.ACTIVE).count(),
        "linked_task_count": selected_tasks.count(),
        "add_issue_form": add_issue_form or IssueForm(
            user=request.user,
            auto_id="add_issue_%s",
        ),
        "edit_issue_form": edit_issue_form or (
            IssueForm(
                user=request.user,
                instance=selected_issue,
                auto_id="edit_issue_%s",
            )
            if selected_issue and selected_issue.state == Issue.State.ACTIVE
            else None
        ),
        "add_task_form": add_task_form or (
            TaskForm(
                user=request.user,
                parent_issue=selected_issue,
                auto_id="add_issue_task_%s",
            )
            if selected_issue and selected_issue.state == Issue.State.ACTIVE
            else None
        ),
        "edit_task_form": edit_task_form or (
            TaskForm(
                user=request.user,
                auto_id="edit_issue_task_%s",
            )
            if selected_issue and selected_issue.state == Issue.State.ACTIVE
            else None
        ),
        "edit_task": edit_task,
        "active_tab": requested_tab,
        "open_modal": open_modal,
        "search": values["search"],
        "state": values["state"],
        "priority": values["priority"],
        "property_id": values["property_id"],
        "deadline_period": values["deadline_period"],
        "sort": values["sort"],
        "deadline_period_options": ISSUE_DEADLINE_PERIOD_OPTIONS,
        "issue_state_choices": Issue.State.choices,
        "deadline_period_label": ISSUE_DEADLINE_PERIOD_OPTIONS.get(
            values["deadline_period"], ""
        ),
        "properties": properties,
        "list_query": urlencode(list_parameters),
        "navigation_query": urlencode(navigation_parameters),
        "has_filters": any(
            (
                values["search"],
                values["state"],
                values["priority"],
                values["property_id"],
                values["deadline_period"],
            )
        ),
        "filter_count": sum(
            bool(value)
            for value in (
                values["state"],
                values["priority"],
                values["property_id"],
                values["deadline_period"],
            )
        ),
        "today": timezone.localdate(),
        "issue_count": issues_for_user(user=request.user).count(),
        "task_count": tasks_for_user(user=request.user).count(),
        "event_count": events_for_user(user=request.user).count(),
        "task_workspace_url": (
            _issue_workspace_url(
                request,
                issue_id=selected_issue.pk,
                tab="tasks",
            )
            if selected_issue
            else reverse("issue:issues")
        ),
    }


@login_required
@require_GET
def issues_view(request):
    context = _issue_list_context(request, **_restore_issue_form_context(request))
    origin = None
    if request.GET.get("open") == "add" and not context["open_modal"]:
        origin = active_property_for_user(request.user, request.GET.get("property"))
        if origin:
            context["add_issue_form"].initial["property"] = origin.pk
            context["open_modal"] = "addIssueModal"
    elif context["open_modal"] == "addIssueModal":
        origin = active_property_for_user(request.user, context["add_issue_form"].data.get("return_property"))
    context["return_property_id"] = origin.pk if origin else None
    if request.GET.get("open") == "edit" and context["edit_issue_form"] is not None:
        context["open_modal"] = "editIssueModal"
    return render(
        request,
        "issue/issues.html",
        context,
    )


@login_required
@require_POST
def add_issue_view(request):
    form = IssueForm(
        request.POST,
        user=request.user,
        auto_id="add_issue_%s",
    )
    if form.is_valid():
        issue = create_issue(user=request.user, **form.cleaned_data)
        property_url = created_record_property_url(issue, request.POST.get("return_property"), "issue")
        if property_url:
            return redirect(property_url)
        return redirect(_issue_workspace_url(request, issue_id=issue.pk))
    return _redirect_with_issue_form_state(
        request,
        action="add_issue",
    )


@login_required
@require_POST
def edit_issue_view(request, issue_id):
    issue = get_object_or_404(
        issues_for_user(user=request.user), pk=issue_id, state=Issue.State.ACTIVE
    )
    form = IssueForm(
        request.POST,
        user=request.user,
        instance=issue,
        auto_id="edit_issue_%s",
    )
    if form.is_valid():
        update_issue(issue=issue, **form.cleaned_data)
        return redirect(_issue_workspace_url(request, issue_id=issue.pk))
    return _redirect_with_issue_form_state(
        request,
        action="edit_issue",
        issue_id=issue.pk,
    )


@login_required
@require_POST
def resolve_issue_view(request, issue_id):
    issue = get_object_or_404(
        issues_for_user(user=request.user), pk=issue_id, state=Issue.State.ACTIVE
    )
    resolve_issue(
        issue=issue,
        dismiss_linked_tasks=request.POST.get("affect_linked_tasks") == "yes",
    )
    property_url = f"{reverse('property:property_detail', args=[issue.property_id])}?tab=work" if issue.property_id else None
    if property_url and request.POST.get("next") == property_url:
        return redirect(property_url)
    return redirect(_issue_workspace_url(request, issue_id=issue.pk))


@login_required
@require_POST
def dismiss_issue_view(request, issue_id):
    issue = get_object_or_404(
        issues_for_user(user=request.user), pk=issue_id, state=Issue.State.ACTIVE
    )
    dismiss_issue(
        issue=issue,
        dismiss_linked_tasks=request.POST.get("affect_linked_tasks") == "yes",
    )
    return redirect(_issue_workspace_url(request, issue_id=issue.pk))


@login_required
@require_POST
def reactivate_issue_view(request, issue_id):
    issue = get_object_or_404(
        issues_for_user(user=request.user),
        pk=issue_id,
        state__in=[Issue.State.RESOLVED, Issue.State.DISMISSED],
    )
    reactivate_issue(issue=issue)
    return redirect(_issue_workspace_url(request, issue_id=issue.pk))


@login_required
@require_POST
def delete_issue_view(request, issue_id):
    issue = get_object_or_404(issues_for_user(user=request.user), pk=issue_id)
    delete_issue(
        issue=issue,
        delete_linked_tasks=request.POST.get("affect_linked_tasks") == "yes",
    )
    return redirect(_issue_workspace_url(request))


@login_required
@require_POST
def add_issue_task_view(request, issue_id):
    issue = get_object_or_404(
        issues_for_user(user=request.user), pk=issue_id, state=Issue.State.ACTIVE
    )
    form = TaskForm(
        request.POST,
        user=request.user,
        parent_issue=issue,
        auto_id="add_issue_task_%s",
    )
    if form.is_valid():
        create_task(
            user=request.user,
            property=None,
            issue=issue,
            **form.cleaned_data,
        )
        return redirect(_issue_workspace_url(request, issue_id=issue.pk, tab="tasks"))
    return _redirect_with_issue_form_state(
        request,
        action="add_issue_task",
        issue_id=issue.pk,
        tab="tasks",
    )


@login_required
@require_POST
def edit_issue_task_view(request, issue_id, task_id):
    issue = get_object_or_404(
        issues_for_user(user=request.user), pk=issue_id, state=Issue.State.ACTIVE
    )
    task = get_object_or_404(
        tasks_for_issue(user=request.user, issue=issue),
        pk=task_id,
        state=Task.State.ACTIVE,
    )
    form = TaskForm(
        request.POST,
        user=request.user,
        instance=task,
        auto_id="edit_issue_task_%s",
    )
    if form.is_valid():
        update_task(task=task, **form.cleaned_data)
        if task.issue_id != issue.pk:
            return redirect(f"{reverse('task:tasks')}?selected={task.pk}&moved=1")
        return redirect(_issue_workspace_url(request, issue_id=issue.pk, tab="tasks"))
    return _redirect_with_issue_form_state(
        request,
        action="edit_issue_task",
        issue_id=issue.pk,
        object_id=task.pk,
        tab="tasks",
    )
