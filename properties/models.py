from django.conf import settings
from django.db import models
class Organisation(models.Model):
    name = models.CharField(
        max_length=200,
    )
    slug = models.SlugField(
        unique=True,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_organisations",
    )
    is_active = models.BooleanField(
        default=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )
    class Meta:
        ordering = ["name"]
    def __str__(self):
        return self.name
class OrganisationSubscription(models.Model):
    class Plan(models.TextChoices):
        FOUNDER_BETA = "founder_beta", "Founder Beta"
        STARTER = "starter", "Starter"
        GROWTH = "growth", "Growth"
        PRO = "pro", "Pro"
    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        CANCELLED = "cancelled", "Cancelled"
        SUSPENDED = "suspended", "Suspended"
    class BillingProvider(models.TextChoices):
        MANUAL = "manual", "Manual"
        STRIPE = "stripe", "Stripe"
        PAYPAL = "paypal", "PayPal"
    PLAN_CONFIG = {
        Plan.FOUNDER_BETA: {
            "public": False,
            "monthly_price": 29,
            "property_limit": 5,
            "member_limit": 25,
            "features": [
                "Core operations dashboard",
                "Tasks and issues",
                "Checklists",
                "Handover",
                "Team access",
                "Recurring tasks",
                "Escalations",
            ],
        },
        Plan.STARTER: {
            "public": True,
            "monthly_price": 39,
            "property_limit": 1,
            "member_limit": 8,
            "features": [
                "Core operations dashboard",
                "Tasks and issues",
                "Checklists",
                "Handover",
                "Team access",
            ],
        },
        Plan.GROWTH: {
            "public": True,
            "monthly_price": 69,
            "property_limit": 3,
            "member_limit": 20,
            "features": [
                "Everything in Starter",
                "Recurring tasks",
                "Operational analytics",
                "Escalations",
            ],
        },
        Plan.PRO: {
            "public": True,
            "monthly_price": 119,
            "property_limit": 10,
            "member_limit": 50,
            "features": [
                "Everything in Growth",
                "Multi-property operations",
                "Advanced workload visibility",
                "Priority support",
            ],
        },
    }
    billing_provider = models.CharField(
        max_length=20,
        choices=BillingProvider.choices,
        default=BillingProvider.MANUAL,
    )
    provider_customer_id = models.CharField(
        max_length=255,
        blank=True,
    )
    provider_subscription_id = models.CharField(
        max_length=255,
        blank=True,
    )
    provider_reference = models.CharField(
        max_length=255,
        blank=True,
    )
    billing_metadata = models.JSONField(
        default=dict,
        blank=True,
    )
    organisation = models.OneToOneField(
        Organisation,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.CharField(
        max_length=30,
        choices=Plan.choices,
        default=Plan.FOUNDER_BETA,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    property_limit = models.PositiveIntegerField(
        default=1,
    )
    member_limit = models.PositiveIntegerField(
        default=10,
    )
    trial_ends_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    current_period_ends_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )
    def apply_plan_limits(self):
        config = self.PLAN_CONFIG.get(
            self.plan,
            {},
        )
        self.property_limit = config.get(
            "property_limit",
            self.property_limit,
        )
        self.member_limit = config.get(
            "member_limit",
            self.member_limit,
        )
    def save(self, *args, **kwargs):
        self.apply_plan_limits()
        update_fields = kwargs.get(
            "update_fields"
        )
        if update_fields is not None:
            update_fields = set(
                update_fields
            )
            update_fields.update(
                {
                    "property_limit",
                    "member_limit",
                }
            )
            kwargs["update_fields"] = (
                list(update_fields)
            )
        super().save(
            *args,
            **kwargs,
        )
    def __str__(self):
        return (
            f"{self.organisation.name} - "
            f"{self.get_plan_display()}"
        )
class OrganisationSubscriptionEvent(
    models.Model
):
    class EventType(models.TextChoices):
        STATUS_CHANGE = (
            "status_change",
            "Status Change",
        )
        PLAN_CHANGE = (
            "plan_change",
            "Plan Change",
        )
    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
        default=EventType.STATUS_CHANGE,
    )
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="subscription_events",
    )
    subscription = models.ForeignKey(
        OrganisationSubscription,
        on_delete=models.CASCADE,
        related_name="events",
    )
    previous_status = models.CharField(
        max_length=20,
        choices=OrganisationSubscription.Status.choices,
        null=True,
        blank=True,
    )
    new_status = models.CharField(
        max_length=20,
        choices=OrganisationSubscription.Status.choices,
        null=True,
        blank=True,
    )
    previous_plan = models.CharField(
        max_length=30,
        choices=OrganisationSubscription.Plan.choices,
        null=True,
        blank=True,
    )
    new_plan = models.CharField(
        max_length=30,
        choices=OrganisationSubscription.Plan.choices,
        null=True,
        blank=True,
    )
    reason = models.CharField(
        max_length=255,
        blank=True,
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscription_changes",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    class Meta:
        ordering = [
            "-created_at",
        ]
    def __str__(self):
        return (
            f"{self.organisation.name}: "
            f"{self.previous_status} → "
            f"{self.new_status}"
        )
class Property(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    address_line_1 = models.CharField(max_length=150, blank=True)
    address_line_2 = models.CharField(max_length=150, blank=True)
    town_city = models.CharField(max_length=100, blank=True)
    postcode = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.PROTECT,
        related_name="properties",
    )
    class Meta:
        verbose_name_plural = "Properties"
        ordering = ["name"]
    def __str__(self):
        return self.name