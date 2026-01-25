from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.db import transaction
from django.views.decorators.http import require_POST, require_http_methods
from django.utils.http import url_has_allowed_host_and_scheme
from .models import UserProfile, Organization, Membership
from .utils import get_user_organizations, is_organization_admin
from .decorators import require_organization_access


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                # Create UserProfile for the new user
                UserProfile.objects.create(user=user)
            messages.success(request, "Account created successfully! Please log in.")
            return redirect("accounts:login")
    else:
        form = UserCreationForm()

    return render(request, "accounts/signup.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("/")

    # Get the 'next' parameter from query string or POST data
    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                # Validate and redirect to 'next' URL if provided and safe, otherwise use LOGIN_REDIRECT_URL
                if next_url and url_has_allowed_host_and_scheme(
                    next_url, allowed_hosts=None
                ):
                    redirect_url = next_url
                else:
                    redirect_url = settings.LOGIN_REDIRECT_URL
                return redirect(redirect_url)
    else:
        form = AuthenticationForm()

    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect(settings.LOGOUT_REDIRECT_URL)


@login_required
def organization_list(request):
    """List all organizations the user belongs to."""
    organizations = get_user_organizations(request.user)

    context = {
        "organizations": organizations,
    }
    return render(request, "accounts/organization_list.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def organization_create(request):
    """Create a new organization."""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        if not name:
            messages.error(request, "Organization name is required.")
            return render(request, "accounts/organization_new.html")

        # Create organization and membership in a transaction
        with transaction.atomic():
            organization = Organization.objects.create(name=name)
            # Create admin membership for the creator
            user_profile = request.user.userprofile
            Membership.objects.create(
                user_profile=user_profile,
                organization=organization,
                role="admin",
            )

        messages.success(
            request, f'Organization "{organization.name}" created successfully.'
        )
        return redirect("accounts:organization_detail", org_uid=organization.uid)

    return render(request, "accounts/organization_new.html")


@login_required
@require_organization_access(org_id_param="org_uid")
def organization_detail(request, org_uid):
    """View organization details and list projects."""
    organization = request.current_organization
    is_admin = is_organization_admin(request.user, organization)

    # Get projects for this organization
    from projects.models import Project

    projects = Project.objects.filter(organization=organization).order_by("-created_at")

    context = {
        "organization": organization,
        "projects": projects,
        "is_admin": is_admin,
    }
    return render(request, "accounts/organization_detail.html", context)


@login_required
@require_organization_access(org_id_param="org_uid", require_admin=True)
@require_http_methods(["GET", "POST"])
def organization_edit(request, org_uid):
    """Edit an organization (admin only)."""
    organization = request.current_organization

    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        if not name:
            messages.error(request, "Organization name is required.")
            return render(
                request,
                "accounts/organization_edit.html",
                {"organization": organization},
            )

        organization.name = name
        organization.save()
        messages.success(
            request,
            f'Organization "{organization.name}" updated successfully.',
        )
        return redirect("accounts:organization_detail", org_uid=organization.uid)

    context = {
        "organization": organization,
    }
    return render(request, "accounts/organization_edit.html", context)


@login_required
@require_organization_access(org_id_param="org_uid", require_admin=True)
@require_POST
def organization_delete(request, org_uid):
    """Delete an organization (admin only)."""
    organization = request.current_organization
    organization_name = organization.name

    # Check if organization has projects within a transaction with row lock
    # to prevent race condition where a project could be created between
    # the check and the delete
    from projects.models import Project

    with transaction.atomic():
        # Lock the organization row to prevent concurrent modifications
        locked_org = Organization.objects.select_for_update().get(id=organization.id)
        project_count = Project.objects.filter(organization=locked_org).count()
        if project_count > 0:
            messages.error(
                request,
                f'Cannot delete organization "{organization_name}" because it has {project_count} project(s). Please delete or move the projects first.',
            )
            return redirect("accounts:organization_detail", org_uid=organization.uid)

        # Delete within the same transaction
        locked_org.delete()

    messages.success(
        request, f'Organization "{organization_name}" deleted successfully.'
    )
    return redirect("accounts:organization_list")
