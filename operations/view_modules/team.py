from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from operations.activity import log_activity
from django.contrib import messages
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
    require_supervisory_access,
    require_organisation_management_access,
    require_invitation_management_access,
    get_property_for_user,
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
def team_list(
    request,
    property_slug,
):
    property_obj = require_supervisory_access(
        request.user,
        property_slug,
    )
    memberships = (
        PropertyMembership.objects
        .filter(
            property=property_obj,
            is_active=True,
        )
        .select_related(
            "user",
        )
        .order_by(
            "user__username",
        )
    )
    role_rank = {
        PropertyMembership.Role.OWNER: 4,
        PropertyMembership.Role.MANAGER: 3,
        PropertyMembership.Role.SUPERVISOR: 2,
        PropertyMembership.Role.TEAM_MEMBER: 1,
    }
    acting_membership = None
    if not request.user.is_superuser:
        acting_membership = (
            PropertyMembership.objects
            .filter(
                property=property_obj,
                user=request.user,
                is_active=True,
            )
            .first()
        )
    can_manage_team = (
        request.user.is_superuser
        or (
            acting_membership
            and acting_membership.role
            in {
                PropertyMembership.Role.OWNER,
                PropertyMembership.Role.MANAGER,
            }
        )
    )
    team_rows = []
    for membership in memberships:
        can_manage_member = False
        if request.user.is_superuser:
            can_manage_member = True
        elif (
            can_manage_team
            and acting_membership
            and membership.user_id != request.user.id
            and role_rank[membership.role]
            < role_rank[acting_membership.role]
        ):
            can_manage_member = True
        team_rows.append(
            {
                "membership": membership,
                "can_manage_member": can_manage_member,
            }
        )
    pending_invitations = []
    if can_manage_team:
        pending_invitations = (
            OrganisationInvitation.objects
            .filter(
                organisation=property_obj.organisation,
                properties=property_obj,
                is_active=True,
                accepted_at__isnull=True,
                revoked_at__isnull=True,
            )
            .distinct()
            .order_by("-created_at")
        )
    context = {
        "property": property_obj,
        "memberships": memberships,
        "active_page": "team",
        "pending_invitations": pending_invitations,
        "team_rows": team_rows,
        "can_manage_team": can_manage_team,
        "membership": acting_membership,
    }
    return render(
        request,
        "operations/team_list.html",
        context,
    )
@login_required
def team_member_create(
    request,
    property_slug,
):
    property_obj, membership = (
        get_property_for_user(
            request.user,
            property_slug,
        )
    )
    organisation = property_obj.organisation
    return redirect(
        (
            reverse(
                "operations:organisation_invite_member",
                kwargs={
                    "organisation_slug": organisation.slug,
                },
            )
            + f"?property={property_obj.slug}"
        )
    )
