from django.core.management.base import BaseCommand
from django.utils import timezone
from operations.services import (
    generate_recurring_tasks_for_date,
    update_subscription_statuses,
    update_task_escalations,
    expire_stale_billing_sessions,
)
class Command(BaseCommand):
    help = (
        "Run scheduled RK Ops processing, including "
        "recurring task generation and escalation updates."
    )
    def handle(self, *args, **options):
        today = timezone.localdate()
        created_count, skipped_count = (
            generate_recurring_tasks_for_date(
                target_date=today,
            )
        )
        escalation_updates = (
            update_task_escalations()
        )
        subscription_updates = (
            update_subscription_statuses()
        )
        expired_billing_sessions = (
            expire_stale_billing_sessions()
        )
        self.stdout.write(
            (
                "Expired billing sessions: "
                f"{expired_billing_sessions}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Subscriptions updated: "
                    f"{subscription_updates}."
                )
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Recurring tasks: "
                    f"{created_count} created, "
                    f"{skipped_count} skipped."
                )
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Escalations updated: "
                    f"{escalation_updates}."
                )
            )
        )