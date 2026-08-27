from accounts.models import PropertyMembership
from properties.models import Property
def rk_ops_permissions(request):
    can_manage_team = False
    can_supervise = False
    accessible_properties = []
    if not request.user.is_authenticated:
        return {
            "can_manage_team": False,
            "can_supervise": False,
            "accessible_properties": [],
        }
    if request.user.is_superuser:
        accessible_properties = list(
            Property.objects
            .filter(is_active=True)
            .order_by("name")
        )
        return {
            "can_manage_team": True,
            "can_supervise": True,
            "accessible_properties": accessible_properties,
        }
    memberships = (
        PropertyMembership.objects
        .filter(
            user=request.user,
            is_active=True,
            property__is_active=True,
        )
        .select_related("property")
        .order_by("property__name")
    )
    accessible_properties = [
        membership.property
        for membership in memberships
    ]
    property_slug = (
        request.resolver_match.kwargs.get("property_slug")
        if request.resolver_match
        else None
    )
    current_membership = None
    if property_slug:
        current_membership = memberships.filter(
            property__slug=property_slug,
        ).first()
    if current_membership:
        can_manage_team = current_membership.role in {
            PropertyMembership.Role.OWNER,
            PropertyMembership.Role.MANAGER,
        }
        can_supervise = current_membership.role in {
            PropertyMembership.Role.OWNER,
            PropertyMembership.Role.MANAGER,
            PropertyMembership.Role.SUPERVISOR,
        }
    return {
        "can_manage_team": can_manage_team,
        "can_supervise": can_supervise,
        "accessible_properties": accessible_properties,
    }