import calendar
from collections import defaultdict
from datetime import date
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
from issue.selectors import issues_for_user
from task.selectors import tasks_for_user

from .forms import EventContactForm, EventForm
from .models import Event, EventContact
from .selectors import (
    EVENT_SORT_OPTIONS,
    USER_PARTICIPATION_REQUIRED_OPTIONS,
    USER_PRESENCE_REQUIRED_OPTIONS,
    calendar_events_for_user,
    event_contacts_for_event,
    events_for_user,
    filtered_events_for_user,
)
from .services import (
    add_contacts_to_event,
    cancel_event,
    create_event,
    delete_event,
    mark_event_occurred,
    reactivate_event,
    remove_contact_from_event,
    update_event,
)

EVENTS_PER_PAGE = 20
DEFAULT_EVENT_STATE = Event.State.SCHEDULED


def _normalised_list_values(request):
    search = request.GET.get("search", "").strip()
    state = request.GET.get("state", DEFAULT_EVENT_STATE)
    sort = request.GET.get("sort", "scheduled_date")
    property_value = request.GET.get("property", "")
    participation = request.GET.get("participation", "any").lower()
    presence = request.GET.get("presence", "any").lower()

    if state not in (*Event.State.values, "all"):
        state = DEFAULT_EVENT_STATE
    if sort not in EVENT_SORT_OPTIONS:
        sort = "scheduled_date"
    if participation not in USER_PARTICIPATION_REQUIRED_OPTIONS:
        participation = "any"
    if presence not in USER_PRESENCE_REQUIRED_OPTIONS:
        presence = "any"
    try:
        property_id = int(property_value)
    except (TypeError, ValueError):
        property_id = ""

    return {
        "search": search,
        "state": state,
        "sort": sort,
        "property_id": property_id,
        "participation": participation,
        "presence": presence,
    }


def _list_query_parameters(values):
    parameters = {}
    if values["search"]:
        parameters["search"] = values["search"]
    if values["state"] != DEFAULT_EVENT_STATE:
        parameters["state"] = values["state"]
    for name in ("participation", "presence"):
        if values[name] != "any":
            parameters[name] = values[name]
    if values["property_id"]:
        parameters["property"] = values["property_id"]
    if values["sort"] != "scheduled_date":
        parameters["sort"] = values["sort"]
    return parameters


def _calendar_month(request):
    today = timezone.localdate()
    try:
        return date(int(request.GET.get("year")), int(request.GET.get("month")), 1)
    except (TypeError, ValueError):
        return today.replace(day=1)


def _shift_month(month, offset):
    month_index = month.year * 12 + month.month - 1 + offset
    year, zero_based_month = divmod(month_index, 12)
    if year < 1 or year > 9999:
        return month
    return date(year, zero_based_month + 1, 1)


def _calendar_query(values, month):
    parameters = _list_query_parameters(values)
    parameters.update({"month": month.month, "year": month.year, "tab": "calendar"})
    return urlencode(parameters)


def _selected_day(request):
    try:
        return date.fromisoformat(request.GET.get("day", ""))
    except (TypeError, ValueError):
        return None


def _event_workspace_url(
    request,
    *,
    event_id=None,
    tab="details",
    form_state=None,
    state=None,
):
    parameters = _list_query_parameters(_normalised_list_values(request))
    selected_day = _selected_day(request)
    if selected_day is not None:
        parameters["day"] = selected_day.isoformat()
    if state is not None:
        if state == DEFAULT_EVENT_STATE:
            parameters.pop("state", None)
        else:
            parameters["state"] = state
    try:
        page = int(request.GET.get("page", ""))
    except (TypeError, ValueError):
        page = None
    if page is not None and page > 1:
        parameters["page"] = page
    if request.GET.get("month") and request.GET.get("year"):
        displayed_month = _calendar_month(request)
        parameters["month"] = displayed_month.month
        parameters["year"] = displayed_month.year
    if event_id is not None:
        parameters["selected"] = event_id
    if tab == "calendar":
        parameters["tab"] = "calendar"
    if form_state is not None:
        parameters["form_state"] = form_state
    url = reverse("event:events")
    return f"{url}?{urlencode(parameters)}" if parameters else url


