from accounts.models import PropertyMembership
from properties.models import Property
from operations.models import Notification
def rk_ops_permissions(request):
    can_manage_team = False
    can_supervise = False
    accessible_properties = []
    unread_notification_count = 0
    recent_notifications = []
    current_property = None
    if not request.user.is_authenticated:
        return {
            "can_manage_team": False,
            "can_supervise": False,
            "accessible_properties": [],
            "unread_notification_count": 0,
            "recent_notifications": [],
        }
    property_slug = (
        request.resolver_match.kwargs.get("property_slug")
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
            .select_related("organisation")
            .order_by("name")
        )
        if property_slug:
            current_property = (
                Property.objects
                .filter(
                    slug=property_slug,
                    is_active=True,
                )
                .first()
            )
        if current_property:
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
                .order_by("-created_at")[:5]
            )
        return {
            "can_manage_team": True,
            "can_supervise": True,
            "accessible_properties": accessible_properties,
            "unread_notification_count": unread_notification_count,
            "recent_notifications": recent_notifications,
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
        .order_by("property__name")
    )
    accessible_properties = [
        membership.property
        for membership in memberships
    ]
    current_membership = None
    if property_slug:
        current_membership = memberships.filter(
            property__slug=property_slug,
        ).first()
    if current_membership:
        current_property = current_membership.property
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
            .order_by("-created_at")[:5]
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
    return {
        "can_manage_team": can_manage_team,
        "can_supervise": can_supervise,
        "accessible_properties": accessible_properties,
        "unread_notification_count": unread_notification_count,
        "recent_notifications": recent_notifications,
    }