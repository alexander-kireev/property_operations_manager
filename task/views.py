from urllib.parse import parse_qs, urlencode, urlsplit

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from config.form_state import (
    deserialise_form_data,
    pop_form_state,
    serialise_form_data,
    store_form_state,
)

from issue.selectors import issues_for_user
from event.selectors import events_for_user

from .forms import TaskForm
from .models import Task
from .selectors import (
    TASK_DEADLINE_PERIOD_OPTIONS,
    TASK_SCHEDULE_PERIOD_OPTIONS,
    TASK_SORT_OPTIONS,
    filtered_tasks_for_user,
    tasks_for_user,
)
from .services import (
    complete_task,
    create_task,
    delete_task,
    dismiss_task,
    reactivate_task,
    update_task,
)


TASKS_PER_PAGE = 20


def _normalised_list_values(request):
    search = request.GET.get("search", "").strip()
    state = request.GET.get("state", "")
    sort = request.GET.get("sort", "completion_deadline")
    priority_value = request.GET.get("priority", "")
    scheduled_period = request.GET.get("scheduled_period", "")
    deadline_period = request.GET.get("deadline_period", "")

    if state not in (*Task.State.values, "all"):
        state = ""
    if sort not in TASK_SORT_OPTIONS:
        sort = "completion_deadline"
    if scheduled_period not in TASK_SCHEDULE_PERIOD_OPTIONS:
        scheduled_period = ""
    if deadline_period not in TASK_DEADLINE_PERIOD_OPTIONS:
        deadline_period = ""

    try:
        priority = int(priority_value)
    except (TypeError, ValueError):
        priority = ""
    if priority not in Task.Priority.values:
        priority = ""

    return {
        "search": search,
        "state": state,
        "priority": priority,
        "scheduled_period": scheduled_period,
        "deadline_period": deadline_period,
        "sort": sort,
    }


def _list_query_parameters(values):
    parameters = {}
    for name in (
        "search",
        "state",
        "priority",
        "scheduled_period",
        "deadline_period",
    ):
        if values[name]:
            parameters[name] = values[name]
    if values["sort"] != "completion_deadline":
        parameters["sort"] = values["sort"]
    return parameters


def _task_workspace_url(request, *, task_id=None, form_state=None):
    parameters = _list_query_parameters(_normalised_list_values(request))
    page = request.GET.get("page", "")
    if page.isdigit() and int(page) > 1:
        parameters["page"] = page
    if task_id is not None:
        parameters["selected"] = task_id
    if form_state is not None:
        parameters["form_state"] = form_state

    url = reverse("task:tasks")
    return f"{url}?{urlencode(parameters)}" if parameters else url


def _restore_add_task_form(request, state):
    return {
        "add_task_form": TaskForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            auto_id="add_task_%s",
        ),
        "open_modal": "addTaskModal",
    }


def _restore_edit_task_form(request, state):
    task = tasks_for_user(user=request.user).filter(
        pk=state.get("task_id"),
        state=Task.State.ACTIVE,
    ).first()
    if task is None:
        return {}
    return {
        "selected_task": task,
        "edit_task_form": TaskForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            instance=task,
            auto_id="edit_task_%s",
        ),
        "open_modal": "editTaskModal",
    }


TASK_FORM_STATE_RESTORERS = {
    "add_task": _restore_add_task_form,
    "edit_task": _restore_edit_task_form,
}


def _restore_task_form_context(request):
    state = pop_form_state(request)
    if not isinstance(state, dict):
        return {}
    restorer = TASK_FORM_STATE_RESTORERS.get(state.get("action"))
    return restorer(request, state) if restorer is not None else {}


def _redirect_with_task_form_state(request, *, action, task_id=None):
    token = store_form_state(request, {
        "action": action,
        "task_id": task_id,
        "data": serialise_form_data(request.POST),
    })
    return redirect(
        _task_workspace_url(
            request,
            task_id=task_id,
            form_state=token,
        )
    )


def _task_action_redirect(request, *, task, deleted=False):
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        parsed_next = urlsplit(next_url)
        next_path = parsed_next.path
        is_task_workspace = next_path == reverse("task:tasks")
        is_own_issue_workspace = (
            task.issue_id
            and next_path == reverse("issue:issues")
            and parse_qs(parsed_next.query).get("selected")
            == [str(task.issue_id)]
        )
        if is_task_workspace or is_own_issue_workspace:
            return redirect(next_url)

    return redirect(
        _task_workspace_url(
            request,
            task_id=None if deleted else task.pk,
        )
    )