def _scheduled_event_from_form_state(request, state):
    return events_for_user(user=request.user).filter(
        pk=state.get("event_id"),
        state=Event.State.SCHEDULED,
    ).first()


def _restore_add_event_forms(request, state):
    data = deserialise_form_data(state.get("data", {}))
    return {
        "add_event_form": EventForm(
            data,
            user=request.user,
            auto_id="add_event_%s",
        ),
        "initial_contacts_form": EventContactForm(
            data,
            user=request.user,
            auto_id="initial_contacts_%s",
        ),
        "open_modal": "addEventModal",
    }


def _restore_edit_event_form(request, state):
    event = _scheduled_event_from_form_state(request, state)
    if event is None:
        return {}
    return {
        "selected_event": event,
        "edit_event_form": EventForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            instance=event,
            auto_id="edit_event_%s",
        ),
        "active_tab": "details",
        "open_modal": "editEventModal",
    }


def _restore_add_event_contacts_form(request, state):
    event = _scheduled_event_from_form_state(request, state)
    if event is None:
        return {}
    return {
        "selected_event": event,
        "add_contacts_form": EventContactForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            event=event,
            auto_id="event_contacts_%s",
        ),
        "active_tab": "details",
        "open_modal": "addEventContactsModal",
    }


EVENT_FORM_STATE_RESTORERS = {
    "add_event": _restore_add_event_forms,
    "edit_event": _restore_edit_event_form,
    "add_event_contacts": _restore_add_event_contacts_form,
}


def _restore_event_form_context(request):
    state = pop_form_state(request)
    if not isinstance(state, dict):
        return {}
    restorer = EVENT_FORM_STATE_RESTORERS.get(state.get("action"))
    return restorer(request, state) if restorer is not None else {}


def _redirect_with_event_form_state(
    request,
    *,
    action,
    event_id=None,
):
    token = store_form_state(request, {
        "action": action,
        "event_id": event_id,
        "data": serialise_form_data(request.POST),
    })
    return redirect(
        _event_workspace_url(
            request,
            event_id=event_id,
            form_state=token,
        )
    )


