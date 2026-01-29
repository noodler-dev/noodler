from django.contrib import admin
from .models import Dataset, Annotation

admin.site.register(Dataset)
admin.site.register(Annotation)
