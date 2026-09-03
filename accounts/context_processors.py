from accounts.models import (
    OrganisationMembership,
    PropertyMembership,
)
from properties.models import Property
from operations.models import Notification
def rk_ops_permissions(request):
    can_manage_team = False
    can_supervise = False
    can_manage_organisation = False
    accessible_properties = []
    unread_notification_count = 0
    recent_notifications = []
    current_property = None
    current_organisation = None
    current_subscription = None
    subscription_warning = False
    can_view_organisation_account = False
    if not request.user.is_authenticated:
        return {
            "can_manage_team": False,
            "can_supervise": False,
            "can_manage_organisation": False,
            "accessible_properties": [],
            "unread_notification_count": 0,
            "recent_notifications": [],
            "current_property": None,
            "current_organisation": None,
            "property": None,
            "current_subscription": None,
            "subscription_warning": False,
            "can_view_organisation_account": False,
        }
    property_slug = (
        request.resolver_match.kwargs.get(
            "property_slug"
        )
        if request.resolver_match
        else None
    )
    organisation_slug = (
        request.resolver_match.kwargs.get(
            "organisation_slug"
        )
        if request.resolver_match
        else None
    )
    # --------------------------------------------------
    # SUPERUSER
    # --------------------------------------------------
    if request.user.is_superuser:
        accessible_properties = list(
            Property.objects
            .filter(
                is_active=True,
                organisation__is_active=True,
            )
            .select_related(
                "organisation"
            )
            .order_by(
                "name"
            )
        )
        if property_slug:
            current_property = (
                Property.objects
                .filter(
                    slug=property_slug,
                    is_active=True,
                    organisation__is_active=True,
                )
                .select_related(
                    "organisation"
                )
                .first()
            )
        elif organisation_slug:
            current_property = (
                Property.objects
                .filter(
                    organisation__slug=organisation_slug,
                    is_active=True,
                    organisation__is_active=True,
                )
                .select_related(
                    "organisation"
                )
                .order_by(
                    "name"
                )
                .first()
            )
        elif accessible_properties:
            current_property = (
                accessible_properties[0]
            )
        if current_property:
            current_organisation = (
                current_property.organisation
            )
            (
                current_subscription,
                subscription_warning,
            ) = get_subscription_context(
                current_property
            )
            unread_notification_count = (
                Notification.objects
                .filter(
                    property=current_property,
                    recipient=request.user,
                    is_read=False,
                )
                .count()
            )
            recent_notifications = list(
                Notification.objects
                .filter(
                    property=current_property,
                    recipient=request.user,
                )
                .select_related(
                    "task",
                    "issue",
                )
                .order_by(
                    "-created_at"
                )[:5]
            )
        return {
            "can_manage_team": True,
            "can_supervise": True,
            "can_manage_organisation": True,
            "accessible_properties": accessible_properties,
            "unread_notification_count": unread_notification_count,
            "recent_notifications": recent_notifications,
            "current_property": current_property,
            "current_organisation": current_organisation,
            "property": current_property,
            "current_subscription": current_subscription,
            "subscription_warning": subscription_warning,
            "can_view_organisation_account": True,
        }
    # --------------------------------------------------
    # NORMAL USER
    # --------------------------------------------------
    memberships = (
        PropertyMembership.objects
        .filter(
            user=request.user,
            is_active=True,
            property__is_active=True,
            property__organisation__is_active=True,
            property__organisation__memberships__user=request.user,
            property__organisation__memberships__is_active=True,
        )
        .select_related(
            "property",
            "property__organisation",
        )
        .distinct()
        .order_by(
            "property__name"
        )
    )
    accessible_properties = [
        membership.property
        for membership in memberships
    ]
    current_membership = None
    # --------------------------------------------------
    # PROPERTY PAGE
    # --------------------------------------------------
    if property_slug:
        current_membership = (
            memberships
            .filter(
                property__slug=property_slug
            )
            .first()
        )
    # --------------------------------------------------
    # ORGANISATION PAGE
    # Account / Billing / Invitations etc.
    # --------------------------------------------------
    elif organisation_slug:
        current_membership = (
            memberships
            .filter(
                property__organisation__slug=organisation_slug
            )
            .first()
        )
    # --------------------------------------------------
    # PROFILE / OTHER AUTHENTICATED PAGE
    # Fall back to user's first accessible property.
    # --------------------------------------------------
    elif memberships.exists():
        current_membership = (
            memberships.first()
        )
    if current_membership:
        current_property = (
            current_membership.property
        )
        current_organisation = (
            current_property.organisation
        )
        can_manage_team = (
            current_membership.role
            in {
                PropertyMembership.Role.OWNER,
                PropertyMembership.Role.MANAGER,
            }
        )
        can_supervise = (
            current_membership.role
            in {
                PropertyMembership.Role.OWNER,
                PropertyMembership.Role.MANAGER,
                PropertyMembership.Role.SUPERVISOR,
            }
        )
        (
            current_subscription,
            subscription_warning,
        ) = get_subscription_context(
            current_property
        )
        recent_notifications = list(
            Notification.objects
            .filter(
                property=current_property,
                recipient=request.user,
            )
            .select_related(
                "task",
                "issue",
            )
            .order_by(
                "-created_at"
            )[:5]
        )
        unread_notification_count = (
            Notification.objects
            .filter(
                property=current_property,
                recipient=request.user,
                is_read=False,
            )
            .count()
        )
    # --------------------------------------------------
    # ORGANISATION MANAGEMENT
    # --------------------------------------------------
    organisation_membership = None
    can_view_organisation_account = False
    if current_organisation:
        organisation_membership = (
            OrganisationMembership.objects
            .filter(
                organisation=current_organisation,
                user=request.user,
                is_active=True,
            )
            .first()
        )
    elif organisation_slug:
        organisation_membership = (
            OrganisationMembership.objects
            .filter(
                organisation__slug=organisation_slug,
                user=request.user,
                is_active=True,
                organisation__is_active=True,
            )
            .select_related(
                "organisation"
            )
            .first()
        )
        if organisation_membership:
            current_organisation = (
                organisation_membership.organisation
            )
    can_manage_organisation = bool(
        organisation_membership
        and organisation_membership.role
        in {
            OrganisationMembership.Role.OWNER,
            OrganisationMembership.Role.ADMIN,
        }
    )
    can_view_organisation_account = (
        can_manage_organisation
        or (
            current_membership
            and current_membership.role
            in {
                PropertyMembership.Role.OWNER,
                PropertyMembership.Role.MANAGER,
            }
        )
    )
    return {
        "can_manage_team": can_manage_team,
        "can_supervise": can_supervise,
        "can_manage_organisation": can_manage_organisation,
        "can_view_organisation_account": can_view_organisation_account,
        "accessible_properties": accessible_properties,
        "unread_notification_count": unread_notification_count,
        "recent_notifications": recent_notifications,
        "current_property": current_property,
        "current_organisation": current_organisation,
        # Important:
        # base.html already uses "property" everywhere.
        "property": current_property,
        "current_subscription": current_subscription,
        "subscription_warning": subscription_warning,
    }
def get_subscription_context(
    property_obj,
):
    if not property_obj:
        return None, False
    subscription = getattr(
        property_obj.organisation,
        "subscription",
        None,
    )
    warning = bool(
        subscription
        and subscription.status
        == subscription.Status.PAST_DUE
    )
    return subscription, warning