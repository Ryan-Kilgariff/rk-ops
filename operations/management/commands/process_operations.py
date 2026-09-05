import logging
from django.core.management.base import (
    BaseCommand,
)
from django.utils import timezone
from operations.services import (
    expire_stale_billing_sessions,
    generate_recurring_tasks_for_date,
    reconcile_paypal_subscriptions,
    reconcile_pending_paypal_billing_sessions,
    update_subscription_statuses,
    update_task_escalations,
)
logger = logging.getLogger(__name__)
class Command(BaseCommand):
    help = (
        "Run scheduled RK Ops processing, including "
        "recurring tasks, escalations, subscription "
        "lifecycle and PayPal reconciliation."
    )
    def handle(
        self,
        *args,
        **options,
    ):
        today = timezone.localdate()
        started_at = timezone.now()
        logger.info(
            "RK Ops automation started at %s.",
            started_at.isoformat(),
        )
        # ------------------------------------------
        # RECURRING TASKS
        # ------------------------------------------
        try:
            created_count, skipped_count = (
                generate_recurring_tasks_for_date(
                    target_date=today,
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    (
                        "Recurring tasks: "
                        f"{created_count} created, "
                        f"{skipped_count} skipped."
                    )
                )
            )
        except Exception:
            logger.exception(
                "Recurring task processing failed."
            )
            self.stderr.write(
                self.style.ERROR(
                    "Recurring task processing failed."
                )
            )
        # ------------------------------------------
        # ESCALATIONS
        # ------------------------------------------
        try:
            escalation_updates = (
                update_task_escalations()
            )
            self.stdout.write(
                self.style.SUCCESS(
                    (
                        "Escalations updated: "
                        f"{escalation_updates}."
                    )
                )
            )
        except Exception:
            logger.exception(
                "Escalation processing failed."
            )
            self.stderr.write(
                self.style.ERROR(
                    "Escalation processing failed."
                )
            )
        # ------------------------------------------
        # LOCAL SUBSCRIPTION LIFECYCLE
        # ------------------------------------------
        try:
            subscription_updates = (
                update_subscription_statuses()
            )
            self.stdout.write(
                self.style.SUCCESS(
                    (
                        "Subscriptions updated: "
                        f"{subscription_updates}."
                    )
                )
            )
        except Exception:
            logger.exception(
                "Subscription lifecycle "
                "processing failed."
            )
            self.stderr.write(
                self.style.ERROR(
                    "Subscription lifecycle "
                    "processing failed."
                )
            )
        # ------------------------------------------
        # EXPIRE STALE BILLING SESSIONS
        # ------------------------------------------
        try:
            expired_billing_sessions = (
                expire_stale_billing_sessions()
            )
            self.stdout.write(
                (
                    "Expired billing sessions: "
                    f"{expired_billing_sessions}"
                )
            )
        except Exception:
            logger.exception(
                "Billing session expiry failed."
            )
            self.stderr.write(
                self.style.ERROR(
                    "Billing session expiry failed."
                )
            )
        # ------------------------------------------
        # RECOVER PENDING PAYPAL CHECKOUTS
        # ------------------------------------------
        try:
            pending_result = (
                reconcile_pending_paypal_billing_sessions()
            )
            self.stdout.write(
                self.style.SUCCESS(
                    (
                        "Pending PayPal sessions: "
                        f"{pending_result['checked']} checked, "
                        f"{pending_result['completed']} recovered, "
                        f"{pending_result['cancelled']} cancelled, "
                        f"{pending_result['failed']} failed."
                    )
                )
            )
        except Exception:
            logger.exception(
                "Pending PayPal reconciliation failed."
            )
            self.stderr.write(
                self.style.ERROR(
                    "Pending PayPal reconciliation failed."
                )
            )
        # ------------------------------------------
        # RECONCILE PAYPAL SUBSCRIPTIONS
        # ------------------------------------------
        try:
            paypal_result = (
                reconcile_paypal_subscriptions()
            )
            self.stdout.write(
                self.style.SUCCESS(
                    (
                        "PayPal subscriptions: "
                        f"{paypal_result['checked']} checked, "
                        f"{paypal_result['updated']} updated, "
                        f"{paypal_result['failed']} failed."
                    )
                )
            )
        except Exception:
            logger.exception(
                "PayPal subscription reconciliation failed."
            )
            self.stderr.write(
                self.style.ERROR(
                    "PayPal subscription reconciliation failed."
                )
            )
        finished_at = timezone.now()
        duration_seconds = (
            finished_at - started_at
        ).total_seconds()
        logger.info(
            (
                "RK Ops automation finished at %s "
                "after %.2f seconds."
            ),
            finished_at.isoformat(),
            duration_seconds,
        )
        self.stdout.write(
            self.style.SUCCESS(
                (
                    "RK Ops automation completed "
                    f"in {duration_seconds:.2f}s."
                )
            )
        )