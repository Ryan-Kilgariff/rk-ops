from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from operations.activity import log_activity
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from accounts.forms import (
    OrganisationInvitationForm,
    MembershipEditForm,
    TeamMemberCreateForm,
    InvitationSignupForm,
)
from operations.models import (
    ActivityLog,
)
from accounts.models import (
    OrganisationInvitation,
    OrganisationMembership,
    PropertyMembership,
)
from operations.utils import (
    require_management_access,
    require_organisation_management_access,
)
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from datetime import timedelta
from django.contrib.auth import login
from django.contrib.auth import get_user_model
from accounts.forms import (
    InvitationSignupForm,
    OrganisationInvitationForm,
)
from django.utils import timezone
import logging
from django.contrib.auth import get_user_model
User = get_user_model()
logger = logging.getLogger(__name__)
@login_required
def team_list(request, property_slug):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    memberships = (
        PropertyMembership.objects
        .filter(property=property_obj)
        .select_related("user")
    )
    context = {
        "property": property_obj,
        "memberships": memberships,
        "active_page": "team",
    }
    return render(
        request,
        "operations/team_list.html",
        context,
    )
@login_required
def team_member_create(request, property_slug):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    if request.method == "POST":
        form = TeamMemberCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            PropertyMembership.objects.create(
                property=property_obj,
                user=user,
                role=form.cleaned_data["role"],
                job_title=form.cleaned_data["job_title"],
            )
            log_activity(
                property_obj=property_obj,
                event_type=ActivityLog.EventType.TEAM_MEMBER_ADDED,
                title=user.get_full_name() or user.username,
                user=request.user,
                detail=form.cleaned_data["role"],
            )
            return redirect(
                "operations:team_list",
                property_slug=property_obj.slug,
            )
    else:
        form = TeamMemberCreateForm()
    context = {
        "property": property_obj,
        "form": form,
        "active_page": "team",
    }
    return render(
        request,
        "operations/team_form.html",
        context,
    )
@login_required
def team_member_edit(request, property_slug, pk):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    membership = get_object_or_404(
        PropertyMembership.objects.select_related(
            "user",
        ),
        pk=pk,
        property=property_obj,
    )
    if request.method == "POST":
        form = MembershipEditForm(
            request.POST,
            instance=membership,
        )
        if form.is_valid():
            form.save()
            return redirect(
                "operations:team_list",
                property_slug=property_obj.slug,
            )
    else:
        form = MembershipEditForm(
            instance=membership,
        )
    context = {
        "property": property_obj,
        "membership": membership,
        "form": form,
        "active_page": "team",
        "form_mode": "edit",
    }
    return render(
        request,
        "operations/team_form.html",
        context,
    )
@login_required
def organisation_invite_member(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    subscription = getattr(
        organisation,
        "subscription",
        None,
    )
    if subscription:
        current_member_count = (
            OrganisationMembership.objects
            .filter(
                organisation=organisation,
                is_active=True,
            )
            .count()
        )
        pending_invite_count = (
            OrganisationInvitation.objects
            .filter(
                organisation=organisation,
                is_active=True,
                accepted_at__isnull=True,
            )
            .count()
        )
        if (
            current_member_count
            + pending_invite_count
            >= subscription.member_limit
        ):
            raise PermissionDenied(
                "This organisation has reached "
                "its team member limit."
            )
    current_property = (
        organisation.properties
        .filter(is_active=True)
        .order_by("name")
        .first()
    )
    if request.method == "POST":
        form = OrganisationInvitationForm(
            request.POST,
            organisation=organisation,
        )
        if form.is_valid():
            invitation = form.save(
                commit=False
            )
            invitation.organisation = (
                organisation
            )
            invitation.invited_by = (
                request.user
            )
            invitation.expires_at = (
                timezone.now()
                + timedelta(days=7)
            )
            invitation.save()
            form.save_m2m()
            accept_path = reverse(
                "operations:organisation_invitation_signup",
                kwargs={
                    "token": invitation.token,
                },
            )
            accept_url = request.build_absolute_uri(
                accept_path
            )
            inviter_name = (
                request.user.get_full_name()
                or request.user.username
            )
            subject = (
                f"You're invited to join "
                f"{organisation.name} on RK Ops"
            )
            property_names = list(
                invitation.properties
                .values_list(
                    "name",
                    flat=True,
                )
            )
            if property_names:
                property_text = ", ".join(
                    property_names
                )
            else:
                property_text = "No property access"
            message = (
                f"{inviter_name} has invited you to join "
                f"{organisation.name} on RK Ops.\n\n"
                f"Organisation role: "
                f"{invitation.get_role_display()}\n"
                f"Property role: "
                f"{invitation.get_property_role_display()}\n\n"
                f"Property access: {property_text}\n\n"
                f"Accept your invitation:\n"
                f"{accept_url}\n\n"
                f"If you weren't expecting this invitation, "
                f"you can ignore this email."
            )
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[
                    invitation.email,
                ],
                fail_silently=False,
            )
            return redirect(
                "operations:organisation_account",
                organisation_slug=organisation.slug,
            )
    else:
        form = OrganisationInvitationForm(
            organisation=organisation,
        )
    return render(
        request,
        "operations/organisation_invitation_form.html",
        {
            "organisation": organisation,
            "property": current_property,
            "form": form,
            "active_page": "account",
        },
    )
