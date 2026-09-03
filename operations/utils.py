from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from accounts.models import (
    OrganisationMembership,
    PropertyMembership,
)
from properties.models import (
    Organisation,
    OrganisationSubscription,
    Property,
)
def require_active_subscription(
    organisation,
):
    try:
        subscription = organisation.subscription
    except OrganisationSubscription.DoesNotExist:
        raise PermissionDenied(
            "This organisation does not have "
            "an active RK Ops subscription."
        )
    blocked_statuses = {
        OrganisationSubscription.Status.CANCELLED,
        OrganisationSubscription.Status.SUSPENDED,
    }
    if subscription.status in blocked_statuses:
        raise PermissionDenied(
            "This RK Ops organisation is currently unavailable."
        )
    return subscription
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
    organisation = property_obj.organisation
    if not organisation.is_active:
        raise PermissionDenied(
            "This property is not available."
        )
    # -----------------------------------------------
    # SUBSCRIPTION CHECK
    # Applies to everybody, including superusers.
    # -----------------------------------------------
    require_active_subscription(
        organisation
    )
    # -----------------------------------------------
    # SUPERUSER
    # -----------------------------------------------
    if user.is_superuser:
        return property_obj, None
    # -----------------------------------------------
    # ORGANISATION ACCESS
    # -----------------------------------------------
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
    # -----------------------------------------------
    # PROPERTY ACCESS
    # -----------------------------------------------
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
    return property_obj, property_membership
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
def require_invitation_management_access(
    user,
    invitation,
):
    organisation = invitation.organisation
    if user.is_superuser:
        return organisation
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
    if organisation_membership.role in {
        OrganisationMembership.Role.OWNER,
        OrganisationMembership.Role.ADMIN,
    }:
        return organisation
    invitation_property_ids = set(
        invitation.properties.values_list(
            "id",
            flat=True,
        )
    )
    if not invitation_property_ids:
        raise PermissionDenied(
            "Invitation management access required."
        )
    managed_property_ids = set(
        PropertyMembership.objects
        .filter(
            user=user,
            is_active=True,
            property_id__in=invitation_property_ids,
            role__in={
                PropertyMembership.Role.OWNER,
                PropertyMembership.Role.MANAGER,
            },
        )
        .values_list(
            "property_id",
            flat=True,
        )
    )
    if not invitation_property_ids.issubset(
        managed_property_ids
    ):
        raise PermissionDenied(
            "Invitation management access required."
        )
    return organisation
def require_organisation_account_access(
    user,
    organisation_slug,
):
    organisation = (
        Organisation.objects
        .filter(
            slug=organisation_slug,
            is_active=True,
        )
        .first()
    )
    if not organisation:
        raise PermissionDenied(
            "Organisation not found."
        )
    if user.is_superuser:
        return organisation
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
    if organisation_membership.role in {
        OrganisationMembership.Role.OWNER,
        OrganisationMembership.Role.ADMIN,
    }:
        return organisation
    manager_access = (
        PropertyMembership.objects
        .filter(
            user=user,
            is_active=True,
            property__organisation=organisation,
            property__is_active=True,
            role__in={
                PropertyMembership.Role.OWNER,
                PropertyMembership.Role.MANAGER,
            },
        )
        .exists()
    )
    if not manager_access:
        raise PermissionDenied(
            "You do not have access to this account."
        )
    return organisation