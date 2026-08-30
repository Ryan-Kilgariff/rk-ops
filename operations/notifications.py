from .models import Notification
def create_notification(
    *,
    property_obj,
    recipient,
    title,
    message="",
    task=None,
    issue=None,
):
    if recipient is None:
        return None
    return Notification.objects.create(
        property=property_obj,
        recipient=recipient,
        title=title,
        message=message,
        task=task,
        issue=issue,
    )