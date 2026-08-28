from django.conf import settings
from django.db import models
from properties.models import Property
class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
    class Category(models.TextChoices):
        FRONT_OFFICE = "front_office", "Front Office"
        HOUSEKEEPING = "housekeeping", "Housekeeping"
        MAINTENANCE = "maintenance", "Maintenance"
        FOOD_BEVERAGE = "food_beverage", "Food & Beverage"
        MANAGEMENT = "management", "Management"
        OTHER = "other", "Other"
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.OTHER,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_ops_tasks",
    )
    due_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    recurring_source = models.ForeignKey(
        "RecurringTask",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_tasks",
    )
    scheduled_date = models.DateField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["due_at", "-priority", "-created_at"]
    def __str__(self):
        return self.title
class Issue(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"
    class Category(models.TextChoices):
        MAINTENANCE = "maintenance", "Maintenance"
        HOUSEKEEPING = "housekeeping", "Housekeeping"
        GUEST = "guest", "Guest Issue"
        SAFETY = "safety", "Safety"
        TECHNOLOGY = "technology", "Technology"
        FOOD_BEVERAGE = "food_beverage", "Food & Beverage"
        OTHER = "other", "Other"
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="issues",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    location = models.CharField(
        max_length=150,
        blank=True,
        help_text="e.g. Room 204, Reception, Kitchen",
    )
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.OTHER,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_ops_issues",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    resolution_notes = models.TextField(blank=True)
    reported_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-priority", "-reported_at"]
    def __str__(self):
        return self.title
class HandoverNote(models.Model):
    class Shift(models.TextChoices):
        MORNING = "morning", "Morning"
        AFTERNOON = "afternoon", "Afternoon"
        EVENING = "evening", "Evening"
        NIGHT = "night", "Night"
        GENERAL = "general", "General"
    class Priority(models.TextChoices):
        NORMAL = "normal", "Normal"
        IMPORTANT = "important", "Important"
        URGENT = "urgent", "Urgent"
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="handover_notes",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ops_handover_notes",
    )
    shift = models.CharField(
        max_length=20,
        choices=Shift.choices,
        default=Shift.GENERAL,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    note = models.TextField()
    is_resolved = models.BooleanField(
        default=False,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    class Meta:
        ordering = [
            "is_resolved",
            "-created_at",
        ]
    def __str__(self):
        return self.note[:60]
class Checklist(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="checklists",
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["name"]
    def __str__(self):
        return self.name
class ChecklistItem(models.Model):
    checklist = models.ForeignKey(
        Checklist,
        on_delete=models.CASCADE,
        related_name="items",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    class Meta:
        ordering = ["order", "id"]
    def __str__(self):
        return self.title
class ChecklistRun(models.Model):
    checklist = models.ForeignKey(
        Checklist,
        on_delete=models.CASCADE,
        related_name="runs",
    )
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ops_checklist_runs",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    class Meta:
        ordering = ["-started_at"]
    @property
    def is_complete(self):
        return self.completed_at is not None
    def __str__(self):
        return f"{self.checklist.name} - {self.started_at:%d %b %Y}"
class ChecklistCompletion(models.Model):
    run = models.ForeignKey(
        ChecklistRun,
        on_delete=models.CASCADE,
        related_name="completions",
    )
    item = models.ForeignKey(
        ChecklistItem,
        on_delete=models.CASCADE,
        related_name="completions",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ops_checklist_completions",
    )
    completed_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run", "item"],
                name="unique_checklist_run_item_completion",
            )
        ]
    def __str__(self):
        return f"{self.run} - {self.item.title}"
class RecurringTask(models.Model):
    class Frequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="recurring_tasks",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=30,
        choices=Task.Category.choices,
        default=Task.Category.OTHER,
    )
    priority = models.CharField(
        max_length=20,
        choices=Task.Priority.choices,
        default=Task.Priority.MEDIUM,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_recurring_ops_tasks",
    )
    frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.DAILY,
    )
    weekday = models.PositiveSmallIntegerField(
        choices=Weekday.choices,
        null=True,
        blank=True,
    )
    due_time = models.TimeField(
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["title"]
    def __str__(self):
        return self.title