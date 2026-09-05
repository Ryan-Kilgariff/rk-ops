from django.contrib import admin
from .models import (
    Checklist,
    ChecklistCompletion,
    ChecklistItem,
    ChecklistRun,
    HandoverNote,
    Issue,
    RecurringTask,
    Task,
)
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "property",
        "category",
        "priority",
        "status",
        "assigned_to",
        "due_at",
    )
    list_filter = (
        "property",
        "category",
        "priority",
        "status",
    )
    search_fields = (
        "title",
        "description",
        "property__name",
    )
    raw_id_fields = ("assigned_to",)
    date_hierarchy = "due_at"
@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "property",
        "location",
        "category",
        "priority",
        "status",
        "assigned_to",
        "reported_at",
    )
    list_filter = (
        "property",
        "category",
        "priority",
        "status",
    )
    search_fields = (
        "title",
        "description",
        "location",
        "property__name",
    )
    raw_id_fields = ("assigned_to",)
class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 1
@admin.register(Checklist)
class ChecklistAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "property",
        "is_active",
        "created_at",
    )
    list_filter = (
        "property",
        "is_active",
    )
    search_fields = (
        "name",
        "description",
    )
    inlines = [
        ChecklistItemInline,
    ]
@admin.register(ChecklistRun)
class ChecklistRunAdmin(admin.ModelAdmin):
    list_display = (
        "checklist",
        "started_by",
        "started_at",
        "completed_at",
    )
    list_filter = (
        "checklist",
    )
@admin.register(ChecklistCompletion)
class ChecklistCompletionAdmin(admin.ModelAdmin):
    list_display = (
        "run",
        "item",
        "completed_by",
        "completed_at",
    )
@admin.register(RecurringTask)
class RecurringTaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "property",
        "frequency",
        "weekday",
        "due_time",
        "is_active",
        "last_generated_for",
        "last_generated_at",
    )
    list_filter = (
        "property",
        "frequency",
        "is_active",
    )
    search_fields = (
        "title",
        "description",
        "property__name",
    )
    raw_id_fields = (
        "assigned_to",
    )
    ordering = (
        "property__name",
        "title",
    )