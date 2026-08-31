from django.contrib import admin
from .models import (
    Organisation,
    OrganisationSubscription,
    OrganisationSubscriptionEvent,
    Property,
)
@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organisation",
        "town_city",
        "postcode",
        "is_active",
        "created_at",
    )
    list_filter = (
        "organisation",
        "is_active",
    )
    search_fields = ("name", "town_city", "postcode", "email")
    prepopulated_fields = {"slug": ("name",)}
@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "is_active",
        "created_at",
    )
    list_filter = (
        "is_active",
    )
    search_fields = (
        "name",
        "owner__username",
        "owner__email",
    )
    prepopulated_fields = {
        "slug": ("name",),
    }
@admin.register(OrganisationSubscription)
class OrganisationSubscriptionAdmin(
    admin.ModelAdmin
):
    list_display = (
        "organisation",
        "plan",
        "status",
        "billing_provider",
        "property_limit",
        "member_limit",
        "updated_at",
    )
    list_filter = (
        "plan",
        "status",
    )
    search_fields = (
        "organisation__name",
    )
    readonly_fields = (
        "property_limit",
        "member_limit",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Subscription",
            {
                "fields": (
                    "organisation",
                    "plan",
                    "status",
                    "property_limit",
                    "member_limit",
                ),
            },
        ),
        (
            "Billing",
            {
                "fields": (
                    "billing_provider",
                    "provider_customer_id",
                    "provider_subscription_id",
                    "provider_reference",
                    "billing_metadata",
                ),
            },
        ),
        (
            "Lifecycle",
            {
                "fields": (
                    "trial_ends_at",
                    "current_period_ends_at",
                    "cancelled_at",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )
@admin.register(OrganisationSubscriptionEvent)
class OrganisationSubscriptionEventAdmin(
    admin.ModelAdmin
):
    list_display = (
        "organisation",
        "previous_status",
        "new_status",
        "reason",
        "changed_by",
        "created_at",
    )
    list_filter = (
        "new_status",
        "created_at",
    )
    search_fields = (
        "organisation__name",
        "reason",
    )
    readonly_fields = (
        "organisation",
        "subscription",
        "previous_status",
        "new_status",
        "reason",
        "changed_by",
        "created_at",
    )