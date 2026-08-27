from django.contrib import admin
from .models import Property
@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "town_city",
        "postcode",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "town_city", "postcode", "email")
    prepopulated_fields = {"slug": ("name",)}