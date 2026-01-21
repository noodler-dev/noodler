from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    # Organization URLs
    path("organizations/", views.organization_list, name="organization_list"),
    path("organizations/new/", views.organization_create, name="organization_create"),
    path(
        "organizations/<int:org_id>/",
        views.organization_detail,
        name="organization_detail",
    ),
    path(
        "organizations/<int:org_id>/edit/",
        views.organization_edit,
        name="organization_edit",
    ),
    path(
        "organizations/<int:org_id>/delete/",
        views.organization_delete,
        name="organization_delete",
    ),
]
