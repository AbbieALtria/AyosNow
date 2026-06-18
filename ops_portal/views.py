from django.shortcuts import render


def app(request):
    return render(request, "ops_portal/app.html")
