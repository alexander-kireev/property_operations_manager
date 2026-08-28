from django.urls import path
from . import views

app_name = "task"

urlpatterns = [
    path("", views.tasks_view, name="tasks"),
    path("add/", views.add_task_view, name="add_task"),
    path("<int:task_id>/", views.task_detail_view, name="task_detail"),
    path("<int:task_id>/edit/", views.edit_task_view, name="edit_task"),
    path("<int:task_id>/dismiss/", views.dismiss_task_view, name="dismiss_task"),
    path("<int:task_id>/complete/", views.complete_task_view, name="complete_task"),
    path("<int:task_id>/reactivate/", views.reactivate_task_view, name="reactivate_task"),
    path("<int:task_id>/delete/", views.delete_task_view, name="delete_task"),
]