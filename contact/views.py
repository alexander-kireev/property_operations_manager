from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from config.form_state import (
    deserialise_form_data,
    pop_form_state,
    serialise_form_data,
    store_form_state,
)

from .forms import ContactCreateForm, ContactForm, ContactMethodForm
from .models import Contact
from .selectors import (
    CONTACT_SORT_OPTIONS,
    contact_methods_for_contact,
    contacts_for_user,
    filtered_contacts_for_user,
)
from .services import (
    create_contact,
    create_contact_method,
    deactivate_contact,
    delete_contact,
    delete_contact_method,
    reactivate_contact,
    update_contact,
    update_contact_method,
)

from note.forms import NoteForm
from note.selectors import (
    notes_for_contact,
)

from note.services import (
    create_note,
    update_note,
    delete_note,
)



CONTACTS_PER_PAGE = 20
CONTACT_WORKSPACE_TABS = ("details", "notes")


def _active_contact_from_form_state(request, state):
    return contacts_for_user(user=request.user).filter(
        pk=state.get("contact_id"),
        state=Contact.State.ACTIVE,
    ).first()


def _restore_add_contact_form(request, state):
    return {
        "add_contact_form": ContactCreateForm(
            deserialise_form_data(state.get("data", {})),
            auto_id="add_contact_%s",
        ),
        "open_modal": "addContactModal",
    }


def _restore_edit_contact_form(request, state):
    contact = _active_contact_from_form_state(request, state)
    if contact is None:
        return {}

    return {
        "selected_contact": contact,
        "edit_contact_form": ContactForm(
            deserialise_form_data(state.get("data", {})),
            instance=contact,
            auto_id="edit_contact_%s",
        ),
        "active_tab": "details",
        "open_modal": "editContactModal",
    }


def _restore_add_contact_method_form(request, state):
    contact = _active_contact_from_form_state(request, state)
    if contact is None:
        return {}

    return {
        "selected_contact": contact,
        "add_contact_method_form": ContactMethodForm(
            deserialise_form_data(state.get("data", {})),
            auto_id="add_contact_method_%s",
        ),
        "active_tab": "details",
        "open_modal": "addContactMethodModal",
    }


def _restore_edit_contact_method_form(request, state):
    contact = _active_contact_from_form_state(request, state)
    if contact is None:
        return {}

    contact_method = contact_methods_for_contact(contact=contact).filter(
        pk=state.get("object_id"),
    ).first()
    if contact_method is None:
        return {}

    return {
        "selected_contact": contact,
        "edit_contact_method": contact_method,
        "edit_contact_method_form": ContactMethodForm(
            deserialise_form_data(state.get("data", {})),
            instance=contact_method,
            auto_id="edit_contact_method_%s",
        ),
        "active_tab": "details",
        "open_modal": "editContactMethodModal",
    }


def _restore_add_contact_note_form(request, state):
    contact = _active_contact_from_form_state(request, state)
    if contact is None:
        return {}

    return {
        "selected_contact": contact,
        "add_contact_note_form": NoteForm(
            deserialise_form_data(state.get("data", {})),
            auto_id="add_note_%s",
        ),
        "active_tab": "notes",
    }


def _restore_edit_contact_note_form(request, state):
    contact = _active_contact_from_form_state(request, state)
    if contact is None:
        return {}

    note = notes_for_contact(
        user=request.user,
        contact=contact,
    ).filter(pk=state.get("object_id")).first()
    if note is None:
        return {}

    return {
        "selected_contact": contact,
        "edit_contact_note": note,
        "edit_contact_note_form": NoteForm(
            deserialise_form_data(state.get("data", {})),
            instance=note,
            auto_id="edit_contact_note_%s",
        ),
        "active_tab": "notes",
    }


CONTACT_FORM_STATE_RESTORERS = {
    "add_contact": _restore_add_contact_form,
    "edit_contact": _restore_edit_contact_form,
    "add_contact_method": _restore_add_contact_method_form,
    "edit_contact_method": _restore_edit_contact_method_form,
    "add_contact_note": _restore_add_contact_note_form,
    "edit_contact_note": _restore_edit_contact_note_form,
}


def _restore_contact_form_context(request):
    state = pop_form_state(request)
    if not isinstance(state, dict):
        return {}

    restorer = CONTACT_FORM_STATE_RESTORERS.get(state.get("action"))
    if restorer is None:
        return {}

    return restorer(request, state)


def _normalised_list_values(request):
    search = request.GET.get("search", "").strip()
    state = request.GET.get("state", "")
    sort = request.GET.get("sort", "name")

    if state not in Contact.State.values:
        state = ""
    if sort not in CONTACT_SORT_OPTIONS:
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


