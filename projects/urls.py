from django.urls import path
from . import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list, name="list"),
    path("new/", views.project_create, name="create"),
    path("<int:project_id>/", views.project_detail, name="detail"),
    path("<int:project_id>/edit/", views.project_edit, name="edit"),
    path("<int:project_id>/delete/", views.project_delete, name="delete"),
    path("<int:project_id>/switch/", views.project_switch, name="switch"),
    path("<int:project_id>/keys/create/", views.api_key_create, name="key_create"),
    path(
        "<int:project_id>/keys/<int:key_id>/created/",
        views.api_key_created,
        name="key_created",
    ),
    path(
        "<int:project_id>/keys/<int:key_id>/revoke/",
        views.api_key_revoke,
        name="key_revoke",
    ),
]
