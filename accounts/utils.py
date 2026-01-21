from .models import Organization, Membership


def get_user_organizations(user):
    """Get all organizations the user belongs to."""
    try:
        user_profile = user.userprofile
        return Organization.objects.filter(
            membership__user_profile=user_profile
        ).distinct()
    except AttributeError:
        return Organization.objects.none()


def get_user_organization(user, org_id):
    """Get a specific organization if user has access."""
    user_orgs = get_user_organizations(user)
    try:
        return user_orgs.get(id=org_id)
    except Organization.DoesNotExist:
        return None


def is_organization_admin(user, organization):
    """Check if user is an admin of the organization."""
    try:
        user_profile = user.userprofile
        membership = Membership.objects.get(
            user_profile=user_profile, organization=organization
        )
        return membership.role == "admin"
    except (AttributeError, Membership.DoesNotExist):
        return False
