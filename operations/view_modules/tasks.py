from django.contrib.auth.decorators import login_required
from operations.activity import log_activity
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from operations.notifications import create_notification
from operations.services import (
    generate_recurring_tasks_for_date,
)
from operations.forms import (
    TaskForm,
    RecurringTaskForm,
)
from operations.models import (
    ActivityLog,
    Task,
    RecurringTask
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
