from django.shortcuts import render


def app(request):
    return render(request, "provider_portal/app.html")
