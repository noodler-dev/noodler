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

