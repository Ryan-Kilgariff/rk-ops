from django.conf import settings
from django.db import models
from properties.models import Property
import uuid
from django.utils import timezone
class OrganisationInvitation(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        MEMBER = "member", "Member"
    class PropertyRole(models.TextChoices):
        OWNER = "owner", "Owner / Admin"
        MANAGER = "manager", "Manager"
        SUPERVISOR = "supervisor", "Supervisor"
        TEAM_MEMBER = "team_member", "Team Member"
    property_role = models.CharField(
        max_length=20,
        choices=PropertyRole.choices,
        default=PropertyRole.TEAM_MEMBER,
    )
    properties = models.ManyToManyField(
        "properties.Property",
        blank=True,
        related_name="organisation_invitations",
    )
    organisation = models.ForeignKey(
        "properties.Organisation",
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_organisation_invitations",
    )
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(
        default=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organisation",
                    "email",
                ],
                condition=models.Q(
                    is_active=True,
                    accepted_at__isnull=True,
                ),
                name="unique_active_organisation_invitation",
            ),
        ]
    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at
    def __str__(self):
        return (
            f"{self.email} → "
            f"{self.organisation.name}"
        )
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