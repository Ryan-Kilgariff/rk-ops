from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .activity import log_activity
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
from django.utils.text import slugify
from properties.forms import PropertyForm
from .notifications import create_notification
from .services import (
    generate_recurring_tasks_for_date,
    update_task_escalations,
)
from accounts.forms import (
    OrganisationInvitationForm,
    MembershipEditForm,
    TeamMemberCreateForm,
    InvitationSignupForm,
)
from properties.models import Property
from .forms import (
    ChecklistForm,
    ChecklistItemForm,
    HandoverNoteForm,
    IssueForm,
    TaskForm,
    RecurringTaskForm,
)
from .models import (
    ActivityLog,
    Checklist,
    ChecklistCompletion,
    ChecklistItem,
    ChecklistRun,
    HandoverNote,
    Issue,
    Task,
    Notification,
    RecurringTask
)
from accounts.models import (
    OrganisationInvitation,
    OrganisationMembership,
    PropertyMembership,
)
from .utils import (
    get_organisation_for_user,
    get_property_for_user,
    require_management_access,
    require_organisation_management_access,
    require_supervisory_access,
)
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from datetime import datetime, timedelta
from django.contrib.auth import login
from django.contrib.auth import get_user_model
from accounts.forms import (
    InvitationSignupForm,
    OrganisationInvitationForm,
)
User = get_user_model()
@login_required
def dashboard(request, property_slug):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    now = timezone.now()
    today = timezone.localdate()
    seven_days_ago = today - timedelta(days=6)
    seven_day_tasks = Task.objects.filter(
        property=property_obj,
        scheduled_date__range=(
            seven_days_ago,
            today,
        ),
    ).exclude(
        status=Task.Status.CANCELLED,
    )
    seven_day_task_count = seven_day_tasks.count()
    seven_day_completed_tasks = seven_day_tasks.filter(
        status=Task.Status.COMPLETED,
    )
    seven_day_completed_count = (
        seven_day_completed_tasks.count()
    )
    if seven_day_task_count:
        seven_day_completion_rate = round(
            (
                seven_day_completed_count
                / seven_day_task_count
            )
            * 100
        )
    else:
        seven_day_completion_rate = 0
    seven_day_issues_reported = (
        Issue.objects
        .filter(
            property=property_obj,
            reported_at__date__range=(
                seven_days_ago,
                today,
            ),
        )
        .count()
    )
    seven_day_issues_resolved = (
        Issue.objects
        .filter(
            property=property_obj,
            resolved_at__date__range=(
                seven_days_ago,
                today,
            ),
        )
        .count()
    )
    seven_day_checklists_completed = (
        ChecklistRun.objects
        .filter(
            checklist__property=property_obj,
            completed_at__date__range=(
                seven_days_ago,
                today,
            ),
        )
        .count()
    )
    seven_day_activity = []
    for day_offset in range(7):
        day = seven_days_ago + timedelta(
            days=day_offset
        )
        completed_tasks = (
            seven_day_completed_tasks
            .filter(
                completed_at__date=day,
            )
            .count()
        )
        issues_reported = (
            Issue.objects
            .filter(
                property=property_obj,
                reported_at__date=day,
            )
            .count()
        )
        issues_resolved = (
            Issue.objects
            .filter(
                property=property_obj,
                resolved_at__date=day,
            )
            .count()
        )
        checklists_completed = (
            ChecklistRun.objects
            .filter(
                checklist__property=property_obj,
                completed_at__date=day,
            )
            .count()
        )
        seven_day_activity.append(
            {
                "date": day,
                "completed_tasks": completed_tasks,
                "issues_reported": issues_reported,
                "issues_resolved": issues_resolved,
                "checklists_completed": (
                    checklists_completed
                ),
            }
        )
    tasks = (
        Task.objects
        .filter(property=property_obj)
        .select_related("assigned_to")
    )
    open_tasks = tasks.exclude(
        status__in=[
            Task.Status.COMPLETED,
            Task.Status.CANCELLED,
        ]
    )
    tasks_today = open_tasks.filter(
        due_at__date=today,
    )
    overdue_tasks = Task.objects.filter(
        property=property_obj,
        due_at__lt=timezone.now(),
    ).exclude(
        status__in=[
            Task.Status.COMPLETED,
            Task.Status.CANCELLED,
        ]
    )
    issues = (
        Issue.objects
        .filter(property=property_obj)
        .select_related("assigned_to")
    )
    open_issues = issues.exclude(
        status__in=[
            Issue.Status.RESOLVED,
            Issue.Status.CLOSED,
        ]
    )
    today_tasks = Task.objects.filter(
        property=property_obj,
        scheduled_date=today,
    )
    today_completed_tasks = today_tasks.filter(
        status=Task.Status.COMPLETED,
    )
    today_task_count = today_tasks.count()
    today_completed_count = today_completed_tasks.count()
    if today_task_count:
        task_completion_rate = round(
            (today_completed_count / today_task_count) * 100
        )
    else:
        task_completion_rate = 0
    recent_completed_tasks = (
        Task.objects
        .filter(
            property=property_obj,
            status=Task.Status.COMPLETED,
        )
        .select_related("assigned_to")
        .order_by("-completed_at")[:5]
    )
    open_issue_counts = {
        "urgent": open_issues.filter(
            priority=Issue.Priority.URGENT
        ).count(),
        "high": open_issues.filter(
            priority=Issue.Priority.HIGH
        ).count(),
        "medium": open_issues.filter(
            priority=Issue.Priority.MEDIUM
        ).count(),
        "low": open_issues.filter(
            priority=Issue.Priority.LOW
        ).count(),
    }
    completed_checklists_today = (
        ChecklistRun.objects
        .filter(
            checklist__property=property_obj,
            completed_at__date=today,
        )
        .count()
    )
    active_handover_count = (
        HandoverNote.objects
        .filter(
            property=property_obj,
            is_resolved=False,
        )
        .count()
    )
    recent_resolved_issues = (
        Issue.objects
        .filter(
            property=property_obj,
            status=Issue.Status.RESOLVED,
        )
        .select_related("assigned_to")
        .order_by("-resolved_at")[:5]
    )
    recent_checklist_runs = (
        ChecklistRun.objects
        .filter(
            checklist__property=property_obj,
            completed_at__isnull=False,
        )
        .select_related(
            "checklist",
            "started_by",
        )
        .order_by("-completed_at")[:5]
    )
    recent_activity = (
        ActivityLog.objects
        .filter(property=property_obj)
        .select_related("user")
        .order_by("-created_at")[:8]
    )
    escalated_tasks = (
        Task.objects
        .filter(
            property=property_obj,
        )
        .exclude(
            status__in=[
                Task.Status.COMPLETED,
                Task.Status.CANCELLED,
            ]
        )
        .exclude(
            escalation_level=(
                Task.EscalationLevel.NONE
            ),
        )
    )
    watch_tasks = escalated_tasks.filter(
        escalation_level=Task.EscalationLevel.WATCH,
    ).count()
    high_escalations = escalated_tasks.filter(
        escalation_level=Task.EscalationLevel.HIGH,
    ).count()
    critical_escalations = escalated_tasks.filter(
        escalation_level=(
            Task.EscalationLevel.CRITICAL
        ),
    ).count()
    urgent_items = (
        open_tasks.filter(
            priority=Task.Priority.URGENT,
        ).count()
        +
        open_issues.filter(
            priority=Issue.Priority.URGENT,
        ).count()
    )
    overdue_by_category = {
        value: overdue_tasks.filter(
            category=value
        ).count()
        for value, label in Task.Category.choices
    }
    overdue_task_details = []
    for task in overdue_tasks.select_related(
        "assigned_to"
    ).order_by("due_at")[:8]:
        overdue_hours = None
        overdue_days = None
        if task.due_at:
            overdue_delta = (
                timezone.now() - task.due_at
            )
            overdue_hours = int(
                overdue_delta.total_seconds() // 3600
            )
            overdue_days = overdue_delta.days
        overdue_task_details.append(
            {
                "task": task,
                "overdue_hours": overdue_hours,
                "overdue_days": overdue_days,
            }
        )
    top_overdue_category = None
    top_overdue_count = 0
    for value, label in Task.Category.choices:
        count = overdue_by_category.get(
            value,
            0,
        )
        if count > top_overdue_count:
            top_overdue_count = count
            top_overdue_category = label
    department_workload = []
    for value, label in Task.Category.choices:
        open_task_count = (
            Task.objects
            .filter(
                property=property_obj,
                category=value,
            )
            .exclude(
                status__in=[
                    Task.Status.COMPLETED,
                    Task.Status.CANCELLED,
                ]
            )
            .count()
        )
        overdue_task_count = (
            overdue_tasks
            .filter(
                category=value,
            )
            .count()
        )
        open_issue_count = (
            open_issues
            .filter(
                category=value,
            )
            .count()
        )
        total_pressure = (
            open_task_count
            + overdue_task_count
            + open_issue_count
        )
        department_workload.append(
            {
                "value": value,
                "label": label,
                "open_tasks": open_task_count,
                "overdue_tasks": overdue_task_count,
                "open_issues": open_issue_count,
                "total_pressure": total_pressure,
            }
        )
    department_workload.sort(
        key=lambda department: department["total_pressure"],
        reverse=True,
    )
    staff_workload = []
    memberships = (
        PropertyMembership.objects
        .filter(
            property=property_obj,
            is_active=True,
        )
        .select_related("user")
    )
    for membership in memberships:
        user = membership.user
        open_task_count = (
            Task.objects
            .filter(
                property=property_obj,
                assigned_to=user,
            )
            .exclude(
                status__in=[
                    Task.Status.COMPLETED,
                    Task.Status.CANCELLED,
                ]
            )
            .count()
        )
        overdue_task_count = (
            overdue_tasks
            .filter(
                assigned_to=user,
            )
            .count()
        )
        open_issue_count = (
            open_issues
            .filter(
                assigned_to=user,
            )
            .count()
        )
        total_workload = (
            open_task_count
            + open_issue_count
        )
        staff_workload.append(
        {
            "user": user,
            "membership": membership,
            "open_tasks": open_task_count,
            "overdue_tasks": overdue_task_count,
            "open_issues": open_issue_count,
            "total_workload": total_workload,
            "task_preview": (
                Task.objects
                .filter(
                    property=property_obj,
                    assigned_to=user,
                )
                .exclude(
                    status__in=[
                        Task.Status.COMPLETED,
                        Task.Status.CANCELLED,
                    ]
                )
                .order_by(
                    "due_at",
                    "-priority",
                )[:3]
            ),
            "issue_preview": (
                open_issues
                .filter(
                    assigned_to=user,
                )
                .order_by(
                    "-priority",
                    "reported_at",
                )[:2]
            ),
        }
    )
    staff_workload.sort(
        key=lambda staff: (
            staff["overdue_tasks"],
            staff["total_workload"],
        ),
        reverse=True,
    )
    unassigned_tasks = (
        Task.objects
        .filter(
            property=property_obj,
            assigned_to__isnull=True,
        )
        .exclude(
            status__in=[
                Task.Status.COMPLETED,
                Task.Status.CANCELLED,
            ]
        )
        .count()
    )
    unassigned_issues = (
        open_issues
        .filter(
            assigned_to__isnull=True,
        )
        .count()
    )
    unassigned_work = (
        unassigned_tasks
        + unassigned_issues
    )
    unassigned_task_preview = (
        Task.objects
        .filter(
            property=property_obj,
            assigned_to__isnull=True,
        )
        .exclude(
            status__in=[
                Task.Status.COMPLETED,
                Task.Status.CANCELLED,
            ]
        )
        .order_by("due_at")[:5]
    )
    unassigned_issue_preview = (
        open_issues
        .filter(
            assigned_to__isnull=True,
        )
        .order_by("-reported_at")[:5]
    )
    department_workload_dashboard = [
        department
        for department in department_workload
        if department["total_pressure"] > 0
    ][:6]
    staff_workload_dashboard = [
        staff
        for staff in staff_workload
        if staff["total_workload"] > 0
    ][:6]
    recent_issues = open_issues.order_by(
        "-reported_at"
    )[:5]
    context = {
        "property": property_obj,
        "tasks_today": tasks_today,
        "overdue_tasks": overdue_tasks,
        "open_tasks": open_tasks,
        "open_issues": open_issues,
        "recent_issues": recent_issues,
        "urgent_items": urgent_items,
        "active_page": "dashboard",
        "recent_activity": recent_activity,
        "today_task_count": today_task_count,
        "today_completed_count": today_completed_count,
        "task_completion_rate": task_completion_rate,
        "open_issue_counts": open_issue_counts,
        "completed_checklists_today": completed_checklists_today,
        "active_handover_count": active_handover_count,
        "seven_day_task_count": seven_day_task_count,
        "seven_day_completed_count": seven_day_completed_count,
        "seven_day_completion_rate": seven_day_completion_rate,
        "seven_day_issues_reported": seven_day_issues_reported,
        "seven_day_issues_resolved": seven_day_issues_resolved,
        "seven_day_checklists_completed": (
            seven_day_checklists_completed
        ),
        "seven_day_activity": seven_day_activity,
        "overdue_by_category": overdue_by_category,
        "overdue_task_details": overdue_task_details,
        "top_overdue_category": top_overdue_category,
        "top_overdue_count": top_overdue_count,
        "department_workload": department_workload,
        "staff_workload": staff_workload,
        "unassigned_tasks": unassigned_tasks,
        "unassigned_issues": unassigned_issues,
        "unassigned_work": unassigned_work,
        "department_workload_dashboard": (
            department_workload_dashboard
        ),
        "staff_workload_dashboard": (
            staff_workload_dashboard
        ),
        "unassigned_task_preview": unassigned_task_preview,
        "unassigned_issue_preview": unassigned_issue_preview,
        "active_memberships": memberships,
        "watch_tasks": watch_tasks,
        "high_escalations": high_escalations,
        "critical_escalations": critical_escalations,
    }
    return render(
        request,
        "operations/dashboard.html",
        context,
    )
