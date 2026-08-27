from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from accounts.models import PropertyMembership
from properties.models import Property
def get_property_for_user(user, property_slug):
    property_obj = get_object_or_404(
        Property,
        slug=property_slug,
        is_active=True,
    )
    if user.is_superuser:
        return property_obj, None
    membership = (
        PropertyMembership.objects
        .filter(
            property=property_obj,
            user=user,
            is_active=True,
        )
        .first()
    )
    if not membership:
        raise PermissionDenied(
            "You do not have access to this property."
        )
    return property_obj, membership
def require_management_access(user, property_slug):
    property_obj, membership = get_property_for_user(
        user,
        property_slug,
    )
    if user.is_superuser:
        return property_obj
    allowed_roles = {
        PropertyMembership.Role.OWNER,
        PropertyMembership.Role.MANAGER,
    }
    if membership.role not in allowed_roles:
        raise PermissionDenied(
            "You do not have permission to manage this area."
        )
    return property_obj
def require_supervisory_access(user, property_slug):
    property_obj, membership = get_property_for_user(
        user,
        property_slug,
    )
    if user.is_superuser:
        return property_obj
    allowed_roles = {
        PropertyMembership.Role.OWNER,
        PropertyMembership.Role.MANAGER,
        PropertyMembership.Role.SUPERVISOR,
    }
    if membership.role not in allowed_roles:
        raise PermissionDenied(
            "You do not have permission to perform this action."
        )
    return property_obj