def _task_list_context(
    request,
    *,
    selected_task=None,
    add_task_form=None,
    edit_task_form=None,
    open_modal=None,
):
    values = _normalised_list_values(request)
    tasks = filtered_tasks_for_user(
        user=request.user,
        **{**values, "state": values["state"] or Task.State.ACTIVE},
    )
    paginator = Paginator(tasks, TASKS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))

    if selected_task is None:
        try:
            selected_id = int(request.GET.get("selected", ""))
        except (TypeError, ValueError):
            selected_id = None
        selected_task = next(
            (task for task in page_obj if task.pk == selected_id),
            None,
        )

    if selected_task is None and page_obj.object_list:
        selected_task = page_obj.object_list[0]

    list_parameters = _list_query_parameters(values)
    navigation_parameters = dict(list_parameters)
    if page_obj.number > 1:
        navigation_parameters["page"] = page_obj.number

    return {
        "page_obj": page_obj,
        "selected_task": selected_task,
        "add_task_form": (
            add_task_form
            if add_task_form is not None
            else TaskForm(user=request.user, auto_id="add_task_%s")
        ),
        "edit_task_form": (
            edit_task_form
            if edit_task_form is not None
            else (
                TaskForm(
                    user=request.user,
                    instance=selected_task,
                    auto_id="edit_task_%s",
                )
                if selected_task
                and selected_task.state == Task.State.ACTIVE
                else None
            )
        ),
        "open_modal": open_modal,
        "search": values["search"],
        "state": values["state"],
        "priority": values["priority"],
        "scheduled_period": values["scheduled_period"],
        "deadline_period": values["deadline_period"],
        "sort": values["sort"],
        "schedule_period_options": TASK_SCHEDULE_PERIOD_OPTIONS,
        "deadline_period_options": TASK_DEADLINE_PERIOD_OPTIONS,
        "scheduled_period_label": TASK_SCHEDULE_PERIOD_OPTIONS.get(
            values["scheduled_period"], ""
        ),
        "deadline_period_label": TASK_DEADLINE_PERIOD_OPTIONS.get(
            values["deadline_period"], ""
        ),
        "list_query": urlencode(list_parameters),
        "navigation_query": urlencode(navigation_parameters),
        "today": timezone.localdate(),
        "has_filters": any(
            (
                values["search"],
                values["state"],
                values["priority"],
                values["scheduled_period"],
                values["deadline_period"],
            )
        ),
        "filter_count": sum(
            bool(value)
            for value in (
                values["state"],
                values["priority"],
                values["scheduled_period"],
                values["deadline_period"],
            )
        ),
        "task_count": tasks_for_user(user=request.user).count(),
        "issue_count": issues_for_user(user=request.user).count(),
        "event_count": events_for_user(user=request.user).count(),
        "task_workspace_url": (
            _task_workspace_url(request, task_id=selected_task.pk)
            if selected_task
            else _task_workspace_url(request)
        ),
        "task_list_url": _task_workspace_url(request),
        "show_mobile_detail": bool(request.GET.get("selected")) or (
            open_modal == "editTaskModal"
        ),
        "relationship_moved": (
            request.GET.get("moved") == "1"
            and selected_task is not None
            and request.GET.get("selected") == str(selected_task.pk)
        ),
    }


@login_required
@require_GET
def tasks_view(request):
    return render(
        request,
        "task/tasks.html",
        _task_list_context(request, **_restore_task_form_context(request)),
    )


@login_required
@require_POST
def add_task_view(request):
    form = TaskForm(
        request.POST,
        user=request.user,
        auto_id="add_task_%s",
    )
    if form.is_valid():
        task = create_task(user=request.user, **form.cleaned_data)
        return redirect(_task_workspace_url(request, task_id=task.pk))
    return _redirect_with_task_form_state(
        request,
        action="add_task",
    )


@login_required
@require_POST
def edit_task_view(request, task_id):
    task = get_object_or_404(
        tasks_for_user(user=request.user),
        pk=task_id,
        state=Task.State.ACTIVE,
    )
    form = TaskForm(
        request.POST,
        user=request.user,
        instance=task,
        auto_id="edit_task_%s",
    )
    if form.is_valid():
        update_task(task=task, **form.cleaned_data)
        return redirect(_task_workspace_url(request, task_id=task.pk))
    return _redirect_with_task_form_state(
        request,
        action="edit_task",
        task_id=task.pk,
    )


@login_required
@require_POST
def dismiss_task_view(request, task_id):
    task = get_object_or_404(
        tasks_for_user(user=request.user),
        pk=task_id,
        state=Task.State.ACTIVE,
    )
    dismiss_task(task=task)
    return _task_action_redirect(request, task=task)


@login_required
@require_POST
def complete_task_view(request, task_id):
    task = get_object_or_404(
        tasks_for_user(user=request.user),
        pk=task_id,
        state=Task.State.ACTIVE,
    )
    complete_task(task=task)
    return _task_action_redirect(request, task=task)


@login_required
@require_POST
def reactivate_task_view(request, task_id):
    task = get_object_or_404(
        tasks_for_user(user=request.user),
        pk=task_id,
        state__in=[Task.State.DISMISSED, Task.State.COMPLETED],
    )
    reactivate_task(task=task)
    return _task_action_redirect(request, task=task)


@login_required
@require_POST
def delete_task_view(request, task_id):
    task = get_object_or_404(tasks_for_user(user=request.user), pk=task_id)
    delete_task(task=task)
    return _task_action_redirect(request, task=task, deleted=True)
