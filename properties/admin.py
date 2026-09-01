from django.contrib import admin
from .models import (
    Organisation,
    OrganisationBillingEvent,
    OrganisationBillingSession,
    OrganisationSubscription,
    OrganisationSubscriptionEvent,
    Property,
)
from properties.models import (
    Organisation,
    OrganisationBillingEvent,
    OrganisationBillingSession,
    OrganisationSubscription,
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
class OrganisationSubscriptionAdmin(admin.ModelAdmin):
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
        "provider_customer_id",
        "provider_subscription_id",
        "provider_reference",
    )
    readonly_fields = (
        "property_limit",
        "member_limit",
        "provider_customer_id",
        "provider_subscription_id",
        "provider_reference",
        "billing_metadata",
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
@admin.register(OrganisationBillingEvent)
class OrganisationBillingEventAdmin(
    admin.ModelAdmin
):
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
        "description",
    )
    readonly_fields = (
        "organisation",
        "subscription",
        "event_type",
        "amount",
        "currency",
        "provider",
        "provider_event_id",
        "provider_reference",
        "description",
        "metadata",
        "created_at",
    )
@admin.register(OrganisationBillingSession)
class OrganisationBillingSessionAdmin(
    admin.ModelAdmin
):
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
    search_fields = (
        "organisation__name",
        "provider_session_id",
        "provider_reference",
    )
    readonly_fields = (
        "organisation",
        "subscription",
        "requested_plan",
        "status",
        "amount",
        "currency",
        "provider",
        "provider_session_id",
        "provider_checkout_url",
        "provider_reference",
        "metadata",
        "expires_at",
        "completed_at",
        "created_at",
        "updated_at",
    )