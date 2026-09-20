from django.urls import path
from . import views

app_name = "contact"

urlpatterns = [
    path("", views.contacts_view, name="contacts"),
    path("add/", views.add_contact_view, name="add_contact"),
    path("<int:contact_id>/edit/", views.edit_contact_view, name="edit_contact"),
    path(
        "<int:contact_id>/deactivate/",
        views.deactivate_contact_view,
        name="deactivate_contact",
    ),
    path(
        "<int:contact_id>/reactivate/",
        views.reactivate_contact_view,
        name="reactivate_contact",
    ),
    path(
        "<int:contact_id>/delete/",
        views.delete_contact_view,
        name="delete_contact",
    ),
    path(
        "<int:contact_id>/methods/add/",
        views.add_contact_method_view,
        name="add_contact_method",
    ),
    path(
        "<int:contact_id>/methods/<int:method_id>/edit/",
        views.edit_contact_method_view,
        name="edit_contact_method",
    ),
    path(
        "<int:contact_id>/methods/<int:method_id>/delete/",
        views.delete_contact_method_view,
        name="delete_contact_method",
    ),
    path(
        "<int:contact_id>/add_note/",
        views.add_contact_note_view,
        name="add_contact_note",
    ),
    path(
        "<int:contact_id>/notes/<int:note_id>/edit/",
        views.edit_contact_note_view,
        name="edit_contact_note",
    ),
    path(
        "<int:contact_id>/notes/<int:note_id>/delete/",
        views.delete_contact_note_view,
        name="delete_contact_note",
    ),
]
