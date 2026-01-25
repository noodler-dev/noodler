import hashlib
import secrets
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from accounts.models import Organization
from .models import Project, ApiKey
from .decorators import require_project_access
from .utils import get_user_organizations, get_user_projects


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

        if not organization_id:
            messages.error(request, "Organization is required.")
            return render(request, "projects/new.html", {"organizations": user_orgs})

        # Validate organization access
        try:
            org = user_orgs.get(id=organization_id)
        except (Organization.DoesNotExist, ValueError):
            messages.error(request, "Invalid organization selected.")
            return render(request, "projects/new.html", {"organizations": user_orgs})

        project = Project.objects.create(name=name, organization=org)
        messages.success(request, f'Project "{project.name}" created successfully.')
        return redirect("projects:detail", project_uid=project.uid)

    context = {
        "organizations": user_orgs,
    }
    return render(request, "projects/new.html", context)


@login_required
@require_project_access(project_id_param="project_uid")
def project_detail(request, project_uid):
    """View project details and manage API keys."""
    # Get active API keys (not revoked)
    api_keys = ApiKey.objects.filter(
        project=request.current_project, revoked_at__isnull=True
    ).order_by("-created_at")

    context = {
        "project": request.current_project,
        "api_keys": api_keys,
        "is_current_project": request.session.get("current_project_id")
        == request.current_project.id,
    }
    return render(request, "projects/detail.html", context)


@login_required
@require_project_access(project_id_param="project_uid")
@require_http_methods(["GET", "POST"])
def project_edit(request, project_uid):
    """Edit a project."""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        if not name:
            messages.error(request, "Project name is required.")
            return render(
                request, "projects/edit.html", {"project": request.current_project}
            )

        request.current_project.name = name
        request.current_project.save()
        messages.success(
            request, f'Project "{request.current_project.name}" updated successfully.'
        )
        return redirect("projects:detail", project_uid=request.current_project.uid)

    context = {
        "project": request.current_project,
    }
    return render(request, "projects/edit.html", context)


@login_required
@require_project_access(project_id_param="project_uid")
@require_POST
def project_delete(request, project_uid):
    """Delete a project (POST-only)."""
    project_name = request.current_project.name
    request.current_project.delete()

    # Clear current project if it was deleted (check original value before auto-update)
    # Use original_current_project_id which was set before the decorator auto-updated the session
    # This prevents clearing the session when deleting a different project than the current one
    original_current_project_id = getattr(request, "original_current_project_id", None)
    if original_current_project_id == request.current_project.id:
        # The deleted project was the original current project, clear it
        del request.session["current_project_id"]
    elif original_current_project_id and original_current_project_id != request.current_project.id:
        # The deleted project was different from the original current project
        # Restore the original current project (auto-update changed it)
        request.session["current_project_id"] = original_current_project_id

    messages.success(request, f'Project "{project_name}" deleted successfully.')

    return redirect("projects:list")


@login_required
@require_project_access(project_id_param="project_uid")
@require_http_methods(["GET", "POST"])
def api_key_create(request, project_uid):
    """Create an API key for a project."""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        if not name:
            messages.error(request, "API key name is required.")
            return redirect("projects:detail", project_uid=request.current_project.uid)

        # Generate random key
        raw_key = secrets.token_urlsafe(32)
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()

        api_key = ApiKey.objects.create(
            name=name, project=request.current_project, hashed_key=hashed_key
        )

        # Store raw key in session temporarily to show once
        request.session[f"api_key_{api_key.id}"] = raw_key

        return redirect(
            "projects:key_created",
            project_uid=request.current_project.uid,
            key_uid=api_key.uid,
        )

    return redirect("projects:detail", project_uid=request.current_project.uid)


@login_required
@require_project_access(project_id_param="project_uid")
def api_key_created(request, project_uid, key_uid):
    """Show the newly created API key (raw key shown once)."""
    api_key = get_object_or_404(ApiKey, uid=key_uid, project=request.current_project)

    # Get raw key from session (one-time display)
    session_key = f"api_key_{api_key.id}"
    raw_key = request.session.get(session_key)

    if raw_key:
        # Remove from session after displaying
        del request.session[session_key]
    else:
        # Key was already shown, redirect to detail
        messages.info(
            request, "This API key was already displayed. It cannot be shown again."
        )
        return redirect("projects:detail", project_uid=request.current_project.uid)

    context = {
        "project": request.current_project,
        "api_key": api_key,
        "raw_key": raw_key,
    }
    return render(request, "projects/key_created.html", context)


@login_required
@require_project_access(project_id_param="project_uid")
@require_POST
def api_key_revoke(request, project_uid, key_uid):
    """Revoke an API key (sets revoked_at, does not hard-delete)."""
    api_key = get_object_or_404(ApiKey, uid=key_uid, project=request.current_project)

    from django.utils import timezone

    api_key.revoked_at = timezone.now()
    api_key.save()

    messages.success(request, f'API key "{api_key.name}" has been revoked.')
    return redirect("projects:detail", project_uid=request.current_project.uid)


@login_required
@require_project_access(project_id_param="project_uid")
@require_POST
def project_switch(request, project_uid):
    """Switch the current project (stored in session)."""
    request.session["current_project_id"] = request.current_project.id
    messages.success(request, f'Switched to project "{request.current_project.name}".')

    # Support redirect to a different page via 'next' parameter
    # Validate the URL to prevent open redirect vulnerabilities
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
        return redirect(next_url)

    return redirect("projects:detail", project_uid=request.current_project.uid)
