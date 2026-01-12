from django.urls import path
from . import views

app_name = "traces"

urlpatterns = [
    path("", views.trace_list, name="list"),
    path("clear-filter/", views.trace_list_clear_filter, name="clear_filter"),
    path("<int:trace_id>/", views.trace_detail, name="detail"),
]
