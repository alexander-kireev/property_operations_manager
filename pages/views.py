from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie

from event.forms import EventForm
from event.models import Event
from event.services import cancel_event, create_event, delete_event, mark_event_occurred, update_event
from issue.forms import IssueForm
from issue.models import Issue
from issue.services import create_issue, delete_issue, resolve_issue, update_issue
from note.forms import NoteForm
from note.selectors import general_notes_for_user
from note.services import create_note, delete_note, update_note
from property.models import Property
from task.forms import TaskForm
from task.models import Task
from task.services import complete_task, create_task, delete_task, update_task


def home_view(request):
    return render(request, "pages/home.html")


def about_us_view(request):
    return render(request, "pages/about_us.html")


def contact_us_view(request):
    return render(request, "pages/contact_us.html")


@login_required
@ensure_csrf_cookie
def dashboard_view(request):
    return render(request, "pages/dashboard.html")


def _records_for_user(user, kind):
    model = {"task": Task, "issue": Issue, "event": Event}.get(kind)
    return model.objects.filter(user=user, deleted_at__isnull=True) if model else None


def _record_data(record, kind):
    property_record = record.property if record.property_id else None
    if kind == "task" and record.issue_id:
        property_record = record.issue.property
    data = {
        "id": record.pk, "kind": kind, "title": record.title,
        "description": record.description, "state": record.state,
        "property": property_record.name if property_record else "",
        "property_id": record.property_id,
        "date": record.scheduled_date.isoformat() if kind != "issue" and record.scheduled_date else "",
    }
    if kind == "task":
        data.update(priority=record.get_priority_display(), priority_id=record.priority,
                    due=record.completion_deadline.isoformat() if record.completion_deadline else "",
                    issue_id=record.issue_id)
    elif kind == "issue":
        data.update(priority=record.get_priority_display(), priority_id=record.priority,
                    due=record.resolution_deadline.isoformat() if record.resolution_deadline else "")
    else:
        data.update(all_day=record.all_day,
                    start_time=record.start_time.strftime("%H:%M") if record.start_time else "",
                    end_time=record.end_time.strftime("%H:%M") if record.end_time else "",
                    user_participation_required=record.user_participation_required,
                    user_presence_required=record.user_presence_required)
    return data


@login_required
@require_GET
def dashboard_data_view(request):
    records = {}
    for kind, state in (("task", Task.State.ACTIVE), ("issue", Issue.State.ACTIVE),
                        ("event", Event.State.SCHEDULED)):
        queryset = _records_for_user(request.user, kind).filter(state=state)
        queryset = queryset.select_related("property", "issue__property") if kind == "task" else queryset.select_related("property")
        records[kind] = [_record_data(item, kind) for item in queryset.order_by("pk")]
    notes = [{"id": item.pk, "content": item.content,
              "created": timezone.localtime(item.created_at).strftime("%d %b %Y, %H:%M")}
             for item in general_notes_for_user(user=request.user)]
    properties = list(Property.objects.filter(user=request.user, state=Property.State.ACTIVE,
                                               deleted_at__isnull=True).order_by("name").values("id", "name"))
    issues = list(Issue.objects.filter(user=request.user, state=Issue.State.ACTIVE,
                                       deleted_at__isnull=True).order_by("title").values("id", "title"))
    return JsonResponse({"today": timezone.localdate().isoformat(), "records": records,
                         "notes": notes, "properties": properties, "issues": issues})


