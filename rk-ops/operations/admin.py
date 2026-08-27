from django.contrib import admin
from .models import Issue, Task
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