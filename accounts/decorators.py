from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from .utils import get_user_organizations, get_user_organization
from .models import Organization


def require_organization_access(
    org_id_param="org_uid",
    require_admin=False,
):
    """
    Decorator to require organization-level access for a view.

    Args:
        org_id_param: Name of URL parameter containing organization UID (default: 'org_uid')
        require_admin: If True, requires user to be an admin of the organization (default: False)

    Usage:
        @login_required
        @require_organization_access(org_id_param='org_uid')
        def organization_detail(request, org_uid):
            # request.current_organization is already set and validated
            ...

        @login_required
        @require_organization_access(org_id_param='org_uid', require_admin=True)
        def organization_edit(request, org_uid):
            # request.current_organization is already set and validated
            # User is guaranteed to be an admin
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            organization = None
            org_uid = None

            # Get org_uid from URL parameters if specified
            if org_id_param in kwargs:
                org_uid = kwargs[org_id_param]
                organization = get_user_organization(request.user, org_uid)
                if not organization:
                    messages.error(
                        request, "You do not have access to this organization."
                    )
                    return redirect("accounts:organization_list")

            # Check admin requirement
            if require_admin and organization:
                from .utils import is_organization_admin

                if not is_organization_admin(request.user, organization):
                    messages.error(
                        request,
                        "You must be an admin to perform this action.",
                    )
                    return redirect("accounts:organization_detail", org_uid=org_uid)

            # Ensure we have an organization if one was required
            if org_id_param in kwargs and not organization:
                messages.error(request, "Organization not found.")
                return redirect("accounts:organization_list")

            # Inject organization and user_organizations into request
            if organization:
                request.current_organization = organization
            request.user_organizations = get_user_organizations(request.user)

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
