from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from operations.models import (
    ActivityLog,
    ChecklistRun,
    HandoverNote,
    Issue,
    Task,
)
from accounts.models import (
    PropertyMembership,
)
from operations.utils import (
    get_property_for_user,
)
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)
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