@login_required
def property_home(request):
    # --------------------------------------------------
    # SUPERUSER
    # --------------------------------------------------
    if request.user.is_superuser:
        property_obj = (
            Property.objects
            .filter(
                is_active=True,
                organisation__is_active=True,
            )
            .select_related("organisation")
            .order_by("name")
            .first()
        )
        if not property_obj:
            raise PermissionDenied(
                "No active properties are available."
            )
        return redirect(
            "operations:dashboard",
            property_slug=property_obj.slug,
        )
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
    membership = memberships.first()
    if not membership:
        raise PermissionDenied(
            "You do not currently have access to any property."
        )
    return redirect(
        "operations:dashboard",
        property_slug=membership.property.slug,
    )
@login_required
def task_list(request, property_slug):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    tasks = (
        Task.objects
        .filter(property=property_obj)
        .select_related("assigned_to")
        .order_by("status", "due_at", "-created_at")
    )
    status_filter = request.GET.get("status")
    priority_filter = request.GET.get("priority")
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    context = {
        "property": property_obj,
        "membership": membership,
        "tasks": tasks,
        "status_filter": status_filter,
        "priority_filter": priority_filter,
        "status_choices": Task.Status.choices,
        "priority_choices": Task.Priority.choices,
        "active_page": "tasks",
    }
    return render(
        request,
        "operations/task_list.html",
        context,
    )
