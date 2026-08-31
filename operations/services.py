from datetime import datetime
from django.utils import timezone
from .activity import log_activity
from .models import ActivityLog, RecurringTask, Task
from .notifications import create_notification
from properties.models import OrganisationSubscription
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
def update_task_escalations(property_obj=None):
    tasks = (
        Task.objects
        .filter(
            due_at__isnull=False,
            property__is_active=True,
        )
        .exclude(
            status__in=[
                Task.Status.COMPLETED,
                Task.Status.CANCELLED,
            ]
        )
    )
    if property_obj is not None:
        tasks = tasks.filter(
            property=property_obj,
        )
    now = timezone.now()
    updated_count = 0
    for task in tasks:
        if task.due_at >= now:
            new_level = Task.EscalationLevel.NONE
        else:
            overdue_hours = (
                now - task.due_at
            ).total_seconds() / 3600
            if overdue_hours >= 24:
                new_level = (
                    Task.EscalationLevel.CRITICAL
                )
            elif overdue_hours >= 8:
                new_level = (
                    Task.EscalationLevel.HIGH
                )
            elif overdue_hours >= 2:
                new_level = (
                    Task.EscalationLevel.WATCH
                )
            else:
                new_level = (
                    Task.EscalationLevel.NONE
                )
        if task.escalation_level != new_level:
            old_level = task.escalation_level
            task.escalation_level = new_level
            task.save(
                update_fields=[
                    "escalation_level",
                    "updated_at",
                ]
            )
            if new_level != Task.EscalationLevel.NONE:
                log_activity(
                    property_obj=task.property,
                    event_type=ActivityLog.EventType.TASK_ESCALATED,
                    title=task.title,
                    user=None,
                    detail=(
                        f"{task.get_escalation_level_display()} escalation"
                    ),
                )
                if (
                    task.assigned_to
                    and new_level in [
                        Task.EscalationLevel.HIGH,
                        Task.EscalationLevel.CRITICAL,
                    ]
                ):
                    create_notification(
                        property_obj=task.property,
                        recipient=task.assigned_to,
                        title=(
                            f"{task.get_escalation_level_display()} "
                            "task escalation"
                        ),
                        message=task.title,
                    )
            elif old_level != Task.EscalationLevel.NONE:
                log_activity(
                    property_obj=task.property,
                    event_type=ActivityLog.EventType.TASK_DEESCALATED,
                    title=task.title,
                    user=None,
                    detail="Escalation cleared",
                )
            updated_count += 1
    return updated_count
def update_subscription_statuses():
    subscriptions = (
        OrganisationSubscription.objects
        .select_related("organisation")
        .filter(
            organisation__is_active=True,
        )
    )
    now = timezone.now()
    updated_count = 0
    for subscription in subscriptions:
        new_status = subscription.status
        # ------------------------------------------
        # TRIAL EXPIRY
        # ------------------------------------------
        if (
            subscription.status
            == OrganisationSubscription.Status.TRIAL
            and subscription.trial_ends_at
            and subscription.trial_ends_at <= now
        ):
            new_status = (
                OrganisationSubscription.Status.SUSPENDED
            )
        # ------------------------------------------
        # ACTIVE PERIOD EXPIRY
        # ------------------------------------------
        elif (
            subscription.status
            == OrganisationSubscription.Status.ACTIVE
            and subscription.current_period_ends_at
            and subscription.current_period_ends_at <= now
        ):
            new_status = (
                OrganisationSubscription.Status.PAST_DUE
            )
        # ------------------------------------------
        # SAVE CHANGE
        # ------------------------------------------
        if new_status != subscription.status:
            subscription.status = new_status
            subscription.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )
            updated_count += 1
    return updated_count