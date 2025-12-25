from django.urls import path
from .views import ingest_spans

urlpatterns = [
    path("spans/", ingest_spans, name="ingest_spans"),
]