@login_required
def task_create(request, property_slug):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    if request.method == "POST":
        form = TaskForm(
            request.POST,
            property_obj=property_obj,
        )
        if form.is_valid():
            task = form.save(commit=False)
            task.property = property_obj
            task.save()
            log_activity(
                property_obj=property_obj,
                event_type=ActivityLog.EventType.TASK_CREATED,
                title=task.title,
                user=request.user,
                detail=(
                    f"{task.get_category_display()} · "
                    f"{task.get_priority_display()}"
                ),
            )
            return redirect(
                "operations:task_list",
                property_slug=property_obj.slug,
            )
    else:
        form = TaskForm(
            property_obj=property_obj,
        )
    context = {
        "property": property_obj,
        "form": form,
        "active_page": "tasks",
    }
    return render(
        request,
        "operations/task_form.html",
        context,
    )
@login_required
def task_edit(request, property_slug, pk):
    property_obj = require_supervisory_access(
        request.user,
        property_slug,
    )
    task = get_object_or_404(
        Task,
        pk=pk,
        property=property_obj,
    )
    if request.method == "POST":
        form = TaskForm(
            request.POST,
            instance=task,
            property_obj=property_obj,
        )
        if form.is_valid():
            updated_task = form.save(commit=False)
            if (
                updated_task.status == Task.Status.COMPLETED
                and not updated_task.completed_at
            ):
                updated_task.completed_at = timezone.now()
            elif updated_task.status != Task.Status.COMPLETED:
                updated_task.completed_at = None
            updated_task.save()
            return redirect(
                "operations:task_list",
                property_slug=property_obj.slug,
            )
    else:
        form = TaskForm(
            instance=task,
            property_obj=property_obj,
        )
    context = {
        "property": property_obj,
        "task": task,
        "form": form,
        "active_page": "tasks",
        "form_mode": "edit",
    }
    return render(
        request,
        "operations/task_form.html",
        context,
    )
