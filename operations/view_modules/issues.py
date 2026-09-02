from django.contrib.auth.decorators import login_required
from operations.activity import log_activity
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from operations.notifications import create_notification
from operations.forms import (
    IssueForm,
)
from operations.models import (
    ActivityLog,
    Issue,
)
from accounts.models import (
    PropertyMembership,
)
from operations.utils import (
    get_property_for_user,
    require_management_access,
    require_supervisory_access,
)
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)
def issue_list(request, property_slug):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    issues = (
        Issue.objects
        .filter(property=property_obj)
        .select_related("assigned_to")
    )
    status_filter = request.GET.get("status")
    priority_filter = request.GET.get("priority")
    if status_filter:
        issues = issues.filter(status=status_filter)
    if priority_filter:
        issues = issues.filter(priority=priority_filter)
    context = {
        "property": property_obj,
        "membership": membership,
        "issues": issues,
        "status_filter": status_filter,
        "priority_filter": priority_filter,
        "status_choices": Issue.Status.choices,
        "priority_choices": Issue.Priority.choices,
        "active_page": "issues",
    }
    return render(
        request,
        "operations/issue_list.html",
        context,
    )
@login_required
def issue_create(request, property_slug):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    if request.method == "POST":
        form = IssueForm(
            request.POST,
            property_obj=property_obj,
        )
        if form.is_valid():
            issue = form.save(commit=False)
            issue.property = property_obj
            issue.save()
            detail_parts = [
                issue.get_category_display(),
                issue.get_priority_display(),
            ]
            if issue.location:
                detail_parts.append(issue.location)
            log_activity(
                property_obj=property_obj,
                event_type=ActivityLog.EventType.ISSUE_REPORTED,
                title=issue.title,
                user=request.user,
                detail=" · ".join(detail_parts),
            )
            return redirect(
                "operations:issue_list",
                property_slug=property_obj.slug,
            )
    else:
        form = IssueForm(
            property_obj=property_obj,
        )
    context = {
        "property": property_obj,
        "form": form,
        "active_page": "issues",
    }
    return render(
        request,
        "operations/issue_form.html",
        context,
    )
@login_required
def issue_edit(request, property_slug, pk):
    property_obj = require_supervisory_access(
        request.user,
        property_slug,
    )
    issue = get_object_or_404(
        Issue,
        pk=pk,
        property=property_obj,
    )
    if request.method == "POST":
        form = IssueForm(
            request.POST,
            instance=issue,
            property_obj=property_obj,
        )
        if form.is_valid():
            updated_issue = form.save(commit=False)
            if (
                updated_issue.status == Issue.Status.RESOLVED
                and not updated_issue.resolved_at
            ):
                updated_issue.resolved_at = timezone.now()
            elif updated_issue.status != Issue.Status.RESOLVED:
                updated_issue.resolved_at = None
            updated_issue.save()
            return redirect(
                "operations:issue_list",
                property_slug=property_obj.slug,
            )
    else:
        form = IssueForm(
            instance=issue,
            property_obj=property_obj,
        )
    context = {
        "property": property_obj,
        "issue": issue,
        "form": form,
        "active_page": "issues",
        "form_mode": "edit",
    }
    return render(
        request,
        "operations/issue_form.html",
        context,
    )
@login_required
def issue_resolve(request, property_slug, pk):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    issue = get_object_or_404(
        Issue,
        pk=pk,
        property=property_obj,
    )
    if request.method == "POST":
        issue.status = Issue.Status.RESOLVED
        issue.resolved_at = timezone.now()
        issue.save(
            update_fields=[
                "status",
                "resolved_at",
                "updated_at",
            ]
        )
        log_activity(
            property_obj=property_obj,
            event_type=ActivityLog.EventType.ISSUE_RESOLVED,
            title=issue.title,
            user=request.user,
        )
    return redirect(
        "operations:issue_list",
        property_slug=property_obj.slug,
    )
@login_required
def issue_quick_assign(
    request,
    property_slug,
    issue_pk,
):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    issue = get_object_or_404(
        Issue,
        pk=issue_pk,
        property=property_obj,
    )
    if request.method == "POST":
        membership_id = request.POST.get(
            "membership_id"
        )
        previous_assignee_id = issue.assigned_to_id
        if membership_id:
            membership = get_object_or_404(
                PropertyMembership,
                pk=membership_id,
                property=property_obj,
                is_active=True,
            )
            issue.assigned_to = membership.user
            assigned_name = (
                membership.user.get_full_name()
                or membership.user.username
            )
        else:
            issue.assigned_to = None
            assigned_name = "Unassigned"
        issue.save(
            update_fields=[
                "assigned_to",
                "updated_at",
            ]
        )
        if issue.assigned_to:
            detail = f"Assigned to {assigned_name}"
        else:
            detail = "Moved to unassigned work"
        if previous_assignee_id != issue.assigned_to_id:
            log_activity(
                property_obj=property_obj,
                event_type=ActivityLog.EventType.ISSUE_ASSIGNED,
                title=issue.title,
                user=request.user,
                detail=detail,
            )
            if issue.assigned_to:
                create_notification(
                    property_obj=property_obj,
                    recipient=issue.assigned_to,
                    title="Issue assigned",
                    message=issue.title,
                    issue=issue
                )
    return redirect(
        "operations:dashboard",
        property_slug=property_obj.slug,
    )
