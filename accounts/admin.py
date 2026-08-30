from django.contrib import admin
from .models import PropertyMembership
from .models import (
    OrganisationInvitation,
    OrganisationMembership,
    PropertyMembership,
)
@admin.register(OrganisationInvitation)
class OrganisationInvitationAdmin(
    admin.ModelAdmin
):
    list_display = (
        "email",
        "organisation",
        "role",
        "invited_by",
        "is_active",
        "accepted_at",
        "created_at",
    )
    list_filter = (
        "organisation",
        "role",
        "is_active",
    )
    search_fields = (
        "email",
        "organisation__name",
    )
    readonly_fields = (
        "token",
        "created_at",
        "accepted_at",
    )
@admin.register(PropertyMembership)
class PropertyMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "property",
        "role",
        "job_title",
        "is_active",
    )
    list_filter = (
        "property",
        "role",
        "is_active",
    )
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "job_title",
    )
@admin.register(OrganisationMembership)
class OrganisationMembershipAdmin(
    admin.ModelAdmin
):
    list_display = (
        "user",
        "organisation",
        "role",
        "is_active",
    )
    list_filter = (
        "role",
        "is_active",
        "organisation",
    )
    search_fields = (
        "user__username",
        "user__email",
        "organisation__name",
    )
