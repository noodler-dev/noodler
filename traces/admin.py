from django.contrib import admin
from .models import Trace, Span

admin.site.register(Trace)
admin.site.register(Span)