from django.contrib import admin
from .models import Dataset, Annotation, FailureMode

admin.site.register(Dataset)
admin.site.register(Annotation)
admin.site.register(FailureMode)
