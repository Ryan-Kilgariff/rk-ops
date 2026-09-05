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
        PENDING = "pending", "Pending setup"
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
    list_display = (
        "organisation",
        "plan",
        "status",
        "billing_provider",
        "provider_subscription_id",
        "property_limit",
        "member_limit",
        "updated_at",
    )
    list_filter = (
        "plan",
        "status",
        "billing_provider",
    )
    search_fields = (
        "organisation__name",
        "provider_event_id",
        "provider_reference",
    )
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
class OrganisationBillingEvent(models.Model):
    class EventType(models.TextChoices):
        PAYMENT_SUCCEEDED = (
            "payment_succeeded",
            "Payment Succeeded",
        )
        PAYMENT_FAILED = (
            "payment_failed",
            "Payment Failed",
        )
        INVOICE_CREATED = (
            "invoice_created",
            "Invoice Created",
        )
        INVOICE_PAID = (
            "invoice_paid",
            "Invoice Paid",
        )
        REFUND_ISSUED = (
            "refund_issued",
            "Refund Issued",
        )
        CHECKOUT_CREATED = (
            "checkout_created",
            "Checkout Created",
        )
        PROVIDER_EVENT = (
            "provider_event",
            "Provider Event",
        )
    list_display = (
        "organisation",
        "event_type",
        "provider",
        "provider_event_id",
        "provider_reference",
        "amount",
        "currency",
        "created_at",
    )
    list_filter = (
        "event_type",
        "provider",
    )
    search_fields = (
        "organisation__name",
        "provider_event_id",
        "provider_reference",
    )
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="billing_events",
    )
    subscription = models.ForeignKey(
        OrganisationSubscription,
        on_delete=models.CASCADE,
        related_name="billing_events",
    )
    event_type = models.CharField(
        max_length=40,
        choices=EventType.choices,
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(
        max_length=10,
        default="GBP",
    )
    provider = models.CharField(
        max_length=20,
        choices=OrganisationSubscription
        .BillingProvider
        .choices,
        default=OrganisationSubscription
        .BillingProvider
        .MANUAL,
    )
    provider_event_id = models.CharField(
        max_length=255,
        blank=True,
    )
    provider_reference = models.CharField(
        max_length=255,
        blank=True,
    )
    description = models.CharField(
        max_length=255,
        blank=True,
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    class Meta:
        ordering = [
            "-created_at",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "provider",
                    "provider_event_id",
                ],
                condition=~models.Q(
                    provider_event_id=""
                ),
                name=(
                    "unique_billing_"
                    "provider_event"
                ),
            ),
        ]
    def __str__(self):
        return (
            f"{self.organisation.name}: "
            f"{self.get_event_type_display()}"
        )
class OrganisationBillingSession(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"
    list_display = (
        "organisation",
        "requested_plan",
        "status",
        "provider",
        "provider_session_id",
        "amount",
        "currency",
        "created_at",
        "completed_at",
        "expires_at",
    )
    list_filter = (
        "status",
        "provider",
        "requested_plan",
    )
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="billing_sessions",
    )
    subscription = models.ForeignKey(
        OrganisationSubscription,
        on_delete=models.CASCADE,
        related_name="billing_sessions",
    )
    requested_plan = models.CharField(
        max_length=30,
        choices=OrganisationSubscription.Plan.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(
        max_length=10,
        default="GBP",
    )
    provider = models.CharField(
        max_length=20,
        choices=OrganisationSubscription
        .BillingProvider
        .choices,
        default=OrganisationSubscription
        .BillingProvider
        .MANUAL,
    )
    provider_session_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True
    )
    provider_checkout_url = models.URLField(
        max_length=1000,
        blank=True,
    )
    provider_reference = models.CharField(
        max_length=255,
        blank=True,
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )
    class Meta:
        ordering = [
            "-created_at",
        ]
    def __str__(self):
        return (
            f"{self.organisation.name}: "
            f"{self.get_requested_plan_display()} "
            f"({self.get_status_display()})"
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