def _event_list_context(
    request,
    *,
    selected_event=None,
    add_event_form=None,
    initial_contacts_form=None,
    edit_event_form=None,
    add_contacts_form=None,
    active_tab=None,
    open_modal=None,
):
    values = _normalised_list_values(request)
    selected_day = _selected_day(request)
    events = filtered_events_for_user(user=request.user, **values)
    if selected_day is not None:
        events = events.filter(scheduled_date=selected_day)
        if values["sort"] == "scheduled_date":
            events = events.order_by("-all_day", "start_time", "title", "pk")
    paginator = Paginator(events, EVENTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))

    if selected_event is None:
        try:
            selected_id = int(request.GET.get("selected", ""))
        except (TypeError, ValueError):
            selected_id = None
        if selected_id is not None:
            selected_event = events.filter(pk=selected_id).first()
        if selected_event is None and page_obj.object_list:
            selected_event = page_obj.object_list[0]

    requested_tab = active_tab or request.GET.get("tab")
    if requested_tab not in ("details", "calendar"):
        requested_tab = "details" if request.GET.get("selected") else "calendar"

    list_parameters = _list_query_parameters(values)
    if selected_day is not None:
        list_parameters["day"] = selected_day.isoformat()
    navigation_parameters = dict(list_parameters)
    if page_obj.number > 1:
        navigation_parameters["page"] = page_obj.number

    displayed_month = _calendar_month(request)
    month_dates = calendar.Calendar(firstweekday=calendar.MONDAY).monthdatescalendar(
        displayed_month.year,
        displayed_month.month,
    )
    calendar_events = list(calendar_events_for_user(
        user=request.user,
        start_date=month_dates[0][0],
        end_date=month_dates[-1][-1],
        **values,
    ))
    events_by_date = defaultdict(list)
    for event in calendar_events:
        events_by_date[event.scheduled_date].append(event)

    today = timezone.localdate()
    first_month_event = next(
        (event.scheduled_date for event in calendar_events
         if event.scheduled_date.month == displayed_month.month
         and event.scheduled_date.year == displayed_month.year),
        None,
    )
    mobile_agenda_day = selected_day or (
        today if today.year == displayed_month.year
        and today.month == displayed_month.month
        and events_by_date[today] else first_month_event or displayed_month
    )
    calendar_weeks = [[{
        "date": day,
        "in_month": day.month == displayed_month.month,
        "is_today": day == today,
        "events": events_by_date[day],
        "first_event": events_by_date[day][0] if events_by_date[day] else None,
        "more_count": max(0, len(events_by_date[day]) - 1),
    } for day in week] for week in month_dates]

    day_query_parameters = _list_query_parameters(values)
    day_query_parameters.update({"month": displayed_month.month, "year": displayed_month.year})

    navigation_parameters.update({
        "month": displayed_month.month,
        "year": displayed_month.year,
    })
    properties = properties_for_user(user=request.user).order_by("name", "pk")
    selected_event_is_active = (
        selected_event is not None and selected_event.state == Event.State.SCHEDULED
    )
    participants = (
        event_contacts_for_event(event=selected_event)
        if selected_event is not None
        else EventContact.objects.none()
    )

    return {
        "page_obj": page_obj,
        "selected_event": selected_event,
        "mobile_expanded_event_id": (
            selected_event.pk if selected_event is not None
            and request.GET.get("selected") == str(selected_event.pk) else None
        ),
        "participants": participants,
        "add_event_form": add_event_form if add_event_form is not None else EventForm(
            user=request.user, auto_id="add_event_%s"
        ),
        "initial_contacts_form": (
            initial_contacts_form
            if initial_contacts_form is not None
            else EventContactForm(user=request.user, auto_id="initial_contacts_%s")
        ),
        "edit_event_form": (
            edit_event_form
            if edit_event_form is not None
            else EventForm(
                user=request.user,
                instance=selected_event,
                auto_id="edit_event_%s",
            ) if selected_event_is_active else None
        ),
        "add_contacts_form": (
            add_contacts_form
            if add_contacts_form is not None
            else EventContactForm(
                user=request.user,
                event=selected_event,
                auto_id="event_contacts_%s",
            ) if selected_event_is_active else None
        ),
        "active_tab": requested_tab,
        "open_modal": open_modal,
        "search": values["search"],
        "state": values["state"],
        "sort": values["sort"],
        "property_id": values["property_id"],
        "participation": values["participation"],
        "presence": values["presence"],
        "event_state_choices": Event.State.choices,
        "properties": properties,
        "list_query": urlencode(list_parameters),
        "selected_day": selected_day,
        "day_query_base": urlencode(day_query_parameters),
        "clear_day_query": urlencode(day_query_parameters),
        "navigation_query": urlencode(navigation_parameters),
        "calendar_month_label": displayed_month.strftime("%B %Y"),
        "calendar_month_number": displayed_month.month,
        "calendar_year": displayed_month.year,
        "calendar_weekdays": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
        "calendar_weeks": calendar_weeks,
        "mobile_agenda_day": mobile_agenda_day,
        "mobile_agenda_events": events_by_date[mobile_agenda_day],
        "calendar_event_count": len(calendar_events),
        "previous_month_query": _calendar_query(values, _shift_month(displayed_month, -1)),
        "next_month_query": _calendar_query(values, _shift_month(displayed_month, 1)),
        "previous_year_query": _calendar_query(values, _shift_month(displayed_month, -12)),
        "next_year_query": _calendar_query(values, _shift_month(displayed_month, 12)),
        "today_query": _calendar_query(values, today.replace(day=1)),
        "has_filters": any((
            values["search"],
            values["state"] != DEFAULT_EVENT_STATE,
            values["property_id"],
            values["participation"] != "any",
            values["presence"] != "any",
        )),
        "filter_count": sum(bool(value) for value in (
            values["state"] != DEFAULT_EVENT_STATE,
            values["property_id"],
            values["participation"] != "any",
            values["presence"] != "any",
        )),
        "event_count": events_for_user(user=request.user).count(),
        "issue_count": issues_for_user(user=request.user).count(),
        "task_count": tasks_for_user(user=request.user).count(),
    }


