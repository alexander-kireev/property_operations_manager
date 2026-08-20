from django.urls import path
from . import views


app_name = "pages"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("about/", views.about_us_view, name="about_us"),
    path("contact/", views.contact_us_view, name="contact_us"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
]