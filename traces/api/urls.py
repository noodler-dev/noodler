from django.urls import path
from . import views

urlpatterns = [
    path("hello/", views.hello_world, name="hello-world"),
    path("ingest/", views.ingest_trace, name="ingest-trace"),
]
