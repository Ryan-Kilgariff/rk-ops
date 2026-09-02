from django.contrib.auth.decorators import login_required
from operations.activity import log_activity
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from operations.forms import (
    HandoverNoteForm,
)
from operations.models import (
    ActivityLog,
    HandoverNote,
    Issue,
)
from operations.utils import (
    get_property_for_user,
)
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)
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
