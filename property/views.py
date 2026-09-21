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

from .forms import PropertyForm
from .models import Property
from .selectors import (
    PROPERTY_SORT_OPTIONS,
    filtered_properties_for_user,
    properties_for_user,
)
from .services import (
    create_property,
    deactivate_property,
    delete_property,
    reactivate_property,
    update_property,
)


PROPERTIES_PER_PAGE = 20


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
    if property_record is not None:
        return redirect(_property_detail_url(property_record, form_state=token))
    return redirect(_property_list_url(request, form_state=token))


def _restore_add_property_form(request, state):
    return PropertyForm(
        deserialise_form_data(state.get("data", {})),
        user=request.user,
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
    )


def _property_list_context(request, *, add_property_form=None):
    values = _normalised_list_values(request)
    properties = filtered_properties_for_user(
        user=request.user,
        **{**values, "state": values["state"] or Property.State.ACTIVE},
    )

    paginator = Paginator(properties, PROPERTIES_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_parameters = _list_query_parameters(values)

    return {
        "add_property_form": (
            add_property_form
            if add_property_form is not None
            else PropertyForm(user=request.user)
        ),
        "page_obj": page_obj,
        "search": values["search"],
        "state": values["state"],
        "sort": values["sort"],
        "list_query": urlencode(query_parameters),
        "has_filters": bool(values["search"] or values["state"]),
        "property_count": properties_for_user(user=request.user).count(),
    }


def _property_detail_context(request, property_record, *, edit_property_form=None):
    return {
        "property": property_record,
        "edit_property_form": (
            edit_property_form
            if edit_property_form is not None
            else PropertyForm(user=request.user, instance=property_record)
        ),
    }


@login_required
@require_GET
def properties_view(request):
    add_property_form = None
    state = pop_form_state(request)
    if isinstance(state, dict) and state.get("action") == "add_property":
        add_property_form = _restore_add_property_form(request, state)

    return render(
        request,
        "property/properties.html",
        _property_list_context(request, add_property_form=add_property_form),
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

    return redirect("property:property_detail", property_id=property_record.pk)


@login_required
@require_POST
def delete_property_view(request, property_id):
    property_record = get_object_or_404(
        properties_for_user(user=request.user),
        pk=property_id,
    )
    delete_property(property_record=property_record)

    return redirect("property:properties")