@login_required
@require_POST
def dashboard_action_view(request):
    action, kind = request.POST.get("action"), request.POST.get("kind")
    record_id = request.POST.get("id", "")
    if action != "add" and (not record_id.isdecimal() or int(record_id) < 1):
        return JsonResponse({"error": "Record not found."}, status=404)
    if kind == "note":
        if action == "add":
            form = NoteForm(request.POST)
            if not form.is_valid():
                return JsonResponse({"errors": form.errors}, status=400)
            note = create_note(user=request.user, content=form.cleaned_data["content"])
        else:
            note = general_notes_for_user(user=request.user).filter(pk=record_id).first()
            if note is None:
                return JsonResponse({"error": "Note not found."}, status=404)
            if action == "delete":
                delete_note(note=note)
                return JsonResponse({"ok": True})
            if action != "edit":
                return JsonResponse({"error": "Unknown action."}, status=400)
            form = NoteForm(request.POST, instance=note)
            if not form.is_valid():
                return JsonResponse({"errors": form.errors}, status=400)
            update_note(note=note, content=form.cleaned_data["content"])
        return JsonResponse({"ok": True, "id": note.pk})

    queryset = _records_for_user(request.user, kind)
    if queryset is None:
        return JsonResponse({"error": "Unknown record type."}, status=400)
    record = None
    if action != "add":
        record = queryset.filter(pk=record_id).first()
        if record is None:
            return JsonResponse({"error": "Record not found."}, status=404)

    if action == "date":
        if kind not in ("task", "event") or record.state not in ("active", "scheduled"):
            return JsonResponse({"error": "This record cannot be scheduled."}, status=400)
        try:
            new_date = date.fromisoformat(request.POST.get("date", ""))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Choose a valid date."}, status=400)
        if kind == "event":
            data = {"title": record.title, "description": record.description,
                    "property": record.property_id or "", "scheduled_date": new_date.isoformat(),
                    "all_day": "on" if record.all_day else "",
                    "start_time": record.start_time.strftime("%H:%M") if record.start_time else "",
                    "end_time": record.end_time.strftime("%H:%M") if record.end_time else "",
                    "user_participation_required": "on" if record.user_participation_required else "",
                    "user_presence_required": "on" if record.user_presence_required else ""}
            form = EventForm(data, user=request.user, instance=record)
            if not form.is_valid():
                return JsonResponse({"errors": form.errors}, status=400)
        record.scheduled_date = new_date
        record.save(update_fields=["scheduled_date"])
    elif action == "deadline":
        if kind not in ("task", "issue") or record.state != "active":
            return JsonResponse({"error": "This deadline cannot be moved."}, status=400)
        try:
            new_date = date.fromisoformat(request.POST.get("date", ""))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Choose a valid date."}, status=400)
        field = "completion_deadline" if kind == "task" else "resolution_deadline"
        setattr(record, field, new_date)
        record.save(update_fields=[field])
    elif action in ("add", "edit"):
        form_class = {"task": TaskForm, "issue": IssueForm, "event": EventForm}[kind]
        form = form_class(request.POST, user=request.user, instance=record)
        if not form.is_valid():
            return JsonResponse({"errors": form.errors}, status=400)
        values = form.cleaned_data
        if kind == "task":
            fields = {name: values[name] for name in ("property", "issue", "priority", "title",
                                                       "description", "scheduled_date", "completion_deadline")}
            record = update_task(task=record, **fields) if record else create_task(user=request.user, **fields)
        elif kind == "issue":
            fields = {name: values[name] for name in ("property", "priority", "title",
                                                       "description", "resolution_deadline")}
            record = update_issue(issue=record, **fields) if record else create_issue(user=request.user, **fields)
        else:
            fields = {name: values[name] for name in ("property", "title", "description",
                                                       "scheduled_date", "all_day", "start_time", "end_time",
                                                       "user_participation_required", "user_presence_required")}
            record = update_event(event=record, **fields) if record else create_event(user=request.user, **fields)
    elif action == "finish":
        if kind == "task":
            complete_task(task=record)
        elif kind == "issue":
            resolve_issue(issue=record)
        else:
            mark_event_occurred(event=record)
    elif action == "cancel" and kind == "event":
        cancel_event(event=record)
    elif action == "delete":
        if kind == "task":
            delete_task(task=record)
        elif kind == "issue":
            delete_issue(issue=record)
        else:
            delete_event(event=record)
    else:
        return JsonResponse({"error": "Unknown action."}, status=400)
    return JsonResponse({"ok": True, "id": record.pk})