@login_required
def task_complete(request, property_slug, pk):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    task = get_object_or_404(
        Task,
        pk=pk,
        property=property_obj,
    )
    if request.method == "POST":
        if task.status != Task.Status.COMPLETED:
            task.status = Task.Status.COMPLETED
            task.completed_at = timezone.now()
            task.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "updated_at",
                ]
            )
            log_activity(
                property_obj=property_obj,
                event_type=ActivityLog.EventType.TASK_COMPLETED,
                title=task.title,
                user=request.user,
            )
    return redirect(
        "operations:task_list",
        property_slug=property_obj.slug,
    )
@login_required
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
def handover_list(request, property_slug):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    notes = (
        HandoverNote.objects
        .filter(property=property_obj)
        .select_related("author")
    )
    open_notes = notes.filter(
        is_resolved=False,
    )
    resolved_notes = notes.filter(
        is_resolved=True,
    )[:10]
    open_issues = (
        Issue.objects
        .filter(property=property_obj)
        .exclude(
            status__in=[
                Issue.Status.RESOLVED,
                Issue.Status.CLOSED,
            ]
        )
        .order_by("-priority", "-reported_at")
    )
    context = {
        "property": property_obj,
        "open_notes": open_notes,
        "resolved_notes": resolved_notes,
        "open_issues": open_issues,
        "active_page": "handover",
    }
    return render(
        request,
        "operations/handover_list.html",
        context,
    )
@login_required
def handover_create(request, property_slug):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    if request.method == "POST":
        form = HandoverNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.property = property_obj
            if request.user.is_authenticated:
                note.author = request.user
            note.save()
            log_activity(
                property_obj=property_obj,
                event_type=ActivityLog.EventType.HANDOVER_ADDED,
                title=note.note[:120],
                user=request.user,
                detail=note.get_shift_display(),
            )
            return redirect(
                "operations:handover_list",
                property_slug=property_obj.slug,
            )
    else:
        form = HandoverNoteForm()
    context = {
        "property": property_obj,
        "form": form,
        "active_page": "handover",
    }
    return render(
        request,
        "operations/handover_form.html",
        context,
    )
@login_required
def handover_resolve(request, property_slug, pk):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    note = get_object_or_404(
        HandoverNote,
        pk=pk,
        property=property_obj,
    )
    if request.method == "POST":
        note.is_resolved = True
        note.resolved_at = timezone.now()
        note.save(
            update_fields=[
                "is_resolved",
                "resolved_at",
            ]
        )
    return redirect(
        "operations:handover_list",
        property_slug=property_obj.slug,
    )
@login_required
def checklist_list(request, property_slug):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    checklists = (
        Checklist.objects
        .filter(
            property=property_obj,
            is_active=True,
        )
        .prefetch_related("items")
    )
    recent_runs = (
        ChecklistRun.objects
        .filter(
            checklist__property=property_obj,
        )
        .select_related(
            "checklist",
            "started_by",
        )[:10]
    )
    context = {
        "property": property_obj,
        "checklists": checklists,
        "recent_runs": recent_runs,
        "active_page": "checklists",
    }
    return render(
        request,
        "operations/checklist_list.html",
        context,
    )
@login_required
def checklist_start(request, property_slug, pk):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    checklist = get_object_or_404(
        Checklist,
        pk=pk,
        property=property_obj,
        is_active=True,
    )
    if request.method == "POST":
        run = ChecklistRun.objects.create(
            checklist=checklist,
            started_by=(
                request.user
                if request.user.is_authenticated
                else None
            ),
        )
        log_activity(
            property_obj=property_obj,
            event_type=ActivityLog.EventType.CHECKLIST_STARTED,
            title=checklist.name,
            user=request.user,
            detail=f"{checklist.items.count()} items",
        )
        return redirect(
            "operations:checklist_run",
            property_slug=property_obj.slug,
            pk=run.pk,
        )
    return redirect(
        "operations:checklist_list",
        property_slug=property_obj.slug,
    )
@login_required
def checklist_run(request, property_slug, pk):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    run = get_object_or_404(
        ChecklistRun.objects.select_related(
            "checklist",
        ),
        pk=pk,
        checklist__property=property_obj,
    )
    items = run.checklist.items.all()
    completed_item_ids = set(
        run.completions.values_list(
            "item_id",
            flat=True,
        )
    )
    total_items = items.count()
    completed_count = len(completed_item_ids)
    context = {
        "property": property_obj,
        "run": run,
        "items": items,
        "completed_item_ids": completed_item_ids,
        "total_items": total_items,
        "completed_count": completed_count,
        "active_page": "checklists",
    }
    return render(
        request,
        "operations/checklist_run.html",
        context,
    )
@login_required
def checklist_item_toggle(request, property_slug, run_pk, item_pk):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    run = get_object_or_404(
        ChecklistRun,
        pk=run_pk,
        checklist__property=property_obj,
    )
    item = get_object_or_404(
        ChecklistItem,
        pk=item_pk,
        checklist=run.checklist,
    )
    if request.method == "POST":
        completion = ChecklistCompletion.objects.filter(
            run=run,
            item=item,
        ).first()
        if completion:
            completion.delete()
        else:
            ChecklistCompletion.objects.create(
                run=run,
                item=item,
                completed_by=(
                    request.user
                    if request.user.is_authenticated
                    else None
                ),
            )
    return redirect(
        "operations:checklist_run",
        property_slug=property_obj.slug,
        pk=run.pk,
    )
