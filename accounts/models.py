from django.conf import settings
from django.db import models
from properties.models import Property
class PropertyMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner / Admin"
        MANAGER = "manager", "Manager"
        SUPERVISOR = "supervisor", "Supervisor"
        TEAM_MEMBER = "team_member", "Team Member"
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="property_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.TEAM_MEMBER,
    )
    job_title = models.CharField(
        max_length=100,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["property", "user"],
                name="unique_property_user_membership",
            )
        ]
        ordering = [
            "user__first_name",
            "user__username",
        ]
    def __str__(self):
        return f"{self.user} - {self.property}"
class OrganisationMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Administrator"
        MEMBER = "member", "Member"
    organisation = models.ForeignKey(
        "properties.Organisation",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organisation_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    is_active = models.BooleanField(
        default=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organisation",
                    "user",
                ],
                name="unique_organisation_membership",
            ),
        ]
    def __str__(self):
        return (
            f"{self.user} - "
            f"{self.organisation} - "
            f"{self.get_role_display()}"
        )