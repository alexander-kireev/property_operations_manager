from django.urls import path
from . import views


app_name = "property"

urlpatterns = [
    path("", views.properties_view, name="properties"),
    path("add/", views.add_property_view, name="add_property"),
    path("<int:property_id>/", views.property_detail_view, name="property_detail"),
    path("<int:property_id>/edit/", views.edit_property_view, name="edit_property"),
    path(
        "<int:property_id>/deactivate/",
        views.deactivate_property_view,
        name="deactivate_property",
    ),
    path(
        "<int:property_id>/reactivate/",
        views.reactivate_property_view,
        name="reactivate_property",
    ),
    path(
        "<int:property_id>/delete/",
        views.delete_property_view,
        name="delete_property",
    ),
]