@login_required
def checklist_complete(request, property_slug, pk):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    run = get_object_or_404(
        ChecklistRun,
        pk=pk,
        checklist__property=property_obj,
    )
    if request.method == "POST":
        required_items = run.checklist.items.filter(
            is_required=True,
        )
        required_ids = set(
            required_items.values_list(
                "id",
                flat=True,
            )
        )
        completed_ids = set(
            run.completions.values_list(
                "item_id",
                flat=True,
            )
        )
        if (
            required_ids.issubset(completed_ids)
            and run.completed_at is None
        ):
            run.completed_at = timezone.now()
            run.save(
                update_fields=[
                    "completed_at",
                ]
            )
            log_activity(
                property_obj=property_obj,
                event_type=ActivityLog.EventType.CHECKLIST_COMPLETED,
                title=run.checklist.name,
                user=request.user,
            )
    return redirect(
        "operations:checklist_run",
        property_slug=property_obj.slug,
        pk=run.pk,
    )
@login_required
def team_list(request, property_slug):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    memberships = (
        PropertyMembership.objects
        .filter(property=property_obj)
        .select_related("user")
    )
    context = {
        "property": property_obj,
        "memberships": memberships,
        "active_page": "team",
    }
    return render(
        request,
        "operations/team_list.html",
        context,
    )
@login_required
def team_member_create(request, property_slug):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    if request.method == "POST":
        form = TeamMemberCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            PropertyMembership.objects.create(
                property=property_obj,
                user=user,
                role=form.cleaned_data["role"],
                job_title=form.cleaned_data["job_title"],
            )
            log_activity(
                property_obj=property_obj,
                event_type=ActivityLog.EventType.TEAM_MEMBER_ADDED,
                title=user.get_full_name() or user.username,
                user=request.user,
                detail=form.cleaned_data["role"],
            )
            return redirect(
                "operations:team_list",
                property_slug=property_obj.slug,
            )
    else:
        form = TeamMemberCreateForm()
    context = {
        "property": property_obj,
        "form": form,
        "active_page": "team",
    }
    return render(
        request,
        "operations/team_form.html",
        context,
    )
@login_required
def team_member_edit(request, property_slug, pk):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    membership = get_object_or_404(
        PropertyMembership.objects.select_related(
            "user",
        ),
        pk=pk,
        property=property_obj,
    )
    if request.method == "POST":
        form = MembershipEditForm(
            request.POST,
            instance=membership,
        )
        if form.is_valid():
            form.save()
            return redirect(
                "operations:team_list",
                property_slug=property_obj.slug,
            )
    else:
        form = MembershipEditForm(
            instance=membership,
        )
    context = {
        "property": property_obj,
        "membership": membership,
        "form": form,
        "active_page": "team",
        "form_mode": "edit",
    }
    return render(
        request,
        "operations/team_form.html",
        context,
    )
@login_required
def checklist_manage(request, property_slug):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    checklists = (
        Checklist.objects
        .filter(property=property_obj)
        .prefetch_related("items")
        .order_by("name")
    )
    context = {
        "property": property_obj,
        "checklists": checklists,
        "active_page": "checklists",
    }
    return render(
        request,
        "operations/checklist_manage.html",
        context,
    )
@login_required
def checklist_create(request, property_slug):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    if request.method == "POST":
        form = ChecklistForm(request.POST)
        if form.is_valid():
            checklist = form.save(commit=False)
            checklist.property = property_obj
            checklist.save()
            return redirect(
                "operations:checklist_edit",
                property_slug=property_obj.slug,
                pk=checklist.pk,
            )
    else:
        form = ChecklistForm()
    context = {
        "property": property_obj,
        "form": form,
        "active_page": "checklists",
    }
    return render(
        request,
        "operations/checklist_form.html",
        context,
    )
@login_required
def checklist_edit(request, property_slug, pk):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    checklist = get_object_or_404(
        Checklist,
        pk=pk,
        property=property_obj,
    )
    if request.method == "POST":
        form = ChecklistForm(
            request.POST,
            instance=checklist,
        )
        if form.is_valid():
            form.save()
            return redirect(
                "operations:checklist_edit",
                property_slug=property_obj.slug,
                pk=checklist.pk,
            )
    else:
        form = ChecklistForm(
            instance=checklist,
        )
    items = checklist.items.all()
    context = {
        "property": property_obj,
        "checklist": checklist,
        "items": items,
        "form": form,
        "active_page": "checklists",
        "form_mode": "edit",
    }
    return render(
        request,
        "operations/checklist_form.html",
        context,
    )
@login_required
def checklist_item_create(request, property_slug, checklist_pk):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    checklist = get_object_or_404(
        Checklist,
        pk=checklist_pk,
        property=property_obj,
    )
    if request.method == "POST":
        form = ChecklistItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.checklist = checklist
            item.save()
            return redirect(
                "operations:checklist_edit",
                property_slug=property_obj.slug,
                pk=checklist.pk,
            )
    else:
        form = ChecklistItemForm()
    context = {
        "property": property_obj,
        "checklist": checklist,
        "form": form,
        "active_page": "checklists",
    }
    return render(
        request,
        "operations/checklist_item_form.html",
        context,
    )
@login_required
def checklist_item_edit(
    request,
    property_slug,
    checklist_pk,
    item_pk,
):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    checklist = get_object_or_404(
        Checklist,
        pk=checklist_pk,
        property=property_obj,
    )
    item = get_object_or_404(
        ChecklistItem,
        pk=item_pk,
        checklist=checklist,
    )
    if request.method == "POST":
        form = ChecklistItemForm(
            request.POST,
            instance=item,
        )
        if form.is_valid():
            form.save()
            return redirect(
                "operations:checklist_edit",
                property_slug=property_obj.slug,
                pk=checklist.pk,
            )
    else:
        form = ChecklistItemForm(
            instance=item,
        )
    context = {
        "property": property_obj,
        "checklist": checklist,
        "item": item,
        "form": form,
        "active_page": "checklists",
        "form_mode": "edit",
    }
    return render(
        request,
        "operations/checklist_item_form.html",
        context,
    )
