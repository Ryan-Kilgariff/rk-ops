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
        null=True,
        blank=True,
    )
    class Meta:
        verbose_name_plural = "Properties"
        ordering = ["name"]
    def __str__(self):
        return self.name