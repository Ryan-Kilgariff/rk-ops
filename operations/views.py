from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from properties.models import Property
from .models import Task
from django.shortcuts import get_object_or_404, redirect, render
from .forms import TaskForm
from .forms import HandoverNoteForm, IssueForm, TaskForm
from .models import (
    Checklist,
    ChecklistCompletion,
    ChecklistRun,
    ChecklistItem,
    HandoverNote,
    Issue,
    Task,
)
from accounts.forms import (
    MembershipEditForm,
    TeamMemberCreateForm,
)
from accounts.models import PropertyMembership
from django.contrib.auth.decorators import login_required
from .utils import (
    get_property_for_user,
    require_management_access,
    require_supervisory_access,
)
@login_required
def dashboard(request, property_slug):
    property_obj, membership = get_property_for_user(
        request.user,
        property_slug
    )
    now = timezone.now()
    today = timezone.localdate()
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
    overdue_tasks = open_tasks.filter(
        due_at__lt=now,
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
    urgent_items = (
        open_tasks.filter(
            priority=Task.Priority.URGENT,
        ).count()
        +
        open_issues.filter(
            priority=Issue.Priority.URGENT,
        ).count()
    )
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
    }
    return render(
        request,
        "operations/dashboard.html",
        context,
    )
@login_required
def property_home(request):
    if request.user.is_superuser:
        property_obj = (
            Property.objects
            .filter(is_active=True)
            .order_by("name")
            .first()
        )
    else:
        membership = (
            PropertyMembership.objects
            .filter(
                user=request.user,
                is_active=True,
                property__is_active=True,
            )
            .select_related("property")
            .order_by("property__name")
            .first()
        )
        property_obj = (
            membership.property
            if membership
            else None
        )
    if not property_obj:
        raise PermissionDenied(
            "You do not have access to an active property."
        )
    return redirect(
        "operations:dashboard",
        property_slug=property_obj.slug,
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
        "tasks": tasks,
        "status_filter": status_filter,
        "priority_filter": priority_filter,
        "status_choices": Task.Status.choices,
        "priority_choices": Task.Priority.choices,
        "active_page": "tasks",
    }
    return redirect(
        "operations:task_list",
        property_slug=property_obj.slug,
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
        task.status = Task.Status.COMPLETED
        task.completed_at = timezone.now()
        task.save(
            update_fields=[
                "status",
                "completed_at",
                "updated_at",
            ]
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
        if required_ids.issubset(completed_ids):
            run.completed_at = timezone.now()
            run.save(
                update_fields=[
                    "completed_at",
                ]
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