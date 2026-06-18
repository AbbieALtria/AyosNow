from django.contrib import admin

from .models import Barangay, City, Region

admin.site.register(Region)
admin.site.register(City)
admin.site.register(Barangay)
