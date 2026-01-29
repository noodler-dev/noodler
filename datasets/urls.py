from django.urls import path
from . import views

app_name = "datasets"

urlpatterns = [
    path("", views.dataset_list, name="list"),
    path("new/", views.dataset_create, name="create"),
    path("<uuid:dataset_uid>/", views.dataset_detail, name="detail"),
    path("<uuid:dataset_uid>/delete/", views.dataset_delete, name="delete"),
    path(
        "<uuid:dataset_uid>/annotate/<uuid:trace_uid>/",
        views.annotation_view,
        name="annotate",
    ),
]
