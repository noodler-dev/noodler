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
    path(
        "<uuid:dataset_uid>/categorize/",
        views.categorize_dataset,
        name="categorize",
    ),
    path(
        "<uuid:dataset_uid>/categories/",
        views.category_list,
        name="categories",
    ),
    path(
        "<uuid:dataset_uid>/categories/new/",
        views.category_create,
        name="category_create",
    ),
    path(
        "<uuid:dataset_uid>/categories/<uuid:category_uid>/edit/",
        views.category_edit,
        name="category_edit",
    ),
    path(
        "<uuid:dataset_uid>/categories/<uuid:category_uid>/delete/",
        views.category_delete,
        name="category_delete",
    ),
]
