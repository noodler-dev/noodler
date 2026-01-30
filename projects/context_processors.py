from .utils import get_current_project, get_user_projects


def current_project(request):
    """
    Add current_project and user_projects to template context for authenticated users.

    current_project: The project currently selected in session, or None.
    user_projects: All projects the user has access to (for switcher dropdown).
    """
    if not request.user.is_authenticated:
        return {}

    current = get_current_project(request.user, request.session)
    projects = (
        get_user_projects(request.user).select_related("organization").order_by("organization__name", "name")
    )

    return {
        "current_project": current,
        "user_projects": projects,
    }
