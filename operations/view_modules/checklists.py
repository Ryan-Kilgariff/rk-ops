from django.contrib.auth.decorators import login_required
from operations.activity import log_activity
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
from operations.forms import (
    ChecklistForm,
    ChecklistItemForm,
)
from operations.models import (
    ActivityLog,
    Checklist,
    ChecklistCompletion,
    ChecklistItem,
    ChecklistRun,
)
from operations.utils import (
    get_property_for_user,
    require_management_access,
)
from django.utils import timezone
from django.http import JsonResponse
import logging
logger = logging.getLogger(__name__)
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
