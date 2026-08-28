from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from operations.models import RecurringTask, Task
class Command(BaseCommand):
    help = "Generate today's tasks from active recurring task templates."
    def handle(self, *args, **options):
        today = timezone.localdate()
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
        created_count = 0
        skipped_count = 0
        for recurring in recurring_tasks:
            should_generate = False
            if recurring.frequency == RecurringTask.Frequency.DAILY:
                should_generate = True
            elif (
                recurring.frequency == RecurringTask.Frequency.WEEKLY
                and recurring.weekday == today.weekday()
            ):
                should_generate = True
            if not should_generate:
                continue
            already_exists = Task.objects.filter(
                property=recurring.property,
                recurring_source=recurring,
                scheduled_date=today,
            ).exists()
            if already_exists:
                skipped_count += 1
                continue
            due_at = None
            if recurring.due_time:
                naive_due = datetime.combine(
                    today,
                    recurring.due_time,
                )
                due_at = timezone.make_aware(
                    naive_due,
                    timezone.get_current_timezone(),
                )
            Task.objects.create(
                property=recurring.property,
                recurring_source=recurring,
                scheduled_date=today,
                title=recurring.title,
                description=recurring.description,
                category=recurring.category,
                priority=recurring.priority,
                assigned_to=recurring.assigned_to,
                due_at=due_at,
                status=Task.Status.OPEN,
            )
            created_count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created: {recurring.property.name} "
                    f"- {recurring.title}"
                )
            )
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_count} task(s)."
            )
        )
        self.stdout.write(
            f"Skipped {skipped_count} existing task(s)."
        )