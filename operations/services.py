from datetime import datetime, timedelta
from django.utils import timezone
from .activity import log_activity
from django.urls import reverse
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
from decimal import Decimal, InvalidOperation
from django.db import (
    IntegrityError,
    transaction,
)
from accounts.models import (
    OrganisationInvitation,
    OrganisationMembership,
)
from operations.models import (
    Checklist,
    Task,
)
from properties.models import (
    OrganisationSubscription,
)
from django.utils.dateparse import parse_datetime
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
            metadata = (
                subscription.billing_metadata
                or {}
            )
            # --------------------------------------
            # SCHEDULED CANCELLATION
            # --------------------------------------
            if metadata.get(
                "cancel_at_period_end"
            ):
                metadata.pop(
                    "cancel_at_period_end",
                    None,
                )
                metadata.pop(
                    "cancel_requested_at",
                    None,
                )
                subscription.billing_metadata = (
                    metadata
                )
                subscription.save(
                    update_fields=[
                        "billing_metadata",
                        "updated_at",
                    ]
                )
                changed = (
                    change_subscription_status(
                        subscription,
                        OrganisationSubscription
                        .Status
                        .CANCELLED,
                        reason=(
                            "Paid subscription period "
                            "ended after cancellation."
                        ),
                    )
                )
                if changed:
                    updated_count += 1
                continue
            # --------------------------------------
            # NORMAL BILLING PERIOD EXPIRY
            # --------------------------------------
            changed = mark_subscription_past_due(
                subscription,
                reason=(
                    "Subscription billing "
                    "period expired."
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
    reason="",
    changed_by=None,
):
    now = timezone.now()
    is_trial = (
        subscription.status
        == OrganisationSubscription.Status.TRIAL
    )
    has_paid_period_remaining = (
        not is_trial
        and subscription.current_period_ends_at
        and subscription.current_period_ends_at > now
    )
    # --------------------------------------------------
    # PAID SUBSCRIPTION:
    # CANCEL PROVIDER RENEWAL BUT KEEP RK OPS ACCESS
    # UNTIL THE CURRENT PAID PERIOD ENDS
    # --------------------------------------------------
    if has_paid_period_remaining:
        metadata = (
            subscription.billing_metadata
            or {}
        )
        metadata["cancel_at_period_end"] = True
        metadata["cancel_requested_at"] = (
            now.isoformat()
        )
        subscription.billing_metadata = metadata
        subscription.cancelled_at = now
        subscription.save(
            update_fields=[
                "billing_metadata",
                "cancelled_at",
                "updated_at",
            ]
        )
        adapter = get_billing_adapter(
            subscription
        )
        try:
            result = adapter.cancel_subscription(
                subscription
            )
        except Exception:
            # Provider cancellation failed,
            # so remove the local cancellation request.
            metadata = (
                subscription.billing_metadata
                or {}
            )
            metadata.pop(
                "cancel_at_period_end",
                None,
            )
            metadata.pop(
                "cancel_requested_at",
                None,
            )
            subscription.billing_metadata = (
                metadata
            )
            subscription.cancelled_at = None
            subscription.save(
                update_fields=[
                    "billing_metadata",
                    "cancelled_at",
                    "updated_at",
                ]
            )
            raise
        # IMPORTANT:
        # Keep status ACTIVE and preserve
        # current_period_ends_at.
        return result
    # --------------------------------------------------
    # TRIAL OR NO PAID PERIOD REMAINING:
    # CANCEL IMMEDIATELY
    # --------------------------------------------------
    adapter = get_billing_adapter(
        subscription
    )
    result = adapter.cancel_subscription(
        subscription
    )
    subscription.cancelled_at = now
    subscription.current_period_ends_at = (
        None
    )
    metadata = (
        subscription.billing_metadata
        or {}
    )
    metadata.pop(
        "cancel_at_period_end",
        None,
    )
    metadata.pop(
        "cancel_requested_at",
        None,
    )
    subscription.billing_metadata = metadata
    subscription.save(
        update_fields=[
            "cancelled_at",
            "current_period_ends_at",
            "billing_metadata",
            "updated_at",
        ]
    )
    change_subscription_status(
        subscription,
        OrganisationSubscription
        .Status
        .CANCELLED,
        reason=(
            reason
            or (
                "Trial cancelled."
                if is_trial
                else "Subscription cancelled."
            )
        ),
        changed_by=changed_by,
    )
    return result
def reactivate_subscription(
    subscription,
    *,
    reason="",
    changed_by=None,
):
    adapter = get_billing_adapter(
        subscription
    )
    result = adapter.reactivate_subscription(
        subscription
    )
    if result.get("requires_checkout"):
        return {
            "requires_checkout": True,
        }
    if result.get("already_active"):
        metadata = (
            subscription.billing_metadata
            or {}
        )
        metadata.pop(
            "cancel_at_period_end",
            None,
        )
        metadata.pop(
            "cancel_requested_at",
            None,
        )
        subscription.billing_metadata = metadata
        subscription.cancelled_at = None
        subscription.save(
            update_fields=[
                "billing_metadata",
                "cancelled_at",
                "updated_at",
            ]
        )
        change_subscription_status(
            subscription,
            OrganisationSubscription
            .Status
            .ACTIVE,
            reason=reason,
            changed_by=changed_by,
        )
        return {
            "requires_checkout": False,
            "awaiting_provider_confirmation": False,
            "already_active": True,
        }
    if result.get(
        "awaiting_provider_confirmation"
    ):
        return {
            "requires_checkout": False,
            "awaiting_provider_confirmation": True,
        }
    metadata = (
        subscription.billing_metadata
        or {}
    )
    metadata.pop(
        "cancel_at_period_end",
        None,
    )
    metadata.pop(
        "cancel_requested_at",
        None,
    )
    subscription.billing_metadata = metadata
    subscription.cancelled_at = None
    subscription.save(
        update_fields=[
            "billing_metadata",
            "cancelled_at",
            "updated_at",
        ]
    )
    change_subscription_status(
        subscription,
        OrganisationSubscription
        .Status
        .ACTIVE,
        reason=reason,
        changed_by=changed_by,
    )
    return {
        "requires_checkout": False,
        "awaiting_provider_confirmation": False,
    }
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
    *,
    trial_signup=False,
):
    existing_session = (
        OrganisationBillingSession.objects
        .filter(
            subscription=subscription,
            requested_plan=requested_plan,
            provider=subscription.billing_provider,
            status=(
                OrganisationBillingSession
                .Status
                .PENDING
            ),
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at")
        .first()
    )
    if (
        existing_session
        and existing_session.provider_checkout_url
    ):
        return existing_session
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
            metadata={
                "trial_signup": trial_signup,
            },
            status=(
                OrganisationBillingSession
                .Status
                .PENDING
            ),
            expires_at=(
                timezone.now()
                + timedelta(minutes=30)
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
def process_paypal_webhook_event(
    event,
):
    event_id = event.get("id", "")
    event_type = event.get("event_type", "")
    resource = event.get("resource", {})
    if not event_id or not event_type:
        return False
    # Prevent PayPal retries from creating
    # duplicate RK Ops billing events.
    if OrganisationBillingEvent.objects.filter(
        provider=(
            OrganisationSubscription
            .BillingProvider
            .PAYPAL
        ),
        provider_event_id=event_id,
    ).exists():
        return False
    try:
        with transaction.atomic():
            return _process_paypal_webhook_event(
                event
            )
    except IntegrityError:
        # Another webhook request may have
        # processed the same PayPal event
        # at the same time.
        return False
def _process_paypal_webhook_event(event):
    event_id = event.get("id", "")
    event_type = event.get("event_type", "")
    resource = event.get("resource", {})
    paypal_subscription_id = ""
    if event_type.startswith(
        "BILLING.SUBSCRIPTION."
    ):
        paypal_subscription_id = (
            resource.get("id", "")
        )
    elif event_type.startswith(
        "PAYMENT.SALE."
    ):
        paypal_subscription_id = (
            resource.get(
                "billing_agreement_id",
                "",
            )
        )
    if not paypal_subscription_id:
        return False
    billing_session = (
        OrganisationBillingSession.objects
        .filter(
            provider=(
                OrganisationSubscription
                .BillingProvider
                .PAYPAL
            ),
            provider_session_id=(
                paypal_subscription_id
            ),
        )
        .select_related(
            "subscription",
            "organisation",
        )
        .order_by("-created_at")
        .first()
    )
    subscription = None
    if billing_session:
        subscription = (
            billing_session.subscription
        )
    if subscription is None:
        subscription = (
            OrganisationSubscription.objects
            .filter(
                billing_provider=(
                    OrganisationSubscription
                    .BillingProvider
                    .PAYPAL
                ),
                provider_subscription_id=(
                    paypal_subscription_id
                ),
            )
            .select_related(
                "organisation"
            )
            .first()
        )
    if subscription is None:
        return False
    with transaction.atomic():
        # --------------------------------------------------
        # SUBSCRIPTION CREATED
        # --------------------------------------------------
        if (
            event_type
            == "BILLING.SUBSCRIPTION.CREATED"
        ):
            log_billing_event(
                subscription,
                (
                    OrganisationBillingEvent
                    .EventType
                    .PROVIDER_EVENT
                ),
                provider_event_id=event_id,
                provider_reference=(
                    paypal_subscription_id
                ),
                description=(
                    "PayPal subscription created "
                    "and awaiting approval."
                ),
                metadata=event,
            )
            return True
        # --------------------------------------------------
        # SUBSCRIPTION ACTIVATED
        # --------------------------------------------------
        if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
            if billing_session:
                billing_session.status = (
                    OrganisationBillingSession
                    .Status
                    .COMPLETED
                )
                billing_session.completed_at = (
                    timezone.now()
                )
                billing_session.save(
                    update_fields=[
                        "status",
                        "completed_at",
                        "updated_at",
                    ]
                )
            if (
                billing_session
                and subscription.provider_subscription_id
                != billing_session.provider_session_id
            ):
                subscription.provider_subscription_id = (
                    billing_session.provider_session_id
                )
                subscription.save(
                    update_fields=[
                        "provider_subscription_id",
                        "updated_at",
                    ]
                )
            if billing_session:
                change_subscription_plan(
                    subscription,
                    billing_session.requested_plan,
                    reason=(
                        "PayPal subscription activated."
                    ),
                    sync_provider=False,
                )
            is_trial_signup = bool(
                billing_session
                and billing_session.metadata.get(
                    "trial_signup"
                )
            )
            if is_trial_signup:
                if not subscription.trial_ends_at:
                    subscription.trial_ends_at = (
                        timezone.now()
                        + timedelta(days=14)
                    )
                    subscription.save(
                        update_fields=[
                            "trial_ends_at",
                            "updated_at",
                        ]
                    )
                change_subscription_status(
                    subscription,
                    OrganisationSubscription
                    .Status
                    .TRIAL,
                    reason=(
                        "PayPal subscription approved "
                        "and 14-day trial started."
                    ),
                )
            else:
                change_subscription_status(
                    subscription,
                    OrganisationSubscription
                    .Status
                    .ACTIVE,
                    reason=(
                        "PayPal subscription activated."
                    ),
                )
            log_billing_event(
                subscription,
                (
                    OrganisationBillingEvent
                    .EventType
                    .PROVIDER_EVENT
                ),
                provider_event_id=event_id,
                provider_reference=(
                    paypal_subscription_id
                ),
                description=(
                    "PayPal subscription activated."
                ),
                metadata=event,
            )
            try:
                sync_paypal_billing_period(
                    subscription
                )
            except Exception:
                pass
            return True
        # --------------------------------------------------
        # PAYMENT COMPLETED
        # --------------------------------------------------
        if (
            event_type
            == "PAYMENT.SALE.COMPLETED"
        ):
            amount = None
            amount_data = resource.get(
                "amount",
                {},
            )
            amount_value = amount_data.get(
                "total"
            )
            if amount_value is not None:
                try:
                    amount = Decimal(
                        str(amount_value)
                    )
                except (
                    InvalidOperation,
                    TypeError,
                    ValueError,
                ):
                    amount = None
            log_billing_event(
                subscription,
                (
                    OrganisationBillingEvent
                    .EventType
                    .PAYMENT_SUCCEEDED
                ),
                amount=amount,
                currency=(
                    amount_data.get(
                        "currency",
                        "GBP",
                    )
                ),
                provider_event_id=event_id,
                provider_reference=(
                    resource.get("id", "")
                ),
                description=(
                    "PayPal payment completed."
                ),
                metadata=event,
            )
            if (
                subscription.status
                == OrganisationSubscription.Status.TRIAL
            ):
                subscription.trial_ends_at = None
                subscription.save(
                    update_fields=[
                        "trial_ends_at",
                        "updated_at",
                    ]
                )
                change_subscription_status(
                    subscription,
                    OrganisationSubscription.Status.ACTIVE,
                    reason=(
                        "First PayPal payment completed "
                        "after trial."
                    ),
                )
            elif (
                subscription.status
                == OrganisationSubscription.Status.PAST_DUE
            ):
                change_subscription_status(
                    subscription,
                    OrganisationSubscription.Status.ACTIVE,
                    reason=(
                        "PayPal payment completed."
                    ),
                )
            try:
                sync_paypal_billing_period(
                    subscription
                )
            except Exception:
                # Do not fail an otherwise valid PayPal
                # payment webhook just because the
                # billing-period sync failed.
                pass
            return True
        if event_type == "BILLING.SUBSCRIPTION.UPDATED":
            metadata = (
                subscription.billing_metadata
                or {}
            )
            pending_change = metadata.get(
                "pending_trial_plan_change"
            )
            if (
                pending_change
                and subscription.status
                == OrganisationSubscription.Status.TRIAL
            ):
                new_plan = pending_change.get(
                    "new_plan"
                )
                if new_plan:
                    change_subscription_plan(
                        subscription,
                        new_plan,
                        reason=(
                            "Trial plan updated "
                            "through PayPal."
                        ),
                        sync_provider=False,
                    )
                    metadata.pop(
                        "pending_trial_plan_change",
                        None,
                    )
                    subscription.billing_metadata = (
                        metadata
                    )
                    subscription.save(
                        update_fields=[
                            "billing_metadata",
                            "updated_at",
                        ]
                    )
            # Keep your existing provider-event
            # logging underneath this.
        # --------------------------------------------------
        # PAYMENT FAILED
        # --------------------------------------------------
        if (
            event_type
            == (
                "BILLING.SUBSCRIPTION."
                "PAYMENT.FAILED"
            )
        ):
            change_subscription_status(
                subscription,
                (
                    OrganisationSubscription
                    .Status
                    .PAST_DUE
                ),
                reason=(
                    "PayPal reported a "
                    "subscription payment failure."
                ),
            )
            log_billing_event(
                subscription,
                (
                    OrganisationBillingEvent
                    .EventType
                    .PAYMENT_FAILED
                ),
                provider_event_id=event_id,
                provider_reference=(
                    paypal_subscription_id
                ),
                description=(
                    "PayPal subscription "
                    "payment failed."
                ),
                metadata=event,
            )
            return True
        # --------------------------------------------------
        # SUSPENDED
        # --------------------------------------------------
        if (
            event_type
            == "BILLING.SUBSCRIPTION.SUSPENDED"
        ):
            change_subscription_status(
                subscription,
                (
                    OrganisationSubscription
                    .Status
                    .SUSPENDED
                ),
                reason=(
                    "PayPal suspended "
                    "the subscription."
                ),
            )
            log_billing_event(
                subscription,
                (
                    OrganisationBillingEvent
                    .EventType
                    .PROVIDER_EVENT
                ),
                provider_event_id=event_id,
                provider_reference=(
                    paypal_subscription_id
                ),
                description=(
                    "PayPal subscription suspended."
                ),
                metadata=event,
            )
            return True
        # --------------------------------------------------
        # CANCELLED / EXPIRED
        # --------------------------------------------------
        if event_type in {
            "BILLING.SUBSCRIPTION.CANCELLED",
            "BILLING.SUBSCRIPTION.EXPIRED",
        }:
            now = timezone.now()
            metadata = (
                subscription.billing_metadata
                or {}
            )
            cancel_at_period_end = (
                metadata.get(
                    "cancel_at_period_end",
                    False,
                )
            )
            has_paid_period_remaining = (
                event_type
                == "BILLING.SUBSCRIPTION.CANCELLED"
                and cancel_at_period_end
                and subscription.current_period_ends_at
                and subscription.current_period_ends_at > now
            )
            # --------------------------------------------------
            # PAYPAL HAS CANCELLED FUTURE RENEWAL,
            # BUT THE CUSTOMER STILL HAS PAID ACCESS
            # --------------------------------------------------
            if has_paid_period_remaining:
                if not subscription.cancelled_at:
                    subscription.cancelled_at = now
                    subscription.save(
                        update_fields=[
                            "cancelled_at",
                            "updated_at",
                        ]
                    )
                log_billing_event(
                    subscription,
                    (
                        OrganisationBillingEvent
                        .EventType
                        .PROVIDER_EVENT
                    ),
                    provider_event_id=event_id,
                    provider_reference=(
                        paypal_subscription_id
                    ),
                    description=(
                        "PayPal subscription cancelled. "
                        "RK Ops access remains active "
                        "until the end of the paid period."
                    ),
                    metadata=event,
                )
                return True
            # --------------------------------------------------
            # IMMEDIATE CANCELLATION / EXPIRY
            # --------------------------------------------------
            change_subscription_status(
                subscription,
                (
                    OrganisationSubscription
                    .Status
                    .CANCELLED
                ),
                reason=(
                    "PayPal subscription "
                    f"event: {event_type}."
                ),
            )
            if not subscription.cancelled_at:
                subscription.cancelled_at = now
                subscription.save(
                    update_fields=[
                        "cancelled_at",
                        "updated_at",
                    ]
                )
            log_billing_event(
                subscription,
                (
                    OrganisationBillingEvent
                    .EventType
                    .PROVIDER_EVENT
                ),
                provider_event_id=event_id,
                provider_reference=(
                    paypal_subscription_id
                ),
                description=(
                    f"PayPal event: {event_type}."
                ),
                metadata=event,
            )
            return True
        # --------------------------------------------------
        # OTHER PAYPAL EVENTS
        # --------------------------------------------------
        log_billing_event(
            subscription,
            (
                OrganisationBillingEvent
                .EventType
                .PROVIDER_EVENT
            ),
            provider_event_id=event_id,
            provider_reference=(
                paypal_subscription_id
            ),
            description=(
                f"PayPal event: {event_type}."
            ),
            metadata=event,
        )
        return True
def expire_stale_billing_sessions():
    now = timezone.now()
    stale_sessions = (
        OrganisationBillingSession.objects
        .filter(
            status=(
                OrganisationBillingSession
                .Status
                .PENDING
            ),
            expires_at__isnull=False,
            expires_at__lte=now,
        )
    )
    expired_count = (
        stale_sessions.update(
            status=(
                OrganisationBillingSession
                .Status
                .EXPIRED
            ),
            updated_at=now,
        )
    )
    return expired_count
def get_organisation_onboarding_progress(
    organisation,
):
    """
    Build onboarding progress from existing
    organisation data.
    No separate onboarding state is stored.
    """
    # ------------------------------------------
    # ORGANISATION
    # ------------------------------------------
    organisation_created = True
    # ------------------------------------------
    # SUBSCRIPTION
    # ------------------------------------------
    try:
        subscription = organisation.subscription
    except OrganisationSubscription.DoesNotExist:
        subscription = None
    subscription_ready = bool(
        subscription
        and subscription.status
        in {
            OrganisationSubscription.Status.TRIAL,
            OrganisationSubscription.Status.ACTIVE,
            OrganisationSubscription.Status.PAST_DUE,
        }
    )
    # ------------------------------------------
    # FIRST PROPERTY
    # ------------------------------------------
    first_property = (
        organisation.properties
        .filter(
            is_active=True,
        )
        .order_by("created_at")
        .first()
    )
    property_created = (
        first_property is not None
    )
    # ------------------------------------------
    # TEAM STARTED
    # ------------------------------------------
    invitation_exists = (
        OrganisationInvitation.objects
        .filter(
            organisation=organisation,
        )
        .exists()
    )
    additional_member_exists = (
        OrganisationMembership.objects
        .filter(
            organisation=organisation,
            is_active=True,
        )
        .exclude(
            user=organisation.owner,
        )
        .exists()
    )
    team_started = (
        invitation_exists
        or additional_member_exists
    )
    # ------------------------------------------
    # FIRST CHECKLIST
    # ------------------------------------------
    checklist_created = (
        Checklist.objects
        .filter(
            property__organisation=organisation,
        )
        .exists()
    )
    # ------------------------------------------
    # FIRST TASK
    # ------------------------------------------
    task_created = (
        Task.objects
        .filter(
            property__organisation=organisation,
        )
        .exists()
    )
    # ------------------------------------------
    # STEPS
    # ------------------------------------------
    steps = [
        {
            "key": "organisation",
            "label": "Organisation created",
            "complete": organisation_created,
            "action_label": "",
            "action_url": "",
        },
        {
            "key": "subscription",
            "label": "Subscription activated",
            "complete": subscription_ready,
            "action_label": "View subscription",
            "action_url":
            ( 
                reverse(
                    "operations:organisation_account",
                    kwargs={
                        "organisation_slug": organisation.slug,
                    },
                )
                + "#subscription-plans"
            )
        },
        {
            "key": "property",
            "label": "Create your first property",
            "complete": property_created,
            "action_label": "Add property",
            "action_url": reverse(
                "operations:organisation_property_create",
                kwargs={
                    "organisation_slug": (
                        organisation.slug
                    ),
                },
            ),
        },
        {
            "key": "team",
            "label": "Invite your team",
            "complete": team_started,
            "action_label": "Invite member",
            "action_url": reverse(
                "operations:organisation_invite_member",
                kwargs={
                    "organisation_slug": (
                        organisation.slug
                    ),
                },
            ),
        },
        {
            "key": "checklist",
            "label": "Create your first checklist",
            "complete": checklist_created,
            "action_label": "Create checklist",
            "action_url": (
                reverse(
                    "operations:checklist_create",
                    kwargs={
                        "property_slug": (
                            first_property.slug
                        ),
                    },
                )
                if first_property
                else ""
            ),
        },
        {
            "key": "task",
            "label": "Create your first task",
            "complete": task_created,
            "action_label": "Create task",
            "action_url": (
                reverse(
                    "operations:task_create",
                    kwargs={
                        "property_slug": (
                            first_property.slug
                        ),
                    },
                )
                if first_property
                else ""
            ),
        },
    ]
    completed_count = sum(
        1
        for step in steps
        if step["complete"]
    )
    total_count = len(steps)
    percentage = round(
        (
            completed_count
            / total_count
        )
        * 100
    )
    return {
        "steps": steps,
        "completed_count": completed_count,
        "total_count": total_count,
        "percentage": percentage,
        "complete": (
            completed_count
            == total_count
        ),
    }
def clear_pending_trial_plan_change(
    subscription,
):
    metadata = (
        subscription.billing_metadata
        or {}
    )
    if (
        "pending_trial_plan_change"
        not in metadata
    ):
        return False
    metadata.pop(
        "pending_trial_plan_change",
        None,
    )
    subscription.billing_metadata = (
        metadata
    )
    subscription.save(
        update_fields=[
            "billing_metadata",
            "updated_at",
        ]
    )
    return True
def sync_paypal_billing_period(
    subscription,
):
    if (
        subscription.billing_provider
        != OrganisationSubscription
        .BillingProvider
        .PAYPAL
    ):
        return None
    if not subscription.provider_subscription_id:
        return None
    adapter = get_billing_adapter(
        subscription
    )
    paypal_data = adapter.get_subscription(
        subscription.provider_subscription_id
    )
    billing_info = (
        paypal_data.get("billing_info")
        or {}
    )
    next_billing_time = (
        billing_info.get(
            "next_billing_time"
        )
    )
    if not next_billing_time:
        return None
    parsed_date = parse_datetime(
        next_billing_time
    )
    if not parsed_date:
        return None
    subscription.current_period_ends_at = (
        parsed_date
    )
    update_fields = [
        "current_period_ends_at",
        "updated_at",
    ]
    if (
        subscription.status
        == OrganisationSubscription.Status.ACTIVE
        and subscription.trial_ends_at
    ):
        subscription.trial_ends_at = None
        update_fields.append(
            "trial_ends_at"
        )
    subscription.save(
        update_fields=update_fields
    )
    return parsed_date