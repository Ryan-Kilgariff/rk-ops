from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from operations.models import (
    ActivityLog,
    Notification,
)
from operations.utils import (
    get_property_for_user,
)
import logging
logger = logging.getLogger(__name__)
@login_required
def activity_list(request, property_slug):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug,
    )
    activities = (
        ActivityLog.objects
        .filter(property=property_obj)
        .select_related("user")
        .order_by("-created_at")
    )
    event_filter = request.GET.get("event_type")
    if event_filter:
        activities = activities.filter(
            event_type=event_filter,
        )
    context = {
        "property": property_obj,
        "membership": membership,
        "activities": activities,
        "event_filter": event_filter,
        "event_choices": ActivityLog.EventType.choices,
        "active_page": "activity",
    }
    return render(
        request,
        "operations/activity_list.html",
        context,
    )
@login_required
def notification_list(
    request,
    property_slug,
):
    property_obj, membership = (
        get_property_for_user(
            request.user,
            property_slug,
        )
    )
    notifications = (
        Notification.objects
        .filter(
            property=property_obj,
            recipient=request.user,
        )
        .order_by("-created_at")
    )
    return render(
        request,
        "operations/notification_list.html",
        {
            "property": property_obj,
            "membership": membership,
            "notifications": notifications,
            "active_page": "notifications",
        },
    )
@login_required
def notification_mark_read(
    request,
    property_slug,
    notification_pk,
):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug,
    )
    notification = get_object_or_404(
        Notification,
        pk=notification_pk,
        property=property_obj,
        recipient=request.user,
    )
    if request.method == "POST":
        notification.is_read = True
        notification.save(
            update_fields=["is_read"]
        )
    return redirect(
        "operations:notification_list",
        property_slug=property_obj.slug,
    )
@login_required
def notification_mark_all_read(
    request,
    property_slug,
):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug,
    )
    if request.method == "POST":
        (
            Notification.objects
            .filter(
                property=property_obj,
                recipient=request.user,
                is_read=False,
            )
            .update(is_read=True)
        )
    return redirect(
        "operations:notification_list",
        property_slug=property_obj.slug,
    )
@login_required
def notification_open(
    request,
    property_slug,
    notification_pk,
):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug,
    )
    notification = get_object_or_404(
        Notification,
        pk=notification_pk,
        property=property_obj,
        recipient=request.user,
    )
    if not notification.is_read:
        notification.is_read = True
        notification.save(
            update_fields=["is_read"]
        )
    if notification.task:
        return redirect(
            "operations:task_edit",
            property_slug=property_obj.slug,
            pk=notification.task.pk,
        )
    if notification.issue:
        return redirect(
            "operations:issue_edit",
            property_slug=property_obj.slug,
            pk=notification.issue.pk,
        )
    return redirect(
        "operations:notification_list",
        property_slug=property_obj.slug,
    )