@login_required
def checklist_item_delete(
    request,
    property_slug,
    checklist_pk,
    item_pk,
):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    checklist = get_object_or_404(
        Checklist,
        pk=checklist_pk,
        property=property_obj,
    )
    item = get_object_or_404(
        ChecklistItem,
        pk=item_pk,
        checklist=checklist,
    )
    if request.method == "POST":
        item.delete()
    return redirect(
        "operations:checklist_edit",
        property_slug=property_obj.slug,
        pk=checklist.pk,
    )
@login_required
@require_POST
def checklist_item_reorder(request, property_slug, checklist_pk):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    checklist = get_object_or_404(
        Checklist,
        pk=checklist_pk,
        property=property_obj,
    )
    try:
        data = json.loads(request.body)
        item_ids = data.get("item_ids", [])
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON"},
            status=400,
        )
    valid_items = {
        item.id: item
        for item in checklist.items.filter(
            id__in=item_ids,
        )
    }
    if len(valid_items) != len(item_ids):
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid checklist item.",
            },
            status=400,
        )
    for index, item_id in enumerate(
        item_ids,
        start=1,
    ):
        item = valid_items[item_id]
        item.order = index * 10
        item.save(update_fields=["order"])
    return JsonResponse(
        {"success": True}
    )
@login_required
def recurring_task_list(request, property_slug):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    recurring_tasks = (
        RecurringTask.objects
        .filter(property=property_obj)
        .select_related("assigned_to")
    )
    context = {
        "property": property_obj,
        "recurring_tasks": recurring_tasks,
        "active_page": "tasks",
    }
    return render(
        request,
        "operations/recurring_task_list.html",
        context,
    )
@login_required
def recurring_task_create(request, property_slug):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    if request.method == "POST":
        form = RecurringTaskForm(
            request.POST,
            property_obj=property_obj,
        )
        if form.is_valid():
            recurring_task = form.save(commit=False)
            recurring_task.property = property_obj
            recurring_task.save()
            return redirect(
                "operations:recurring_task_list",
                property_slug=property_obj.slug,
            )
    else:
        form = RecurringTaskForm(
            property_obj=property_obj,
        )
    context = {
        "property": property_obj,
        "form": form,
        "active_page": "tasks",
    }
    return render(
        request,
        "operations/recurring_task_form.html",
        context,
    )
@login_required
def recurring_task_generate_today(request, property_slug):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    if request.method == "POST":
        generate_recurring_tasks_for_date(
            timezone.localdate(),
            property_obj=property_obj,
        )
    return redirect(
        "operations:task_list",
        property_slug=property_obj.slug,
    )
@login_required
def recurring_task_edit(request, property_slug, pk):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    recurring_task = get_object_or_404(
        RecurringTask,
        pk=pk,
        property=property_obj,
    )
    if request.method == "POST":
        form = RecurringTaskForm(
            request.POST,
            instance=recurring_task,
            property_obj=property_obj,
        )
        if form.is_valid():
            form.save()
            return redirect(
                "operations:recurring_task_list",
                property_slug=property_obj.slug,
            )
    else:
        form = RecurringTaskForm(
            instance=recurring_task,
            property_obj=property_obj,
        )
    context = {
        "property": property_obj,
        "form": form,
        "recurring_task": recurring_task,
        "active_page": "tasks",
        "form_mode": "edit",
    }
    return render(
        request,
        "operations/recurring_task_form.html",
        context,
    )
@login_required
def recurring_task_toggle(request, property_slug, pk):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    recurring_task = get_object_or_404(
        RecurringTask,
        pk=pk,
        property=property_obj,
    )
    if request.method == "POST":
        recurring_task.is_active = not recurring_task.is_active
        recurring_task.save(
            update_fields=[
                "is_active",
                "updated_at",
            ]
        )
    return redirect(
        "operations:recurring_task_list",
        property_slug=property_obj.slug,
    )
