from django.urls import path
from . import views

app_name = "traces"

urlpatterns = [
    path("", views.trace_list, name="list"),
    path("<uuid:trace_uid>/", views.trace_detail, name="detail"),
]
