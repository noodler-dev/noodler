from django.contrib import admin
from .models import Trace, Observation, Generation

admin.site.register(Trace)
admin.site.register(Observation)
admin.site.register(Generation)
