from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from properties.models import Property
from .models import Task
from django.shortcuts import get_object_or_404, redirect, render
from .forms import TaskForm
from .forms import HandoverNoteForm, IssueForm, TaskForm
from .models import HandoverNote, Issue, Task
def dashboard(request):
    property_obj = get_object_or_404(
        Property,
        slug="willowmere-house",
        is_active=True,
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
def task_list(request):
    property_obj = get_object_or_404(
        Property,
        slug="willowmere-house",
        is_active=True,
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
    return render(
        request,
        "operations/task_list.html",
        context,
    )
def task_create(request):
    property_obj = get_object_or_404(
        Property,
        slug="willowmere-house",
        is_active=True,
    )
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.property = property_obj
            task.save()
            return redirect("operations:task_list")
    else:
        form = TaskForm()
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
def task_edit(request, pk):
    property_obj = get_object_or_404(
        Property,
        slug="willowmere-house",
        is_active=True,
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
            return redirect("operations:task_list")
    else:
        form = TaskForm(instance=task)
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
def task_complete(request, pk):
    property_obj = get_object_or_404(
        Property,
        slug="willowmere-house",
        is_active=True,
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
    return redirect("operations:task_list")
def issue_list(request):
    property_obj = get_object_or_404(
        Property,
        slug="willowmere-house",
        is_active=True,
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
def issue_create(request):
    property_obj = get_object_or_404(
        Property,
        slug="willowmere-house",
        is_active=True,
    )
    if request.method == "POST":
        form = IssueForm(request.POST)
        if form.is_valid():
            issue = form.save(commit=False)
            issue.property = property_obj
            issue.save()
            return redirect("operations:issue_list")
    else:
        form = IssueForm()
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
def issue_edit(request, pk):
    property_obj = get_object_or_404(
        Property,
        slug="willowmere-house",
        is_active=True,
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
            return redirect("operations:issue_list")
    else:
        form = IssueForm(instance=issue)
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
def issue_resolve(request, pk):
    property_obj = get_object_or_404(
        Property,
        slug="willowmere-house",
        is_active=True,
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
    return redirect("operations:issue_list")
def handover_list(request):
    property_obj = get_object_or_404(
        Property,
        slug="willowmere-house",
        is_active=True,
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
def handover_create(request):
    property_obj = get_object_or_404(
        Property,
        slug="willowmere-house",
        is_active=True,
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
                "operations:handover_list"
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
def handover_resolve(request, pk):
    property_obj = get_object_or_404(
        Property,
        slug="willowmere-house",
        is_active=True,
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
        "operations:handover_list"
    )