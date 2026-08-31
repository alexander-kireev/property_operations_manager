from django.urls import path
from . import views

app_name = "issue"

urlpatterns = [
    path("", views.issues_view, name="issues"),
    path("add/", views.add_issue_view, name="add_issue"),
    path("<int:issue_id>/edit/", views.edit_issue_view, name="edit_issue"),
    path("<int:issue_id>/resolve/", views.resolve_issue_view, name="resolve_issue"),
    path("<int:issue_id>/dismiss/", views.dismiss_issue_view, name="dismiss_issue"),
    path("<int:issue_id>/reactivate/", views.reactivate_issue_view, name="reactivate_issue"),
    path("<int:issue_id>/delete/", views.delete_issue_view, name="delete_issue"),
    path("<int:issue_id>/tasks/add/", views.add_issue_task_view, name="add_issue_task"),
    path("<int:issue_id>/tasks/<int:task_id>/edit/", views.edit_issue_task_view, name="edit_issue_task"),
]
