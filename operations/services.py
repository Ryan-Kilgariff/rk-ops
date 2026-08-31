from datetime import datetime
from django.utils import timezone
from .activity import log_activity
from .models import ActivityLog, RecurringTask, Task
from .notifications import create_notification
from properties.models import (
    OrganisationBillingSession,
    OrganisationBillingEvent,
    OrganisationSubscription,
    OrganisationSubscriptionEvent,
)
from operations.billing import (
    get_billing_adapter,
)
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
def mark_subscription_past_due(
    subscription,
    *,
    reason="Subscription payment is past due.",
    changed_by=None,
):
    return change_subscription_status(
        subscription,
        OrganisationSubscription.Status.PAST_DUE,
        reason=reason,
        changed_by=changed_by,
    )
def suspend_subscription(
    subscription,
    *,
    reason="Subscription suspended.",
    changed_by=None,
):
    return change_subscription_status(
        subscription,
        OrganisationSubscription.Status.SUSPENDED,
        reason=reason,
        changed_by=changed_by,
    )
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
        # ------------------------------------------
        # TRIAL EXPIRY
        # ------------------------------------------
        if (
            subscription.status
            == OrganisationSubscription.Status.TRIAL
            and subscription.trial_ends_at
            and subscription.trial_ends_at <= now
        ):
            changed = suspend_subscription(
                subscription,
                reason="Trial period expired.",
            )
            if changed:
                updated_count += 1
            continue
        # ------------------------------------------
        # ACTIVE PERIOD EXPIRY
        # ------------------------------------------
        if (
            subscription.status
            == OrganisationSubscription.Status.ACTIVE
            and subscription.current_period_ends_at
            and subscription.current_period_ends_at <= now
        ):
            changed = mark_subscription_past_due(
                subscription,
                reason=(
                    "Subscription billing period expired."
                ),
            )
            if changed:
                updated_count += 1
    return updated_count
def change_subscription_status(
    subscription,
    new_status,
    *,
    reason="",
    changed_by=None,
):
    previous_status = subscription.status
    if previous_status == new_status:
        return False
    subscription.status = new_status
    subscription.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )
    OrganisationSubscriptionEvent.objects.create(
        organisation=subscription.organisation,
        subscription=subscription,
        event_type=(
            OrganisationSubscriptionEvent
            .EventType
            .STATUS_CHANGE
        ),
        previous_status=previous_status,
        new_status=new_status,
        reason=reason,
        changed_by=changed_by,
    )
    return True
def change_subscription_plan(
    subscription,
    new_plan,
    *,
    reason="",
    changed_by=None,
    sync_provider=True,
):
    previous_plan = subscription.plan
    if previous_plan == new_plan:
        return False
    if sync_provider:
        adapter = get_billing_adapter(
            subscription
        )
        adapter.change_plan(
            subscription,
            new_plan,
        )
    subscription.plan = new_plan
    subscription.save(
        update_fields=[
            "plan",
            "updated_at",
        ]
    )
    OrganisationSubscriptionEvent.objects.create(
        organisation=(
            subscription.organisation
        ),
        subscription=subscription,
        event_type=(
            OrganisationSubscriptionEvent
            .EventType
            .PLAN_CHANGE
        ),
        previous_plan=previous_plan,
        new_plan=new_plan,
        reason=reason,
        changed_by=changed_by,
    )
    return True
def activate_subscription(
    subscription,
    *,
    reason="Subscription activated.",
    changed_by=None,
):
    subscription.cancelled_at = None
    subscription.save(
        update_fields=[
            "cancelled_at",
            "updated_at",
        ]
    )
    return change_subscription_status(
        subscription,
        OrganisationSubscription.Status.ACTIVE,
        reason=reason,
        changed_by=changed_by,
    )
def cancel_subscription(
    subscription,
    *,
    reason="Subscription cancelled.",
    changed_by=None,
):
    adapter = get_billing_adapter(
        subscription
    )
    adapter.cancel_subscription(
        subscription
    )
    subscription.cancelled_at = (
        timezone.now()
    )
    subscription.current_period_ends_at = (
        None
    )
    subscription.save(
        update_fields=[
            "cancelled_at",
            "current_period_ends_at",
            "updated_at",
        ]
    )
    return change_subscription_status(
        subscription,
        OrganisationSubscription
        .Status
        .CANCELLED,
        reason=reason,
        changed_by=changed_by,
    )
def reactivate_subscription(
    subscription,
    *,
    reason="Subscription reactivated.",
    changed_by=None,
):
    adapter = get_billing_adapter(
        subscription
    )
    adapter.reactivate_subscription(
        subscription
    )
    subscription.cancelled_at = None
    subscription.save(
        update_fields=[
            "cancelled_at",
            "updated_at",
        ]
    )
    return change_subscription_status(
        subscription,
        OrganisationSubscription
        .Status
        .ACTIVE,
        reason=reason,
        changed_by=changed_by,
    )
def get_subscription_by_provider_subscription_id(
    provider,
    provider_subscription_id,
):
    return (
        OrganisationSubscription.objects
        .select_related("organisation")
        .filter(
            billing_provider=provider,
            provider_subscription_id=(
                provider_subscription_id
            ),
        )
        .first()
    )
def get_subscription_by_provider_customer_id(
    provider,
    provider_customer_id,
):
    return (
        OrganisationSubscription.objects
        .select_related("organisation")
        .filter(
            billing_provider=provider,
            provider_customer_id=(
                provider_customer_id
            ),
        )
        .first()
    )
def log_billing_event(
    subscription,
    event_type,
    *,
    amount=None,
    currency="GBP",
    provider_event_id="",
    provider_reference="",
    description="",
    metadata=None,
):
    return OrganisationBillingEvent.objects.create(
        organisation=subscription.organisation,
        subscription=subscription,
        event_type=event_type,
        amount=amount,
        currency=currency,
        provider=subscription.billing_provider,
        provider_event_id=provider_event_id,
        provider_reference=provider_reference,
        description=description,
        metadata=metadata or {},
    )
def create_billing_session(
    subscription,
    requested_plan,
):
    OrganisationBillingSession.objects.filter(
        subscription=subscription,
        status=OrganisationBillingSession.Status.PENDING,
    ).update(
        status=OrganisationBillingSession.Status.CANCELLED,
    )
    config = (
        OrganisationSubscription.PLAN_CONFIG[
            requested_plan
        ]
    )
    amount = config["monthly_price"]
    session = (
        OrganisationBillingSession.objects.create(
            organisation=subscription.organisation,
            subscription=subscription,
            requested_plan=requested_plan,
            amount=amount,
            currency="GBP",
            provider=subscription.billing_provider,
            status=(
                OrganisationBillingSession
                .Status
                .PENDING
            ),
        )
    )
    adapter = get_billing_adapter(
        subscription
    )
    provider_session = (
        adapter.create_checkout_session(
            session
        )
    )
    session.provider_session_id = (
        provider_session.get(
            "session_id",
            "",
        )
    )
    session.provider_checkout_url = (
        provider_session.get(
            "checkout_url",
            "",
        )
    )
    session.provider_reference = (
        provider_session.get(
            "reference",
            "",
        )
    )
    session.save(
        update_fields=[
            "provider_session_id",
            "provider_checkout_url",
            "provider_reference",
            "updated_at",
        ]
    )
    log_billing_event(
        subscription,
        OrganisationBillingEvent
        .EventType
        .CHECKOUT_CREATED,
        amount=amount,
        description=(
            "Billing checkout session created."
        ),
        metadata={
            "billing_session_id": session.pk,
            "requested_plan": requested_plan,
        },
    )
    return session