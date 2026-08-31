from django.contrib import admin
from .models import (
    Organisation,
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
class OrganisationSubscriptionAdmin(
    admin.ModelAdmin
):
    list_display = (
        "organisation",
        "plan",
        "status",
        "property_limit",
        "member_limit",
        "current_period_ends_at",
    )
    list_filter = (
        "plan",
        "status",
    )
    search_fields = (
        "organisation__name",
    )