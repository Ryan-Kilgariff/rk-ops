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
    def __str__(self):
        return (
            f"{self.organisation.name} - "
            f"{self.get_plan_display()}"
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