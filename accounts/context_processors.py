from .models import PropertyMembership
def rk_ops_permissions(request):
    can_manage_team = False
    can_supervise = False
    if not request.user.is_authenticated:
        return {
            "can_manage_team": False,
            "can_supervise": False,
        }
    if request.user.is_superuser:
        return {
            "can_manage_team": True,
            "can_supervise": True,
        }
    membership = (
        PropertyMembership.objects
        .filter(
            user=request.user,
            is_active=True,
        )
        .first()
    )
    if membership:
        can_manage_team = membership.role in {
            PropertyMembership.Role.OWNER,
            PropertyMembership.Role.MANAGER,
        }
        can_supervise = membership.role in {
            PropertyMembership.Role.OWNER,
            PropertyMembership.Role.MANAGER,
            PropertyMembership.Role.SUPERVISOR,
        }
    return {
        "can_manage_team": can_manage_team,
        "can_supervise": can_supervise,
    }