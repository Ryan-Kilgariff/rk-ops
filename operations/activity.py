from .models import ActivityLog
def log_activity(
    *,
    property_obj,
    event_type,
    title,
    user=None,
    detail="",
):
    ActivityLog.objects.create(
        property=property_obj,
        user=user,
        event_type=event_type,
        title=title,
        detail=detail,
    )