def accept_organisation_invitation(
    *,
    invitation,
    user,
):
    organisation_membership, created = (
        OrganisationMembership.objects.get_or_create(
            organisation=invitation.organisation,
            user=user,
            defaults={
                "role": invitation.role,
                "is_active": True,
            },
        )
    )
    if not created:
        organisation_membership.role = invitation.role
        organisation_membership.is_active = True
        organisation_membership.save(
            update_fields=[
                "role",
                "is_active",
            ]
        )
    for property_obj in invitation.properties.all():
        PropertyMembership.objects.update_or_create(
            property=property_obj,
            user=user,
            defaults={
                "role": invitation.property_role,
                "is_active": True,
            },
        )
        log_activity(
            property_obj=property_obj,
            event_type=ActivityLog.EventType.TEAM_MEMBER_ADDED,
            title=(
                user.get_full_name()
                or user.username
            ),
            user=invitation.invited_by,
            detail="Joined via organisation invitation",
        )
    invitation.accepted_at = timezone.now()
    invitation.is_active = False
    invitation.save(
        update_fields=[
            "accepted_at",
            "is_active",
        ]
    )
@login_required
def organisation_invitation_accept(
    request,
    token,
):
    invitation = get_object_or_404(
        OrganisationInvitation.objects.select_related(
            "organisation",
            "invited_by",
        ),
        token=token,
        is_active=True,
        accepted_at__isnull=True,
    )
    # -----------------------------------------------
    # Invitation validity
    # -----------------------------------------------
    if invitation.revoked_at:
        raise PermissionDenied(
            "This invitation has been revoked."
        )
    if invitation.is_expired:
        raise PermissionDenied(
            "This invitation has expired."
        )
    # -----------------------------------------------
    # Make sure the logged-in account matches
    # the invited email address
    # -----------------------------------------------
    user_email = (
        request.user.email
        or ""
    ).strip().lower()
    invitation_email = (
        invitation.email
        or ""
    ).strip().lower()
    if user_email != invitation_email:
        raise PermissionDenied(
            "This invitation belongs to a different email address."
        )
    # -----------------------------------------------
    # Accept
    # -----------------------------------------------
    if request.method == "POST":
        accept_organisation_invitation(
            invitation=invitation,
            user=request.user,
        )
        first_property = (
            invitation.properties
            .filter(is_active=True)
            .order_by("name")
            .first()
        )
        if first_property:
            return redirect(
                "operations:dashboard",
                property_slug=first_property.slug,
            )
        return redirect(
            "operations:organisation_account",
            organisation_slug=invitation.organisation.slug,
        )
    # -----------------------------------------------
    # Page context
    # -----------------------------------------------
    current_property = (
        invitation.properties
        .filter(is_active=True)
        .order_by("name")
        .first()
    )
    if current_property is None:
        current_property = (
            invitation.organisation.properties
            .filter(is_active=True)
            .order_by("name")
            .first()
        )
    context = {
        "invitation": invitation,
        "organisation": invitation.organisation,
        "property": current_property,
    }
    return render(
        request,
        "operations/organisation_invitation_accept.html",
        context,
    )