@login_required
def recurring_task_delete(request, property_slug, pk):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    recurring_task = get_object_or_404(
        RecurringTask,
        pk=pk,
        property=property_obj,
    )
    if request.method == "POST":
        recurring_task.delete()
    return redirect(
        "operations:recurring_task_list",
        property_slug=property_obj.slug,
    )
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
def task_quick_assign(
    request,
    property_slug,
    task_pk,
):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    task = get_object_or_404(
        Task,
        pk=task_pk,
        property=property_obj,
    )
    if request.method == "POST":
        membership_id = request.POST.get(
            "membership_id"
        )
        previous_assignee_id = task.assigned_to_id
        if membership_id:
            membership = get_object_or_404(
                PropertyMembership,
                pk=membership_id,
                property=property_obj,
                is_active=True,
            )
            task.assigned_to = membership.user
            assigned_name = (
                membership.user.get_full_name()
                or membership.user.username
            )
        else:
            task.assigned_to = None
            assigned_name = "Unassigned"
        task.save(
            update_fields=[
                "assigned_to",
                "updated_at",
            ]
        )
        if task.assigned_to:
            detail = f"Assigned to {assigned_name}"
        else:
            detail = "Moved to unassigned work"
        if previous_assignee_id != task.assigned_to_id:
            log_activity(
                property_obj=property_obj,
                event_type=ActivityLog.EventType.TASK_ASSIGNED,
                title=task.title,
                user=request.user,
                detail=detail,
            )
            if task.assigned_to:
                create_notification(
                    property_obj=property_obj,
                    recipient=task.assigned_to,
                    title="Task assigned",
                    message=task.title,
                    task=task,
                )
    return redirect(
        "operations:dashboard",
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
@login_required
def organisation_account(
    request,
    organisation_slug,
):
    organisation, membership = (
        get_organisation_for_user(
            request.user,
            organisation_slug,
        )
    )
    pending_invitations = (
        OrganisationInvitation.objects
        .filter(
            organisation=organisation,
            is_active=True,
            accepted_at__isnull=True,
        )
        .order_by("-created_at")
    )
    properties = (
        organisation.properties
        .filter(is_active=True)
        .order_by("name")
    )
    organisation_memberships = (
        OrganisationMembership.objects
        .filter(
            organisation=organisation,
            is_active=True,
        )
        .select_related("user")
        .order_by(
            "role",
            "user__username",
        )
    )
    current_property = properties.first()
    context = {
        "organisation": organisation,
        "organisation_membership": membership,
        "property": current_property,
        "organisation_properties": properties,
        "organisation_memberships": organisation_memberships,
        "property_count": properties.count(),
        "active_page": "account",
        "pending_invitations": pending_invitations,
    }
    return render(
        request,
        "operations/organisation_account.html",
        context,
    )
@login_required
def organisation_property_create(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    current_property = (
        organisation.properties
        .filter(is_active=True)
        .order_by("name")
        .first()
    )
    if request.method == "POST":
        form = PropertyForm(
            request.POST,
        )
        if form.is_valid():
            property_obj = form.save(
                commit=False
            )
            property_obj.organisation = (
                organisation
            )
            base_slug = slugify(
                property_obj.name
            )
            slug = base_slug
            counter = 2
            while Property.objects.filter(
                slug=slug
            ).exists():
                slug = (
                    f"{base_slug}-{counter}"
                )
                counter += 1
            property_obj.slug = slug
            property_obj.save()
            # Give the creator management access
            # to the new property.
            PropertyMembership.objects.get_or_create(
                property=property_obj,
                user=request.user,
                defaults={
                    "role": PropertyMembership.Role.OWNER,
                    "is_active": True,
                },
            )
            return redirect(
                "operations:dashboard",
                property_slug=property_obj.slug,
            )
    else:
        form = PropertyForm()
    context = {
        "organisation": organisation,
        "property": current_property,
        "form": form,
        "active_page": "account",
    }
    return render(
        request,
        "operations/organisation_property_form.html",
        context,
    )
@login_required
def organisation_invite_member(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    current_property = (
        organisation.properties
        .filter(is_active=True)
        .order_by("name")
        .first()
    )
    if request.method == "POST":
        form = OrganisationInvitationForm(
            request.POST,
            organisation=organisation,
        )
        if form.is_valid():
            invitation = form.save(
                commit=False
            )
            invitation.organisation = (
                organisation
            )
            invitation.invited_by = (
                request.user
            )
            invitation.expires_at = (
                timezone.now()
                + timedelta(days=7)
            )
            invitation.save()
            form.save_m2m()
            accept_path = reverse(
                "operations:organisation_invitation_accept",
                kwargs={
                    "token": invitation.token,
                },
            )
            accept_url = request.build_absolute_uri(
                accept_path
            )
            inviter_name = (
                request.user.get_full_name()
                or request.user.username
            )
            subject = (
                f"You're invited to join "
                f"{organisation.name} on RK Ops"
            )
            property_names = list(
                invitation.properties
                .values_list(
                    "name",
                    flat=True,
                )
            )
            if property_names:
                property_text = ", ".join(
                    property_names
                )
            else:
                property_text = "No property access"
            message = (
                f"{inviter_name} has invited you to join "
                f"{organisation.name} on RK Ops.\n\n"
                f"Organisation role: "
                f"{invitation.get_role_display()}\n"
                f"Property role: "
                f"{invitation.get_property_role_display()}\n\n"
                f"Property access: {property_text}\n\n"
                f"Accept your invitation:\n"
                f"{accept_url}\n\n"
                f"If you weren't expecting this invitation, "
                f"you can ignore this email."
            )
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[
                    invitation.email,
                ],
                fail_silently=False,
            )
            return redirect(
                "operations:organisation_account",
                organisation_slug=organisation.slug,
            )
    else:
        form = OrganisationInvitationForm(
            organisation=organisation,
        )
    return render(
        request,
        "operations/organisation_invitation_form.html",
        {
            "organisation": organisation,
            "property": current_property,
            "form": form,
            "active_page": "account",
        },
    )
def accept_organisation_invitation(
    *,
    invitation,
    user,
):
    organisation_membership, created = (
        OrganisationMembership.objects.get_or_create(
            organisation=invitation.organisation,
            user=user,
            defaults={
                "role": invitation.role,
                "is_active": True,
            },
        )
    )
    if not created:
        organisation_membership.role = invitation.role
        organisation_membership.is_active = True
        organisation_membership.save(
            update_fields=[
                "role",
                "is_active",
            ]
        )
    for property_obj in invitation.properties.all():
        PropertyMembership.objects.update_or_create(
            property=property_obj,
            user=user,
            defaults={
                "role": invitation.property_role,
                "is_active": True,
            },
        )
        log_activity(
            property_obj=property_obj,
            event_type=ActivityLog.EventType.TEAM_MEMBER_ADDED,
            title=(
                user.get_full_name()
                or user.username
            ),
            user=invitation.invited_by,
            detail="Joined via organisation invitation",
        )
    invitation.accepted_at = timezone.now()
    invitation.is_active = False
    invitation.save(
        update_fields=[
            "accepted_at",
            "is_active",
        ]
    )
@login_required
def organisation_invitation_accept(
    request,
    token,
):
    invitation = get_object_or_404(
        OrganisationInvitation.objects.select_related(
            "organisation",
            "invited_by",
        ),
        token=token,
        is_active=True,
        accepted_at__isnull=True,
    )
    # -----------------------------------------------
    # Invitation validity
    # -----------------------------------------------
    if invitation.revoked_at:
        raise PermissionDenied(
            "This invitation has been revoked."
        )
    if invitation.is_expired:
        raise PermissionDenied(
            "This invitation has expired."
        )
    # -----------------------------------------------
    # Make sure the logged-in account matches
    # the invited email address
    # -----------------------------------------------
    user_email = (
        request.user.email
        or ""
    ).strip().lower()
    invitation_email = (
        invitation.email
        or ""
    ).strip().lower()
    if user_email != invitation_email:
        raise PermissionDenied(
            "This invitation belongs to a different email address."
        )
    # -----------------------------------------------
    # Accept
    # -----------------------------------------------
    if request.method == "POST":
        accept_organisation_invitation(
            invitation=invitation,
            user=request.user,
        )
        first_property = (
            invitation.properties
            .filter(is_active=True)
            .order_by("name")
            .first()
        )
        if first_property:
            return redirect(
                "operations:dashboard",
                property_slug=first_property.slug,
            )
        return redirect(
            "operations:organisation_account",
            organisation_slug=invitation.organisation.slug,
        )
    # -----------------------------------------------
    # Page context
    # -----------------------------------------------
    current_property = (
        invitation.properties
        .filter(is_active=True)
        .order_by("name")
        .first()
    )
    if current_property is None:
        current_property = (
            invitation.organisation.properties
            .filter(is_active=True)
            .order_by("name")
            .first()
        )
    context = {
        "invitation": invitation,
        "organisation": invitation.organisation,
        "property": current_property,
    }
    return render(
        request,
        "operations/organisation_invitation_accept.html",
        context,
    )
def organisation_invitation_signup(
    request,
    token,
):
    invitation = get_object_or_404(
        OrganisationInvitation.objects.select_related(
            "organisation",
        ),
        token=token,
        is_active=True,
        accepted_at__isnull=True,
    )
    if invitation.revoked_at:
        raise PermissionDenied(
            "This invitation has been revoked."
        )
    if invitation.is_expired:
        raise PermissionDenied(
            "This invitation has expired."
        )
    invited_email = invitation.email.strip().lower()
    existing_user = (
        User.objects
        .filter(
            email__iexact=invited_email,
        )
        .first()
    )
    if existing_user:
        accept_url = reverse(
            "operations:organisation_invitation_accept",
            kwargs={
                "token": invitation.token,
            },
        )
        login_url = reverse("login")
        return redirect(
            f"{login_url}?next={accept_url}"
        )
    if request.method == "POST":
        form = InvitationSignupForm(
            request.POST,
        )
        if form.is_valid():
            user = form.save(
                commit=False
            )
            user.email = invited_email
            base_username = (
                invited_email
                .split("@")[0]
                .replace(".", "")
                .replace("-", "")
            )
            username = base_username
            counter = 2
            while User.objects.filter(
                username=username
            ).exists():
                username = (
                    f"{base_username}{counter}"
                )
                counter += 1
            user.username = username
            user.set_password(
                form.cleaned_data["password1"]
            )
            user.save()
            login(
                request,
                user,
                backend="django.contrib.auth.backends.ModelBackend",
            )
            accept_organisation_invitation(
                invitation=invitation,
                user=user,
            )
            first_property = (
                invitation.properties
                .filter(is_active=True)
                .order_by("name")
                .first()
            )
            if first_property:
                return redirect(
                    "operations:dashboard",
                    property_slug=first_property.slug,
                )
            return redirect(
                "operations:organisation_account",
                organisation_slug=invitation.organisation.slug,
            )
    else:
        form = InvitationSignupForm()
    return render(
        request,
        "operations/organisation_invitation_signup.html",
        {
            "form": form,
            "invitation": invitation,
            "organisation": invitation.organisation,
        },
    )
@login_required
def organisation_invitation_revoke(
    request,
    organisation_slug,
    invitation_pk,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    invitation = get_object_or_404(
        OrganisationInvitation,
        pk=invitation_pk,
        organisation=organisation,
        accepted_at__isnull=True,
    )
    if request.method == "POST":
        invitation.is_active = False
        invitation.revoked_at = timezone.now()
        invitation.save(
            update_fields=[
                "is_active",
                "revoked_at",
            ]
        )
    return redirect(
        "operations:organisation_account",
        organisation_slug=organisation.slug,
    )
@login_required
def organisation_invitation_resend(
    request,
    organisation_slug,
    invitation_pk,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    invitation = get_object_or_404(
        OrganisationInvitation,
        pk=invitation_pk,
        organisation=organisation,
        accepted_at__isnull=True,
    )
    if request.method == "POST":
        invitation.is_active = True
        invitation.revoked_at = None
        invitation.expires_at = (
            timezone.now()
            + timedelta(days=7)
        )
        invitation.save(
            update_fields=[
                "is_active",
                "revoked_at",
                "expires_at",
            ]
        )
        accept_path = reverse(
            "operations:organisation_invitation_signup",
            kwargs={
                "token": invitation.token,
            },
        )
        accept_url = request.build_absolute_uri(
            accept_path
        )
        inviter_name = (
            request.user.get_full_name()
            or request.user.username
        )
        property_names = list(
            invitation.properties
            .values_list(
                "name",
                flat=True,
            )
        )
        property_text = (
            ", ".join(property_names)
            if property_names
            else "No property access"
        )
        subject = (
            f"Reminder: you're invited to join "
            f"{organisation.name} on RK Ops"
        )
        message = (
            f"{inviter_name} has invited you to join "
            f"{organisation.name} on RK Ops.\n\n"
            f"Organisation role: "
            f"{invitation.get_role_display()}\n"
            f"Property role: "
            f"{invitation.get_property_role_display()}\n"
            f"Property access: "
            f"{property_text}\n\n"
            f"Accept your invitation:\n"
            f"{accept_url}\n\n"
            f"This invitation expires in 7 days."
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[
                invitation.email,
            ],
            fail_silently=False,
        )
    return redirect(
        "operations:organisation_account",
        organisation_slug=organisation.slug,
    )
