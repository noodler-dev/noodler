from django.urls import path
from . import views

urlpatterns = [
    path("ingest/", views.ingest_trace, name="ingest-trace"),
]
