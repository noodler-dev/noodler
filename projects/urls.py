from django.urls import path
from . import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list, name="list"),
    path("new/", views.project_create, name="create"),
    path("<uuid:project_uid>/", views.project_detail, name="detail"),
    path("<uuid:project_uid>/edit/", views.project_edit, name="edit"),
    path("<uuid:project_uid>/delete/", views.project_delete, name="delete"),
    path("<uuid:project_uid>/switch/", views.project_switch, name="switch"),
    path("<uuid:project_uid>/keys/create/", views.api_key_create, name="key_create"),
    path(
        "<uuid:project_uid>/keys/<uuid:key_uid>/created/",
        views.api_key_created,
        name="key_created",
    ),
    path(
        "<uuid:project_uid>/keys/<uuid:key_uid>/revoke/",
        views.api_key_revoke,
        name="key_revoke",
    ),
]
