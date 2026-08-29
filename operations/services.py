from datetime import datetime
from django.utils import timezone
from .activity import log_activity
from .models import ActivityLog, RecurringTask, Task
def generate_recurring_tasks_for_date(
    target_date,
    property_obj=None,
):
    recurring_tasks = (
        RecurringTask.objects
        .filter(
            is_active=True,
            property__is_active=True,
        )
        .select_related(
            "property",
            "assigned_to",
        )
    )
    if property_obj is not None:
        recurring_tasks = recurring_tasks.filter(
            property=property_obj,
        )
    created_count = 0
    skipped_count = 0
    for recurring in recurring_tasks:
        should_generate = False
        if recurring.frequency == RecurringTask.Frequency.DAILY:
            should_generate = True
        elif (
            recurring.frequency == RecurringTask.Frequency.WEEKLY
            and recurring.weekday == target_date.weekday()
        ):
            should_generate = True
        if not should_generate:
            continue
        already_exists = Task.objects.filter(
            property=recurring.property,
            recurring_source=recurring,
            scheduled_date=target_date,
        ).exists()
        if already_exists:
            skipped_count += 1
            continue
        due_at = None
        if recurring.due_time:
            naive_due = datetime.combine(
                target_date,
                recurring.due_time,
            )
            due_at = timezone.make_aware(
                naive_due,
                timezone.get_current_timezone(),
            )
        Task.objects.create(
            property=recurring.property,
            recurring_source=recurring,
            scheduled_date=target_date,
            title=recurring.title,
            description=recurring.description,
            category=recurring.category,
            priority=recurring.priority,
            assigned_to=recurring.assigned_to,
            due_at=due_at,
            status=Task.Status.OPEN,
        )
        recurring.last_generated_at = timezone.now()
        recurring.last_generated_for = target_date
        recurring.save(
            update_fields=[
                "last_generated_at",
                "last_generated_for",
                "updated_at",
            ]
        )
        detail = "Generated automatically"
        if recurring.due_time:
            detail += f" · Due {recurring.due_time.strftime('%H:%M')}"
        log_activity(
            property_obj=recurring.property,
            event_type=ActivityLog.EventType.RECURRING_GENERATED,
            title=recurring.title,
            user=None,
            detail=detail,
        )
        created_count += 1
    return created_count, skipped_count