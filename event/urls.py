from django.urls import path
from . import views

app_name = "event"

urlpatterns = [
    path("", views.events_view, name="events"),
    path("add/", views.add_event_view, name="add_event"),
    path("<int:event_id>/edit/", views.edit_event_view, name="edit_event"),
    path("<int:event_id>/delete/", views.delete_event_view, name="delete_event"),
    path("<int:event_id>/mark_occurred/", views.mark_event_occurred_view , name="mark_event_occurred"),
    path("<int:event_id>/cancel/", views.cancel_event_view , name="cancel_event"),
    path("<int:event_id>/reactivate/", views.reactivate_event_view , name="reactivate_event"),
    path("<int:event_id>/contacts/add/", views.add_event_contacts_to_event_view, name="add_event_contacts_to_event"),
    path("<int:event_id>/contacts/<int:event_contact_id>/remove/", views.delete_event_contact_from_event_view, name="delete_event_contact_from_event"),
]
