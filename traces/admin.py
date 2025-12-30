from django.contrib import admin
from .models import RawTrace, Trace, Span

admin.site.register(RawTrace)
admin.site.register(Trace)
admin.site.register(Span)
