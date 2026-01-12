import hashlib
import secrets
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from accounts.models import Organization
from .models import Project, ApiKey


def get_user_organizations(user):
    """Get all organizations the user belongs to."""
    try:
        user_profile = user.userprofile
        return Organization.objects.filter(
            membership__user_profile=user_profile
        ).distinct()
    except AttributeError:
        return Organization.objects.none()


def get_user_projects(user):
    """Get all projects the user has access to (via their organizations)."""
    orgs = get_user_organizations(user)
    return Project.objects.filter(organization__in=orgs)


@login_required
def project_list(request):
    """List all projects the user has access to."""
    projects = get_user_projects(request.user)
    current_project_id = request.session.get("current_project_id")

    context = {
        "projects": projects,
        "current_project_id": current_project_id,
    }
    return render(request, "projects/list.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def project_create(request):
    """Create a new project."""
    user_orgs = get_user_organizations(request.user)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        organization_id = request.POST.get("organization")

        if not name:
            messages.error(request, "Project name is required.")
            return render(request, "projects/new.html", {"organizations": user_orgs})

        # Validate organization access
        try:
            org = user_orgs.get(id=organization_id)
        except Organization.DoesNotExist:
            messages.error(request, "Invalid organization selected.")
            return render(request, "projects/new.html", {"organizations": user_orgs})

        project = Project.objects.create(name=name, organization=org)
        messages.success(request, f'Project "{project.name}" created successfully.')
        return redirect("projects:detail", project_id=project.id)

    context = {
        "organizations": user_orgs,
    }
    return render(request, "projects/new.html", context)


@login_required
def project_detail(request, project_id):
    """View project details and manage API keys."""
    project = get_object_or_404(Project, id=project_id)

    # Check access
    user_orgs = get_user_organizations(request.user)
    if project.organization not in user_orgs:
        messages.error(request, "You do not have access to this project.")
        return redirect("projects:list")

    # Get active API keys (not revoked)
    api_keys = ApiKey.objects.filter(project=project, revoked_at__isnull=True).order_by(
        "-created_at"
    )

    context = {
        "project": project,
        "api_keys": api_keys,
        "is_current_project": request.session.get("current_project_id") == project.id,
    }
    return render(request, "projects/detail.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def project_edit(request, project_id):
    """Edit a project."""
    project = get_object_or_404(Project, id=project_id)

    # Check access
    user_orgs = get_user_organizations(request.user)
    if project.organization not in user_orgs:
        messages.error(request, "You do not have access to this project.")
        return redirect("projects:list")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        if not name:
            messages.error(request, "Project name is required.")
            return render(request, "projects/edit.html", {"project": project})

        project.name = name
        project.save()
        messages.success(request, f'Project "{project.name}" updated successfully.')
        return redirect("projects:detail", project_id=project.id)

    context = {
        "project": project,
    }
    return render(request, "projects/edit.html", context)


@login_required
@require_POST
def project_delete(request, project_id):
    """Delete a project (POST-only)."""
    project = get_object_or_404(Project, id=project_id)

    # Check access
    user_orgs = get_user_organizations(request.user)
    if project.organization not in user_orgs:
        messages.error(request, "You do not have access to this project.")
        return redirect("projects:list")

    project_name = project.name
    project.delete()
    messages.success(request, f'Project "{project_name}" deleted successfully.')

    # Clear current project if it was deleted
    if request.session.get("current_project_id") == project_id:
        del request.session["current_project_id"]

    return redirect("projects:list")


@login_required
@require_http_methods(["GET", "POST"])
def api_key_create(request, project_id):
    """Create an API key for a project."""
    project = get_object_or_404(Project, id=project_id)

    # Check access
    user_orgs = get_user_organizations(request.user)
    if project.organization not in user_orgs:
        messages.error(request, "You do not have access to this project.")
        return redirect("projects:list")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        if not name:
            messages.error(request, "API key name is required.")
            return redirect("projects:detail", project_id=project.id)

        # Generate random key
        raw_key = secrets.token_urlsafe(32)
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()

        api_key = ApiKey.objects.create(
            name=name, project=project, hashed_key=hashed_key
        )

        # Store raw key in session temporarily to show once
        request.session[f"api_key_{api_key.id}"] = raw_key

        return redirect(
            "projects:key_created", project_id=project.id, key_id=api_key.id
        )

    return redirect("projects:detail", project_id=project.id)


@login_required
def api_key_created(request, project_id, key_id):
    """Show the newly created API key (raw key shown once)."""
    project = get_object_or_404(Project, id=project_id)
    api_key = get_object_or_404(ApiKey, id=key_id, project=project)

    # Check access
    user_orgs = get_user_organizations(request.user)
    if project.organization not in user_orgs:
        messages.error(request, "You do not have access to this project.")
        return redirect("projects:list")

    # Get raw key from session (one-time display)
    session_key = f"api_key_{key_id}"
    raw_key = request.session.get(session_key)

    if raw_key:
        # Remove from session after displaying
        del request.session[session_key]
    else:
        # Key was already shown, redirect to detail
        messages.info(
            request, "This API key was already displayed. It cannot be shown again."
        )
        return redirect("projects:detail", project_id=project.id)

    context = {
        "project": project,
        "api_key": api_key,
        "raw_key": raw_key,
    }
    return render(request, "projects/key_created.html", context)


@login_required
@require_POST
def api_key_revoke(request, project_id, key_id):
    """Revoke an API key (sets revoked_at, does not hard-delete)."""
    project = get_object_or_404(Project, id=project_id)
    api_key = get_object_or_404(ApiKey, id=key_id, project=project)

    # Check access
    user_orgs = get_user_organizations(request.user)
    if project.organization not in user_orgs:
        messages.error(request, "You do not have access to this project.")
        return redirect("projects:list")

    from django.utils import timezone

    api_key.revoked_at = timezone.now()
    api_key.save()

    messages.success(request, f'API key "{api_key.name}" has been revoked.')
    return redirect("projects:detail", project_id=project.id)


@login_required
@require_POST
def project_switch(request, project_id):
    """Switch the current project (stored in session)."""
    project = get_object_or_404(Project, id=project_id)

    # Validate access (must be in same org)
    user_orgs = get_user_organizations(request.user)
    if project.organization not in user_orgs:
        messages.error(request, "You do not have access to this project.")
        return redirect("projects:list")

    request.session["current_project_id"] = project.id
    messages.success(request, f'Switched to project "{project.name}".')
    return redirect("projects:detail", project_id=project.id)
