from django.contrib import admin
from .models import PropertyMembership
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