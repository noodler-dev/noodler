from django.urls import path
from . import views

urlpatterns = [
    path("", views.TraceListView.as_view(), name="trace-list"),
]
