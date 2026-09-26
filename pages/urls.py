from django.urls import path
from . import views


app_name = "pages"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("about/", views.about_us_view, name="about_us"),
    path("contact/", views.contact_us_view, name="contact_us"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("dashboard/data/", views.dashboard_data_view, name="dashboard_data"),
    path("dashboard/action/", views.dashboard_action_view, name="dashboard_action"),
]
