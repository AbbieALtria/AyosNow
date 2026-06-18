from django.shortcuts import render


def app(request):
    return render(request, "customer_portal/app.html")