@login_required
@require_GET
def events_view(request):
    context = _event_list_context(request, **_restore_event_form_context(request))
    if request.GET.get("open") == "edit" and context["edit_event_form"] is not None:
        context["open_modal"] = "editEventModal"
    return render(
        request,
        "event/events.html",
        context,
    )


@login_required
@require_POST
def add_event_view(request):
    event_form = EventForm(request.POST, user=request.user, auto_id="add_event_%s")
    contacts_form = EventContactForm(
        request.POST,
        user=request.user,
        auto_id="initial_contacts_%s",
    )
    event_is_valid = event_form.is_valid()
    contacts_are_valid = contacts_form.is_valid()
    if event_is_valid and contacts_are_valid:
        event = create_event(
            user=request.user,
            contacts=contacts_form.cleaned_data["contacts"],
            **event_form.cleaned_data,
        )
        return redirect(_event_workspace_url(request, event_id=event.pk))
    return _redirect_with_event_form_state(
        request,
        action="add_event",
    )


@login_required
@require_POST
def delete_event_view(request, event_id):
    event = get_object_or_404(events_for_user(user=request.user), pk=event_id)
    delete_event(event=event)
    return redirect(_event_workspace_url(request))


@login_required
@require_POST
def edit_event_view(request, event_id):
    event = get_object_or_404(
        events_for_user(user=request.user),
        pk=event_id,
        state=Event.State.SCHEDULED,
    )
    form = EventForm(
        request.POST,
        user=request.user,
        instance=event,
        auto_id="edit_event_%s",
    )
    if form.is_valid():
        update_event(event=event, **form.cleaned_data)
        return redirect(_event_workspace_url(request, event_id=event.pk))
    return _redirect_with_event_form_state(
        request,
        action="edit_event",
        event_id=event.pk,
    )


@login_required
@require_POST
def mark_event_occurred_view(request, event_id):
    event = get_object_or_404(
        events_for_user(user=request.user), pk=event_id, state=Event.State.SCHEDULED
    )
    mark_event_occurred(event=event)
    return redirect(
        _event_workspace_url(request, event_id=event_id, state="all")
    )


@login_required
@require_POST
def cancel_event_view(request, event_id):
    event = get_object_or_404(
        events_for_user(user=request.user), pk=event_id, state=Event.State.SCHEDULED
    )
    cancel_event(event=event)
    property_url = f"{reverse('property:property_detail', args=[event.property_id])}?tab=schedule" if event.property_id else None
    if property_url and request.POST.get("next") == property_url:
        return redirect(property_url)
    return redirect(
        _event_workspace_url(request, event_id=event_id, state="all")
    )


@login_required
@require_POST
def reactivate_event_view(request, event_id):
    event = get_object_or_404(events_for_user(user=request.user), pk=event_id)
    reactivate_event(event=event)
    return redirect(_event_workspace_url(request, event_id=event_id))


@login_required
@require_POST
def add_event_contacts_to_event_view(request, event_id):
    event = get_object_or_404(
        events_for_user(user=request.user), pk=event_id, state=Event.State.SCHEDULED
    )
    form = EventContactForm(request.POST, user=request.user, event=event)
    if form.is_valid():
        add_contacts_to_event(event=event, contacts=form.cleaned_data["contacts"])
        return redirect(_event_workspace_url(request, event_id=event.pk))
    return _redirect_with_event_form_state(
        request,
        action="add_event_contacts",
        event_id=event.pk,
    )


@login_required
@require_POST
def delete_event_contact_from_event_view(request, event_id, event_contact_id):
    event = get_object_or_404(
        events_for_user(user=request.user), pk=event_id, state=Event.State.SCHEDULED
    )
    event_contact = get_object_or_404(
        EventContact.objects.select_related("event"),
        pk=event_contact_id,
        event=event,
    )
    remove_contact_from_event(event_contact=event_contact)
    return redirect(_event_workspace_url(request, event_id=event.pk))
