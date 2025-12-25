from django.contrib import admin
from .models import Organization, UserProfile, Membership

admin.site.register(Organization)
admin.site.register(UserProfile)
admin.site.register(Membership)
