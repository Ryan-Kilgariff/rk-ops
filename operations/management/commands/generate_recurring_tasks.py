from django.core.management.base import BaseCommand
from django.utils import timezone
from operations.services import (
    generate_recurring_tasks_for_date,
)
class Command(BaseCommand):
    help = "Generate today's tasks from recurring task templates."
    def handle(self, *args, **options):
        today = timezone.localdate()
        created_count, skipped_count = (
            generate_recurring_tasks_for_date(
                today
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_count} task(s)."
            )
        )
        self.stdout.write(
            f"Skipped {skipped_count} existing task(s)."
        )