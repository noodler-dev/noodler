from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from .utils import (
    get_user_projects,
    get_current_project,
    set_current_project,
    get_or_auto_select_project,
)
from .models import Project


def require_project_access(
    require_current_project=False,
    project_id_param="project_id",
    check_both=False,
    auto_select=True,
    auto_update=True,
):
    """
    Decorator to require project-level access for a view.

    Args:
        require_current_project: If True, requires current_project_id in session
        project_id_param: Name of URL parameter containing project ID (default: 'project_id')
        check_both: If True, validates both URL project_id and session current_project match
        auto_select: If True, automatically select first project if none is set (default: True)
        auto_update: If True, automatically update current project when visiting project links (default: True)

    Usage:
        @login_required
        @require_project_access(require_current_project=True)
        def trace_list(request):
            # request.current_project is already set and validated
            ...

        @login_required
        @require_project_access(project_id_param='project_id')
        def project_detail(request, project_id):
            # request.current_project is already set and validated
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user_projects = get_user_projects(request.user)
            project = None
            project_id = None

            # Get project_id from URL parameters if specified
            if project_id_param in kwargs:
                project_id = kwargs[project_id_param]
                try:
                    project = user_projects.get(id=project_id)
                except Project.DoesNotExist:
                    messages.error(request, "You do not have access to this project.")
                    return redirect("projects:list")

            # Auto-update: If we have a project from URL and auto_update is enabled,
            # update the current project in session
            if auto_update and project_id and project:
                current_project = get_current_project(request.user, request.session)
                if not current_project or current_project.id != project_id:
                    set_current_project(request.session, project_id)

            # Handle session-based current_project requirement
            if require_current_project:
                current_project = get_current_project(request.user, request.session)

                # No current project set
                if not current_project:
                    if auto_select:
                        # Auto-select first available project
                        current_project = get_or_auto_select_project(
                            request.user, request.session
                        )
                        if current_project:
                            project = current_project
                        else:
                            # User has no projects
                            messages.info(
                                request,
                                "You don't have access to any projects. Please create one first.",
                            )
                            return redirect("projects:list")
                    else:
                        # Auto-select disabled, redirect to project list
                        messages.info(
                            request, "Please select a project to view traces."
                        )
                        return redirect("projects:list")
                else:
                    # Current project exists and is valid
                    # If check_both is True, ensure URL project_id matches session project_id
                    if check_both:
                        if project_id and project_id != current_project.id:
                            messages.error(
                                request,
                                "The project in the URL does not match your current project.",
                            )
                            return redirect("projects:list")
                        project = current_project
                    else:
                        # Use session project if no URL project_id was provided
                        if not project:
                            project = current_project

            # If check_both is True but require_current_project is False, validate both match
            elif check_both and project_id:
                current_project = get_current_project(request.user, request.session)
                if current_project and project_id != current_project.id:
                    messages.error(
                        request,
                        "The project in the URL does not match your current project.",
                    )
                    return redirect("projects:list")

            # If we have a project from URL but no session requirement, use URL project
            if project and not require_current_project:
                pass  # project is already set from URL

            # Ensure we have a project if one was required
            if require_current_project and not project:
                messages.error(request, "No project selected.")
                return redirect("projects:list")

            # Inject project and user_projects into request
            request.current_project = project
            request.user_projects = user_projects

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