@login_required
def team_member_edit(
    request,
    property_slug,
    pk,
):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    target_membership = get_object_or_404(
        PropertyMembership.objects.select_related(
            "user",
        ),
        pk=pk,
        property=property_obj,
        is_active=True,
    )
    role_rank = {
        PropertyMembership.Role.OWNER: 4,
        PropertyMembership.Role.MANAGER: 3,
        PropertyMembership.Role.SUPERVISOR: 2,
        PropertyMembership.Role.TEAM_MEMBER: 1,
    }
    acting_membership = None
    if not request.user.is_superuser:
        acting_membership = get_object_or_404(
            PropertyMembership,
            property=property_obj,
            user=request.user,
            is_active=True,
        )
        # Managers/owners cannot edit someone
        # at the same or a higher level.
        if (
            role_rank[target_membership.role]
            >= role_rank[acting_membership.role]
        ):
            raise PermissionDenied(
                "You cannot manage this team member."
            )
    if request.method == "POST":
        form = MembershipEditForm(
            request.POST,
            instance=target_membership,
        )
        if form.is_valid():
            new_role = form.cleaned_data["role"]
            # ------------------------------------------
            # ROLE HIERARCHY
            # ------------------------------------------
            if (
                not request.user.is_superuser
                and role_rank[new_role]
                >= role_rank[acting_membership.role]
            ):
                form.add_error(
                    "role",
                    "You cannot assign this role.",
                )
            # ------------------------------------------
            # LAST OWNER PROTECTION
            # ------------------------------------------
            if (
                target_membership.role
                == PropertyMembership.Role.OWNER
                and new_role
                != PropertyMembership.Role.OWNER
            ):
                owner_count = (
                    PropertyMembership.objects
                    .filter(
                        property=property_obj,
                        role=PropertyMembership.Role.OWNER,
                        is_active=True,
                    )
                    .count()
                )
                if owner_count <= 1:
                    form.add_error(
                        "role",
                        (
                            "The final property owner "
                            "cannot be demoted."
                        ),
                    )
            if not form.errors:
                form.save()
                messages.success(
                    request,
                    "Team member updated.",
                )
                return redirect(
                    "operations:team_list",
                    property_slug=property_obj.slug,
                )
    else:
        form = MembershipEditForm(
            instance=target_membership,
        )
        # ------------------------------------------
        # RESTRICT DROPDOWN FOR NON-SUPERUSERS
        # ------------------------------------------
        if acting_membership:
            form.fields["role"].choices = [
                choice
                for choice in form.fields["role"].choices
                if (
                    role_rank.get(choice[0], 0)
                    < role_rank[acting_membership.role]
                )
            ]
    context = {
        "property": property_obj,
        "membership": target_membership,
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
    source_property_slug = request.GET.get(
        "property"
    )
    source_property = None
    if source_property_slug:
        source_property = require_management_access(
            request.user,
            source_property_slug,
        )
        organisation = source_property.organisation
        if organisation.slug != organisation_slug:
            raise PermissionDenied(
                "This property does not belong "
                "to this organisation."
            )
    else:
        organisation = (
            require_organisation_management_access(
                request.user,
                organisation_slug,
            )
        )
    property_manager_invite = False
    if source_property:
        organisation_membership = (
            OrganisationMembership.objects
            .filter(
                organisation=organisation,
                user=request.user,
                is_active=True,
            )
            .first()
        )
        is_org_manager = (
            request.user.is_superuser
            or (
                organisation_membership
                and organisation_membership.role
                in {
                    OrganisationMembership.Role.OWNER,
                    OrganisationMembership.Role.ADMIN,
                }
            )
        )
        property_manager_invite = (
            not is_org_manager
        )
    subscription = getattr(
        organisation,
        "subscription",
        None,
    )
    # --------------------------------------------------
    # MEMBER LIMIT
    # --------------------------------------------------
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
                revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
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
        .filter(
            is_active=True
        )
        .order_by("name")
        .first()
    )
    # --------------------------------------------------
    # POST
    # --------------------------------------------------
    if request.method == "POST":
        form = OrganisationInvitationForm(
            request.POST,
            organisation=organisation,
        )
        if property_manager_invite:
            form.fields["role"].disabled = True
            form.fields["properties"].queryset = (
                organisation.properties.filter(
                    pk=source_property.pk
                )
            )
            allowed_property_roles = {
                PropertyMembership.Role.SUPERVISOR,
                PropertyMembership.Role.TEAM_MEMBER,
            }
            form.fields["property_role"].choices = [
                choice
                for choice
                in form.fields["property_role"].choices
                if choice[0] in allowed_property_roles
            ]
        if form.is_valid():
            invited_email = (
                form.cleaned_data["email"]
                .strip()
                .lower()
            )
            if property_manager_invite:
                allowed_property_roles = {
                    PropertyMembership.Role.SUPERVISOR,
                    PropertyMembership.Role.TEAM_MEMBER,
                }
                if (
                    form.cleaned_data["property_role"]
                    not in allowed_property_roles
                ):
                    form.add_error(
                        "property_role",
                        "You cannot assign this property role.",
                    )
            # ------------------------------------------
            # ALREADY AN ORGANISATION MEMBER
            # ------------------------------------------
            existing_member = (
                OrganisationMembership.objects
                .filter(
                    organisation=organisation,
                    is_active=True,
                    user__email__iexact=invited_email,
                )
                .select_related("user")
                .first()
            )
            if existing_member:
                form.add_error(
                    "email",
                    (
                        "A user with this email is already "
                        "a member of this organisation."
                    ),
                )
            else:
                # --------------------------------------
                # EXISTING PENDING INVITATION
                # --------------------------------------
                existing_invitation = (
                    OrganisationInvitation.objects
                    .filter(
                        organisation=organisation,
                        email__iexact=invited_email,
                        is_active=True,
                        accepted_at__isnull=True,
                    )
                    .order_by("-created_at")
                    .first()
                )
                if existing_invitation:
                    if (
                        not existing_invitation.revoked_at
                        and not existing_invitation.is_expired
                    ):
                        form.add_error(
                            "email",
                            (
                                "An active invitation has "
                                "already been sent to this email."
                            ),
                        )
                    else:
                        # Old expired/revoked invitation should
                        # no longer block a fresh invitation.
                        existing_invitation.is_active = False
                        existing_invitation.save(
                            update_fields=[
                                "is_active",
                            ]
                        )
                # --------------------------------------
                # CREATE INVITATION
                # --------------------------------------
                if not form.errors:
                    invitation = form.save(
                        commit=False
                    )
                    if property_manager_invite:
                        invitation.role = (
                            OrganisationInvitation.Role.MEMBER
                        )
                    invitation.organisation = (
                        organisation
                    )
                    invitation.invited_by = (
                        request.user
                    )
                    invitation.email = (
                        invited_email
                    )
                    invitation.expires_at = (
                        timezone.now()
                        + timedelta(days=7)
                    )
                    invitation.save()
                    if property_manager_invite:
                        invitation.properties.set(
                            [source_property]
                        )
                    else:
                        form.save_m2m()
                    # ----------------------------------
                    # INVITATION URL
                    # ----------------------------------
                    accept_path = reverse(
                        "operations:organisation_invitation_signup",
                        kwargs={
                            "token": invitation.token,
                        },
                    )
                    accept_url = (
                        request.build_absolute_uri(
                            accept_path
                        )
                    )
                    inviter_name = (
                        request.user.get_full_name()
                        or request.user.username
                    )
                    subject = (
                        "You're invited to join "
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
                        property_text = (
                            "No property access"
                        )
                    message = (
                        f"{inviter_name} has invited you "
                        f"to join {organisation.name} "
                        f"on RK Ops.\n\n"
                        f"Organisation role: "
                        f"{invitation.get_role_display()}\n"
                        f"Property role: "
                        f"{invitation.get_property_role_display()}"
                        f"\n\n"
                        f"Property access: "
                        f"{property_text}\n\n"
                        f"Accept your invitation:\n"
                        f"{accept_url}\n\n"
                        "If you weren't expecting this "
                        "invitation, you can ignore this email."
                    )
                    try:
                        send_mail(
                            subject=subject,
                            message=message,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[
                                invitation.email,
                            ],
                            fail_silently=False,
                        )
                    except Exception:
                        logger.exception(
                            "Invitation email delivery could not be confirmed "
                            "for %s",
                            invitation.email,
                        )
                        messages.warning(
                            request,
                            (
                                "The invitation was created, but RK Ops could "
                                "not confirm email delivery."
                            ),
                        )
                    else:
                        messages.success(
                            request,
                            (
                                "Invitation sent to "
                                f"{invitation.email}."
                            ),
                        )
                    if source_property:
                        return redirect(
                            "operations:team_list",
                            property_slug=source_property.slug,
                        )
                    return redirect(
                        "operations:organisation_account",
                        organisation_slug=organisation.slug,
                    )
    # --------------------------------------------------
    # GET
    # --------------------------------------------------
    if request.method != "POST":
        form = OrganisationInvitationForm(
            organisation=organisation,
            initial={
                "properties": (
                    [source_property.pk]
                    if source_property
                    else []
                ),
            },
        )
    if property_manager_invite:
        form.fields["role"].initial = (
            OrganisationInvitation.Role.MEMBER
        )
        form.fields["role"].disabled = True
        form.fields["properties"].queryset = (
            organisation.properties.filter(
                pk=source_property.pk
            )
        )
        form.fields["properties"].initial = [
            source_property.pk
        ]
        allowed_property_roles = {
            PropertyMembership.Role.SUPERVISOR,
            PropertyMembership.Role.TEAM_MEMBER,
        }
        form.fields["property_role"].choices = [
            choice
            for choice
            in form.fields["property_role"].choices
            if choice[0] in allowed_property_roles
        ]
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
            user.username = (
                form.cleaned_data["username"]
                .strip()
            )
            user.set_password(
                form.cleaned_data["password1"]
            )
            user.save()
            login(
                request,
                user,
                backend="accounts.backends."
                    "UsernameOrEmailBackend"
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
    source_property_slug = request.GET.get(
        "property"
    )
    invitation = get_object_or_404(
        OrganisationInvitation.objects.select_related(
            "organisation"
        ).prefetch_related(
            "properties"
        ),
        pk=invitation_pk,
        organisation__slug=organisation_slug,
    )
    organisation = (
        require_invitation_management_access(
            request.user,
            invitation,
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
        messages.success(
            request,
            (
                f"Invitation to "
                f"{invitation.email} "
                f"has been revoked."
            ),
        )
    if source_property_slug:
        return redirect(
            "operations:team_list",
            property_slug=source_property_slug,
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
    source_property_slug = request.GET.get(
        "property"
    )
    invitation = get_object_or_404(
        OrganisationInvitation.objects.select_related(
            "organisation"
        ).prefetch_related(
            "properties"
        ),
        pk=invitation_pk,
        organisation__slug=organisation_slug,
    )
    organisation = (
        require_invitation_management_access(
            request.user,
            invitation,
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
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[
                    invitation.email,
                ],
                fail_silently=False,
            )
        except Exception:
            logger.exception(
                "Invitation resend email delivery could not be "
                "confirmed for %s",
                invitation.email,
            )
            messages.warning(
                request,
                (
                    "The invitation was renewed, but RK Ops could "
                    "not confirm email delivery."
                ),
            )
        else:
            messages.success(
                request,
                (
                    "Invitation resent to "
                    f"{invitation.email}."
                ),
            )
    if source_property_slug:
        return redirect(
            "operations:team_list",
            property_slug=source_property_slug,
        )
    return redirect(
        "operations:organisation_account",
        organisation_slug=organisation.slug,
    )
@login_required
def team_member_remove(
    request,
    property_slug,
    pk,
):
    property_obj = require_management_access(
        request.user,
        property_slug,
    )
    target_membership = get_object_or_404(
        PropertyMembership.objects.select_related(
            "user",
        ),
        pk=pk,
        property=property_obj,
        is_active=True,
    )
    role_rank = {
        PropertyMembership.Role.OWNER: 4,
        PropertyMembership.Role.MANAGER: 3,
        PropertyMembership.Role.SUPERVISOR: 2,
        PropertyMembership.Role.TEAM_MEMBER: 1,
    }
    if not request.user.is_superuser:
        acting_membership = get_object_or_404(
            PropertyMembership,
            property=property_obj,
            user=request.user,
            is_active=True,
        )
        if (
            role_rank[target_membership.role]
            >= role_rank[acting_membership.role]
        ):
            raise PermissionDenied(
                "You cannot remove this team member."
            )
    # Do not remove yourself through team management.
    if (
        target_membership.user_id
        == request.user.id
        and not request.user.is_superuser
    ):
        raise PermissionDenied(
            "You cannot remove yourself from the property."
        )
    # Never remove the final active owner.
    if (
        target_membership.role
        == PropertyMembership.Role.OWNER
    ):
        owner_count = (
            PropertyMembership.objects
            .filter(
                property=property_obj,
                role=PropertyMembership.Role.OWNER,
                is_active=True,
            )
            .count()
        )
        if owner_count <= 1:
            raise PermissionDenied(
                "The final property owner cannot be removed."
            )
    if request.method == "POST":
        target_membership.is_active = False
        target_membership.save(
            update_fields=[
                "is_active",
            ]
        )
        messages.success(
            request,
            (
                f"{target_membership.user.get_username()} "
                "has been removed from this property."
            ),
        )
    return redirect(
        "operations:team_list",
        property_slug=property_obj.slug,
    )
@login_required
def organisation_invitation_list(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    invitations = (
        OrganisationInvitation.objects
        .filter(
            organisation=organisation,
            is_active=True,
            accepted_at__isnull=True,
        )
        .order_by("-created_at")
    )
    return render(
        request,
        "operations/organisation_invitation_list.html",
        {
            "organisation": organisation,
            "invitations": invitations,
            "active_page": "account",
        },
    )