def _contact_workspace_url(
    request,
    *,
    contact_id=None,
    tab="details",
    form_state=None,
):
    parameters = _list_query_parameters(_normalised_list_values(request))
    page = request.GET.get("page", "")
    if page.isdigit() and int(page) > 1:
        parameters["page"] = page
    if contact_id is not None:
        parameters["selected"] = contact_id
    if tab == "notes":
        parameters["tab"] = "notes"
    if form_state is not None:
        parameters["form_state"] = form_state

    url = reverse("contact:contacts")
    return f"{url}?{urlencode(parameters)}" if parameters else url


def _redirect_with_contact_form_state(
    request,
    *,
    action,
    contact_id=None,
    object_id=None,
    tab="details",
):
    state = {
        "action": action,
        "contact_id": contact_id,
        "object_id": object_id,
        "data": serialise_form_data(request.POST),
    }
    token = store_form_state(request, state)
    return redirect(
        _contact_workspace_url(
            request,
            contact_id=contact_id,
            tab=tab,
            form_state=token,
        )
    )


def _contact_list_context(
    request,
    *,
    selected_contact=None,
    add_contact_form=None,
    edit_contact_form=None,
    add_contact_method_form=None,
    edit_contact_method=None,
    edit_contact_method_form=None,
    active_tab=None,
    open_modal=None,
    add_contact_note_form=None,
    edit_contact_note=None,
    edit_contact_note_form=None,
):
    values = _normalised_list_values(request)
    contacts = filtered_contacts_for_user(user=request.user, **values)
    paginator = Paginator(contacts, CONTACTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))

    if selected_contact is None:
        try:
            selected_id = int(request.GET.get("selected", ""))
        except (TypeError, ValueError):
            selected_id = None
        selected_contact = next(
            (contact for contact in page_obj if contact.pk == selected_id),
            None,
        )

    if selected_contact is None and page_obj.object_list:
        selected_contact = page_obj.object_list[0]

    requested_tab = active_tab or request.GET.get("tab", "details")
    if requested_tab not in CONTACT_WORKSPACE_TABS:
        requested_tab = "details"

    contact_methods = []
    notes = []

    selected_contact_is_active = (
        selected_contact is not None
        and selected_contact.state == Contact.State.ACTIVE
    )

    if selected_contact is not None:

        if requested_tab == "details":
            contact_methods = list(selected_contact.contact_methods.all())

            if add_contact_method_form is None and selected_contact_is_active:
                add_contact_method_form = ContactMethodForm(auto_id="add_contact_method_%s")

            if (
                edit_contact_method is None
                and selected_contact.state == Contact.State.ACTIVE
            ):
                try:
                    edit_method_id = int(request.GET.get("edit_method", ""))
                except (TypeError, ValueError):
                    edit_method_id = None

                for method in contact_methods:
                    if method.pk == edit_method_id:
                        edit_contact_method = method
                        break

            if edit_contact_method_form is None and edit_contact_method is not None:
                edit_contact_method_form = ContactMethodForm(
                    instance=edit_contact_method,
                    auto_id="edit_contact_method_%s",
                )

            if edit_contact_method is not None and open_modal is None:
                open_modal = "editContactMethodModal"

        else:
            notes = list(notes_for_contact(user=request.user, contact=selected_contact))

            if add_contact_note_form is None and selected_contact_is_active:
                add_contact_note_form = NoteForm(auto_id="add_note_%s")

    list_parameters = _list_query_parameters(values)
    navigation_parameters = dict(list_parameters)
    if page_obj.number > 1:
        navigation_parameters["page"] = page_obj.number

    if add_contact_form is None:
        add_contact_form = ContactCreateForm(auto_id="add_contact_%s")

    if edit_contact_form is None and selected_contact_is_active:
        edit_contact_form = ContactForm(instance=selected_contact, auto_id="edit_contact_%s")

    return {
        "page_obj": page_obj,
        "selected_contact": selected_contact,
        "contact_methods": contact_methods,
        "notes": notes,
        "add_contact_form": add_contact_form,
        "edit_contact_form": edit_contact_form,
        "add_contact_method_form": add_contact_method_form,
        "edit_contact_method": edit_contact_method,
        "edit_contact_method_form": edit_contact_method_form,
        "add_contact_note_form": add_contact_note_form,
        "edit_contact_note": edit_contact_note,
        "edit_contact_note_form": edit_contact_note_form,
        "active_tab": requested_tab,
        "open_modal": open_modal,
        "search": values["search"],
        "state": values["state"],
        "sort": values["sort"],
        "list_query": urlencode(list_parameters),
        "navigation_query": urlencode(navigation_parameters),
        "has_filters": bool(values["search"] or values["state"]),
        "contact_count": contacts_for_user(user=request.user).count(),
        "show_mobile_detail": bool(request.GET.get("selected"))
        or open_modal in (
            "editContactModal",
            "addContactMethodModal",
            "editContactMethodModal",
        ),
    }


