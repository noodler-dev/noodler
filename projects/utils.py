from accounts.models import Organization
from .models import Project


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


def get_current_project(user, session):
    """
    Get current project from session and validate user has access.
    
    Args:
        user: The user object
        session: Django session object
        
    Returns:
        Project object if valid current project exists, None otherwise
    """
    current_project_id = session.get("current_project_id")
    if not current_project_id:
        return None
    
    user_projects = get_user_projects(user)
    try:
        return user_projects.get(id=current_project_id)
    except Project.DoesNotExist:
        # Current project is no longer accessible, clear it from session
        del session["current_project_id"]
        return None


def set_current_project(session, project_id):
    """
    Set current project in session.
    
    Args:
        session: Django session object
        project_id: ID of the project to set as current
    """
    session["current_project_id"] = project_id


def get_or_auto_select_project(user, session):
    """
    Get current project from session, or auto-select first available project.
    
    If no current project is set, automatically selects the user's first
    accessible project and sets it in the session.
    
    Args:
        user: The user object
        session: Django session object
        
    Returns:
        Project object if user has any projects, None otherwise
    """
    # Try to get current project from session
    current_project = get_current_project(user, session)
    if current_project:
        return current_project
    
    # No current project set, auto-select first available project
    user_projects = get_user_projects(user)
    first_project = user_projects.first()
    
    if first_project:
        set_current_project(session, first_project.id)
        return first_project
    
    # User has no projects
    return None

