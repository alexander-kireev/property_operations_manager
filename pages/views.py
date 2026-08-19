from django.shortcuts import render


def home_view(request):
    return render(request, "pages/home.html")

def about_us_view(request):
    return render(request, "pages/about_us.html")

def contact_us_view(request):
    return render(request, "pages/contact_us.html")