def organisation_invitation_signup(
    request,
    token,
):
    invitation = get_object_or_404(
        OrganisationInvitation.objects.select_related(
            "organisation",
        ),
        token=token,
        is_active=True,
        accepted_at__isnull=True,
    )
    if invitation.revoked_at:
        raise PermissionDenied(
            "This invitation has been revoked."
        )
    if invitation.is_expired:
        raise PermissionDenied(
            "This invitation has expired."
        )
    invited_email = invitation.email.strip().lower()
    existing_user = (
        User.objects
        .filter(
            email__iexact=invited_email,
        )
        .first()
    )
    current_property = (
        invitation.properties
        .filter(is_active=True)
        .order_by("name")
        .first()
    )
    if current_property is None:
        current_property = (
            invitation.organisation.properties
            .filter(is_active=True)
            .order_by("name")
            .first()
        )
    if existing_user:
        accept_url = reverse(
            "operations:organisation_invitation_accept",
            kwargs={
                "token": invitation.token,
            },
        )
        login_url = reverse("login")
        return redirect(
            f"{login_url}?next={accept_url}"
        )
    if request.method == "POST":
        form = InvitationSignupForm(
            request.POST,
        )
        if form.is_valid():
            user = form.save(
                commit=False
            )
            user.email = invited_email
            base_username = (
                invited_email
                .split("@")[0]
                .replace(".", "")
                .replace("-", "")
            )
            username = base_username
            counter = 2
            while User.objects.filter(
                username=username
            ).exists():
                username = (
                    f"{base_username}{counter}"
                )
                counter += 1
            user.username = username
            user.set_password(
                form.cleaned_data["password1"]
            )
            user.save()
            login(
                request,
                user,
                backend="django.contrib.auth.backends.ModelBackend",
            )
            accept_organisation_invitation(
                invitation=invitation,
                user=user,
            )
            first_property = (
                invitation.properties
                .filter(is_active=True)
                .order_by("name")
                .first()
            )
            if first_property:
                return redirect(
                    "operations:dashboard",
                    property_slug=first_property.slug,
                )
            return redirect(
                "operations:organisation_account",
                organisation_slug=invitation.organisation.slug,
            )
    else:
        form = InvitationSignupForm()
    return render(
        request,
        "operations/organisation_invitation_signup.html",
        {
            "form": form,
            "invitation": invitation,
            "organisation": invitation.organisation,
            "property": current_property,
        },
    )
@login_required
def organisation_invitation_revoke(
    request,
    organisation_slug,
    invitation_pk,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    invitation = get_object_or_404(
        OrganisationInvitation,
        pk=invitation_pk,
        organisation=organisation,
        accepted_at__isnull=True,
    )
    if request.method == "POST":
        invitation.is_active = False
        invitation.revoked_at = timezone.now()
        invitation.save(
            update_fields=[
                "is_active",
                "revoked_at",
            ]
        )
    return redirect(
        "operations:organisation_account",
        organisation_slug=organisation.slug,
    )
@login_required
def organisation_invitation_resend(
    request,
    organisation_slug,
    invitation_pk,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    invitation = get_object_or_404(
        OrganisationInvitation,
        pk=invitation_pk,
        organisation=organisation,
        accepted_at__isnull=True,
    )
    if request.method == "POST":
        invitation.is_active = True
        invitation.revoked_at = None
        invitation.expires_at = (
            timezone.now()
            + timedelta(days=7)
        )
        invitation.save(
            update_fields=[
                "is_active",
                "revoked_at",
                "expires_at",
            ]
        )
        accept_path = reverse(
            "operations:organisation_invitation_signup",
            kwargs={
                "token": invitation.token,
            },
        )
        accept_url = request.build_absolute_uri(
            accept_path
        )
        inviter_name = (
            request.user.get_full_name()
            or request.user.username
        )
        property_names = list(
            invitation.properties
            .values_list(
                "name",
                flat=True,
            )
        )
        property_text = (
            ", ".join(property_names)
            if property_names
            else "No property access"
        )
        subject = (
            f"Reminder: you're invited to join "
            f"{organisation.name} on RK Ops"
        )
        message = (
            f"{inviter_name} has invited you to join "
            f"{organisation.name} on RK Ops.\n\n"
            f"Organisation role: "
            f"{invitation.get_role_display()}\n"
            f"Property role: "
            f"{invitation.get_property_role_display()}\n"
            f"Property access: "
            f"{property_text}\n\n"
            f"Accept your invitation:\n"
            f"{accept_url}\n\n"
            f"This invitation expires in 7 days."
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[
                invitation.email,
            ],
            fail_silently=False,
        )
    return redirect(
        "operations:organisation_account",
        organisation_slug=organisation.slug,
    )