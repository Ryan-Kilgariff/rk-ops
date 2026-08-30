from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from accounts.models import (
    OrganisationMembership,
    PropertyMembership,
)
from properties.models import (
    Organisation,
    Property,
)
def get_property_for_user(
    user,
    property_slug,
):
    property_obj = get_object_or_404(
        Property.objects.select_related(
            "organisation"
        ),
        slug=property_slug,
        is_active=True,
    )
    # --------------------------------------------------
    # SUPERUSER
    # --------------------------------------------------
    if user.is_superuser:
        return property_obj, None
    # --------------------------------------------------
    # PROPERTY MUST BELONG TO AN ACTIVE ORGANISATION
    # --------------------------------------------------
    organisation = property_obj.organisation
    if (
        organisation is None
        or not organisation.is_active
    ):
        raise PermissionDenied(
            "This property is not available."
        )
    # --------------------------------------------------
    # ORGANISATION ACCESS
    # --------------------------------------------------
    organisation_membership = (
        OrganisationMembership.objects
        .filter(
            organisation=organisation,
            user=user,
            is_active=True,
        )
        .first()
    )
    if not organisation_membership:
        raise PermissionDenied(
            "You do not have access to this organisation."
        )
    # --------------------------------------------------
    # PROPERTY ACCESS
    # --------------------------------------------------
    property_membership = (
        PropertyMembership.objects
        .filter(
            property=property_obj,
            user=user,
            is_active=True,
        )
        .first()
    )
    if not property_membership:
        raise PermissionDenied(
            "You do not have access to this property."
        )
    return (
        property_obj,
        property_membership,
    )
def require_management_access(
    user,
    property_slug,
):
    property_obj, membership = (
        get_property_for_user(
            user,
            property_slug,
        )
    )
    if user.is_superuser:
        return property_obj
    if membership.role not in {
        PropertyMembership.Role.OWNER,
        PropertyMembership.Role.MANAGER,
    }:
        raise PermissionDenied(
            "Management access required."
        )
    return property_obj
def require_supervisory_access(
    user,
    property_slug,
):
    property_obj, membership = (
        get_property_for_user(
            user,
            property_slug,
        )
    )
    if user.is_superuser:
        return property_obj
    if membership.role not in {
        PropertyMembership.Role.OWNER,
        PropertyMembership.Role.MANAGER,
        PropertyMembership.Role.SUPERVISOR,
    }:
        raise PermissionDenied(
            "Supervisory access required."
        )
    return property_obj
def get_organisation_for_user(
    user,
    organisation_slug,
):
    organisation = get_object_or_404(
        Organisation,
        slug=organisation_slug,
        is_active=True,
    )
    if user.is_superuser:
        return organisation, None
    membership = (
        OrganisationMembership.objects
        .filter(
            organisation=organisation,
            user=user,
            is_active=True,
        )
        .first()
    )
    if not membership:
        raise PermissionDenied(
            "You do not have access to this organisation."
        )
    return organisation, membership
def require_organisation_management_access(
    user,
    organisation_slug,
):
    organisation, membership = (
        get_organisation_for_user(
            user,
            organisation_slug,
        )
    )
    if user.is_superuser:
        return organisation
    if membership.role not in {
        OrganisationMembership.Role.OWNER,
        OrganisationMembership.Role.ADMIN,
    }:
        raise PermissionDenied(
            "Organisation management access required."
        )
    return organisation