@login_required
@require_GET
def contacts_view(request):
    context_overrides = _restore_contact_form_context(request)
    return render(
        request,
        "contact/contacts.html",
        _contact_list_context(request, **context_overrides),
    )


@login_required
@require_POST
def add_contact_view(request):
    form = ContactCreateForm(request.POST, auto_id="add_contact_%s")
    if form.is_valid():
        contact = create_contact(user=request.user, **form.cleaned_data)
        return redirect(_contact_workspace_url(request, contact_id=contact.pk))

    return _redirect_with_contact_form_state(
        request,
        action="add_contact",
    )


@login_required
@require_POST
def edit_contact_view(request, contact_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )
    form = ContactForm(
        request.POST,
        instance=contact,
        auto_id="edit_contact_%s",
    )
    if form.is_valid():
        update_contact(contact=contact, **form.cleaned_data)
        return redirect(_contact_workspace_url(request, contact_id=contact.pk))

    return _redirect_with_contact_form_state(
        request,
        action="edit_contact",
        contact_id=contact.pk,
    )


@login_required
@require_POST
def deactivate_contact_view(request, contact_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )
    deactivate_contact(contact=contact)
    return redirect(_contact_workspace_url(request, contact_id=contact.pk))


@login_required
@require_POST
def reactivate_contact_view(request, contact_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.DEACTIVATED,
    )
    reactivate_contact(contact=contact)
    return redirect(_contact_workspace_url(request, contact_id=contact.pk))


@login_required
@require_POST
def delete_contact_view(request, contact_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
    )
    delete_contact(contact=contact)
    return redirect(_contact_workspace_url(request))


@login_required
@require_POST
def add_contact_method_view(request, contact_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )
    form = ContactMethodForm(
        request.POST,
        auto_id="add_contact_method_%s",
    )
    if form.is_valid():
        create_contact_method(contact=contact, **form.cleaned_data)
        return redirect(_contact_workspace_url(request, contact_id=contact.pk))

    return _redirect_with_contact_form_state(
        request,
        action="add_contact_method",
        contact_id=contact.pk,
    )


@login_required
@require_POST
def edit_contact_method_view(request, contact_id, method_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )
    contact_method = get_object_or_404(
        contact_methods_for_contact(contact=contact),
        pk=method_id,
    )
    form = ContactMethodForm(
        request.POST,
        instance=contact_method,
        auto_id="edit_contact_method_%s",
    )
    if form.is_valid():
        update_contact_method(
            contact_method=contact_method,
            **form.cleaned_data,
        )
        return redirect(_contact_workspace_url(request, contact_id=contact.pk))

    return _redirect_with_contact_form_state(
        request,
        action="edit_contact_method",
        contact_id=contact.pk,
        object_id=contact_method.pk,
    )


@login_required
@require_POST
def delete_contact_method_view(request, contact_id, method_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )
    contact_method = get_object_or_404(
        contact_methods_for_contact(contact=contact),
        pk=method_id,
    )
    delete_contact_method(contact_method=contact_method)
    return redirect(_contact_workspace_url(request, contact_id=contact.pk))


@login_required
@require_POST
def add_contact_note_view(request, contact_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )

    form = NoteForm(
        request.POST,
        auto_id="add_note_%s",
    )
    if form.is_valid():
        create_note(user=request.user, contact=contact, **form.cleaned_data)
        return redirect(_contact_workspace_url(request, contact_id=contact.pk, tab="notes"))

    return _redirect_with_contact_form_state(
        request,
        action="add_contact_note",
        contact_id=contact.pk,
        tab="notes",
    )

@login_required
@require_POST
def edit_contact_note_view(request, contact_id, note_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )

    note = get_object_or_404(
        notes_for_contact(user=request.user,
                          contact=contact).filter(pk=note_id))

    form = NoteForm(
        request.POST,
        instance=note,
        auto_id="edit_contact_note_%s",
    )
    if form.is_valid():
        update_note(
            note=note,
            **form.cleaned_data,
        )
        return redirect(_contact_workspace_url(request, contact_id=contact.pk, tab="notes"))

    return _redirect_with_contact_form_state(
        request,
        action="edit_contact_note",
        contact_id=contact.pk,
        object_id=note.pk,
        tab="notes",
    )


@login_required
@require_POST
def delete_contact_note_view(request, contact_id, note_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )
    note = get_object_or_404(
        notes_for_contact(user=request.user, contact=contact),
        pk=note_id,
    )
    delete_note(note=note)
    return redirect(_contact_workspace_url(request, contact_id=contact.pk, tab="notes"))
