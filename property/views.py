from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

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


def _property_list_context(request, *, add_property_form=None):
    search = request.GET.get("search", "").strip()
    state = request.GET.get("state", "")
    sort = request.GET.get("sort", "name")

    if state not in Property.State.values:
        state = ""

    if sort not in PROPERTY_SORT_OPTIONS:
        sort = "name"

    properties = filtered_properties_for_user(
        user=request.user,
        search=search,
        state=state,
        sort=sort,
    )

    paginator = Paginator(properties, PROPERTIES_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_parameters = {}

    if search:
        query_parameters["search"] = search

    if state:
        query_parameters["state"] = state

    if sort != "name":
        query_parameters["sort"] = sort

    return {
        "add_property_form": (
            add_property_form
            if add_property_form is not None
            else PropertyForm(user=request.user)
        ),
        "page_obj": page_obj,
        "search": search,
        "state": state,
        "sort": sort,
        "list_query": urlencode(query_parameters),
        "has_filters": bool(search or state),
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
    return render(
        request,
        "property/properties.html",
        _property_list_context(request),
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

    return render(
        request,
        "property/properties.html",
        _property_list_context(request, add_property_form=form),
    )


@login_required
@require_GET
def property_detail_view(request, property_id):
    property_record = get_object_or_404(
        properties_for_user(user=request.user),
        pk=property_id,
    )

    return render(
        request,
        "property/property_detail.html",
        _property_detail_context(request, property_record),
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

    return render(
        request,
        "property/property_detail.html",
        _property_detail_context(
            request,
            property_record,
            edit_property_form=form,
        ),
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
