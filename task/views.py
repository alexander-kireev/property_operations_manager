from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .selectors import (
    TASK_DEADLINE_PERIOD_OPTIONS,
    TASK_SCHEDULE_PERIOD_OPTIONS,
    TASK_SORT_OPTIONS,
    filtered_tasks_for_user,
    tasks_for_user
)

from .services import (
    create_task,
    update_task,
    dismiss_task,
    complete_task,
    delete_task,
    reactivate_task
)

from .forms import TaskForm
from .models import Task

TASKS_PER_PAGE = 20


def _task_list_context(request, *, add_task_form=None):
    search = request.GET.get("search", "").strip()
    state = request.GET.get("state", "")
    sort = request.GET.get("sort", "")
    priority_value = request.GET.get("priority", "")
    scheduled_period = request.GET.get("scheduled_period", "")
    deadline_period = request.GET.get("deadline_period", "")

    if state not in Task.State.values:
        state = ""

    if sort not in TASK_SORT_OPTIONS:
        sort = "title"

    try:
        priority = int(priority_value)
    except (TypeError, ValueError):
        priority = ""

    if priority not in Task.Priority.values:
        priority = ""

    if scheduled_period not in TASK_SCHEDULE_PERIOD_OPTIONS:
        scheduled_period = ""

    if deadline_period not in TASK_DEADLINE_PERIOD_OPTIONS:
        deadline_period = ""

    tasks = filtered_tasks_for_user(
        user=request.user,
        search=search,
        state=state,
        priority=priority,
        scheduled_period=scheduled_period,
        deadline_period=deadline_period,
        sort=sort,
    )

    paginator = Paginator(tasks, TASKS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_parameters = {}

    if search:
        query_parameters["search"] = search

    if state:
        query_parameters["state"] = state

    if priority:
        query_parameters["priority"] = priority

    if scheduled_period:
        query_parameters["scheduled_period"] = scheduled_period

    if deadline_period:
        query_parameters["deadline_period"] = deadline_period

    if sort != "title":
        query_parameters["sort"] = sort

    return {
        "add_task_form": (
            add_task_form
            if add_task_form is not None
            else TaskForm(user=request.user)
        ),
        "page_obj": page_obj,
        "search": search,
        "state": state,
        "priority": priority,
        "scheduled_period": scheduled_period,
        "deadline_period": deadline_period,
        "sort": sort,
        "schedule_period_options": TASK_SCHEDULE_PERIOD_OPTIONS,
        "deadline_period_options": TASK_DEADLINE_PERIOD_OPTIONS,
        "list_query": urlencode(query_parameters),
        "has_filters": bool(
            search
            or state
            or priority
            or deadline_period
            or scheduled_period
        ),
    }


def _task_detail_context(request, task, *, edit_task_form=None):
    return {
        "task": task,
        "edit_task_form": (
            edit_task_form if edit_task_form is not None
            else TaskForm(user=request.user, instance=task)
        )
    }


@login_required
@require_GET
def tasks_view(request):
    return render(
        request,
        "task/tasks.html",
        _task_list_context(request)
    )

@login_required
@require_GET
def task_detail_view(request, task_id):
    task = get_object_or_404(
        tasks_for_user(user=request.user),
        pk=task_id
    )

    return render(
        request,
        "task/task_detail.html",
        _task_detail_context(request, task)
    )

@login_required
@require_POST
def edit_task_view(request, task_id):
    task = get_object_or_404(
        tasks_for_user(user=request.user),
        pk=task_id,
        state=Task.State.ACTIVE
    )
    form = TaskForm(
        request.POST,
        user=request.user,
        instance=task
    )

    if form.is_valid():
        update_task(
            task=task,
            **form.cleaned_data
        )

        return redirect("task:task_detail", task_id=task.pk)

    return render(
        request,
        "task/task_detail.html",
        _task_detail_context(
            request,
            task,
            edit_task_form=form
        )
    )


@login_required
@require_POST
def dismiss_task_view(request, task_id):
    task = get_object_or_404(
        tasks_for_user(user=request.user),
        pk=task_id,
        state=Task.State.ACTIVE
    )

    dismiss_task(task=task)

    return redirect("task:task_detail", task_id=task.pk)


@login_required
@require_POST
def complete_task_view(request, task_id):
    task = get_object_or_404(
        tasks_for_user(user=request.user),
        pk=task_id,
        state=Task.State.ACTIVE
    )

    complete_task(task=task)

    return redirect("task:task_detail", task_id=task.pk)


@login_required
@require_POST
def reactivate_task_view(request, task_id):
    task = get_object_or_404(
        tasks_for_user(user=request.user),
        pk=task_id,
        state__in=[
            Task.State.DISMISSED,
            Task.State.COMPLETED
        ]
    )

    reactivate_task(task=task)

    return redirect("task:task_detail", task_id=task.pk)



@login_required
@require_POST
def add_task_view(request):
    form = TaskForm(request.POST, user=request.user)

    if form.is_valid():
        task_record = create_task(
            user=request.user,
            **form.cleaned_data
        )

        return redirect("task:task_detail", task_id=task_record.pk)

    return render(
        request,
        "task/tasks.html",
        _task_list_context(request, add_task_form=form)
    )

@login_required
@require_POST
def delete_task_view(request, task_id):
    task = get_object_or_404(
        tasks_for_user(user=request.user),
        pk=task_id
    )

    delete_task(task=task)

    return redirect("task:tasks")