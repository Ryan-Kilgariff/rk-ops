from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.text import slugify
from properties.forms import PropertyForm
from django.utils.text import slugify
from properties.models import (
    Organisation,
    OrganisationSubscription,
    OrganisationBillingEvent,
    OrganisationBillingSession,
    Property,
)
from accounts.models import (
    OrganisationInvitation,
    OrganisationMembership,
    PropertyMembership,
)
from operations.utils import (
    get_organisation_for_user,
    require_organisation_management_access,
)
from operations.services import (
    get_organisation_onboarding_progress,
)
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)
@login_required
def account_home(request):
    if request.user.is_superuser:
        organisations = (
            Organisation.objects
            .filter(is_active=True)
            .select_related("subscription")
            .order_by("name")
        )
    else:
        organisation_ids = (
            OrganisationMembership.objects
            .filter(
                user=request.user,
                is_active=True,
            )
            .values_list(
                "organisation_id",
                flat=True,
            )
        )
        organisations = (
            Organisation.objects
            .filter(
                id__in=organisation_ids,
                is_active=True,
            )
            .select_related("subscription")
            .order_by("name")
        )
        if not organisations.exists():
            return redirect(
                "operations:organisation_create"
            )
    return render(
        request,
        "operations/account_home.html",
        {
            "organisations": organisations,
            "active_page": "account",
        },
    )
@login_required
def organisation_account(
    request,
    organisation_slug,
):
    organisation, membership = (
        get_organisation_for_user(
            request.user,
            organisation_slug,
        )
    )
    onboarding_progress = (
        get_organisation_onboarding_progress(
            organisation
        )
    )
    subscription = getattr(
        organisation,
        "subscription",
        None,
    )
    trial_days_remaining = None
    if (
        subscription
        and subscription.status
        == OrganisationSubscription.Status.TRIAL
        and subscription.trial_ends_at
    ):
        remaining = (
            subscription.trial_ends_at
            - timezone.now()
        )
        trial_days_remaining = max(
            0,
            remaining.days + 1,
        )
    trial_monthly_price = None
    if (
        subscription
        and subscription.status
        == OrganisationSubscription.Status.TRIAL
    ):
        plan_config = (
            OrganisationSubscription
            .PLAN_CONFIG.get(
                subscription.plan,
                {}
            )
        )
        trial_monthly_price = (
            plan_config.get(
                "monthly_price"
            )
        )
    latest_billing_session = None
    latest_billing_event = None
    latest_provider_event = None
    if request.user.is_superuser and subscription:
        latest_billing_session = (
            OrganisationBillingSession.objects
            .filter(
                organisation=organisation
            )
            .order_by("-created_at")
            .first()
        )
        latest_billing_event = (
            OrganisationBillingEvent.objects
            .filter(
                organisation=organisation
            )
            .order_by("-created_at")
            .first()
        )
        latest_provider_event = (
            OrganisationBillingEvent.objects
            .filter(
                organisation=organisation,
                provider_event_id__gt="",
            )
            .order_by("-created_at")
            .first()
        )
    billing_events_queryset = (
        OrganisationBillingEvent.objects
        .filter(
            organisation=organisation
        )
        .order_by("-created_at")
    )
    billing_event_count = (
        billing_events_queryset.count()
    )
    billing_events = (
        billing_events_queryset[:5]
    )
    subscription_events = (
        organisation.subscription_events
        .select_related(
            "changed_by",
        )
        .order_by(
            "-created_at",
        )[:5]
    )
    subscription_event_count = (
        organisation.subscription_events.count()
    )
    pending_invitations = (
        OrganisationInvitation.objects
        .filter(
            organisation=organisation,
            is_active=True,
            accepted_at__isnull=True,
        )
        .order_by("-created_at")
    )
    properties = (
        organisation.properties
        .filter(is_active=True)
        .order_by("name")
    )
    organisation_memberships = (
        OrganisationMembership.objects
        .filter(
            organisation=organisation,
            is_active=True,
        )
        .select_related("user")
        .order_by(
            "role",
            "user__username",
        )
    )
    available_plans = []
    for plan_value, plan_label in (
        OrganisationSubscription.Plan.choices
    ):
        config = (
            OrganisationSubscription.PLAN_CONFIG[
                plan_value
            ]
        )
        if not config["public"]:
            continue
        available_plans.append(
            {
                "value": plan_value,
                "label": plan_label,
                "monthly_price": (
                    config["monthly_price"]
                ),
                "property_limit": (
                    config["property_limit"]
                ),
                "member_limit": (
                    config["member_limit"]
                ),
                "features": (
                    config["features"]
                ),
                "is_current": (
                    subscription
                    and
                    subscription.plan == plan_value
                ),
            }
        )
    property_count = (
        organisation.properties
        .filter(
            is_active=True,
        )
        .count()
    )
    active_member_count = (
        OrganisationMembership.objects
        .filter(
            organisation=organisation,
            is_active=True,
        )
        .count()
    )
    pending_invitation_count = (
        OrganisationInvitation.objects
        .filter(
            organisation=organisation,
            is_active=True,
            accepted_at__isnull=True,
        )
        .count()
    )
    allocated_member_count = (
        active_member_count
        + pending_invitation_count
    )
    if subscription:
        property_limit = subscription.property_limit
        member_limit = subscription.member_limit
        property_usage_percent = (
            round(
                (
                    property_count
                    / property_limit
                )
                * 100
            )
            if property_limit
            else 0
        )
        member_usage_percent = (
            round(
                (
                    active_member_count
                    / member_limit
                )
                * 100
            )
            if member_limit
            else 0
        )
        property_limit_reached = (
            property_count >= property_limit
        )
        member_limit_reached = (
            active_member_count >= member_limit
        )
    else:
        property_limit = 0
        member_limit = 0
        property_usage_percent = 0
        member_usage_percent = 0
        property_limit_reached = False
        member_limit_reached = False
    property_usage_width = min(
        property_usage_percent,
        100,
    )

    member_usage_width = min(
        member_usage_percent,
        100,
    )
    pending_invitation_queryset = (
        OrganisationInvitation.objects
        .filter(
            organisation=organisation,
            is_active=True,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
        )
        .order_by("-created_at")
    )
    pending_invitation_count = (
        pending_invitation_queryset.count()
    )
    pending_invitations = (
        pending_invitation_queryset[:5]
    )
    current_property = properties.first()
    context = {
        "organisation": organisation,
        "organisation_membership": membership,
        "property": current_property,
        "organisation_properties": properties,
        "organisation_memberships": organisation_memberships,
        "property_count": properties.count(),
        "active_page": "account",
        "pending_invitations": pending_invitations,
        "subscription": subscription,
        "subscription_events": subscription_events,
        "active_member_count": active_member_count,
        "property_limit": property_limit,
        "member_limit": member_limit,
        "property_usage_percent": property_usage_percent,
        "member_usage_percent": member_usage_percent,
        "property_limit_reached": property_limit_reached,
        "member_limit_reached": member_limit_reached,
        "pending_invitation_count": pending_invitation_count,
        "allocated_member_count": allocated_member_count,
        "property_usage_width": property_usage_width,
        "member_usage_width": member_usage_width,
        "available_plans": available_plans,
        "subscription_event_count": subscription_event_count,
        "latest_billing_session": (
            latest_billing_session
        ),
        "latest_billing_event": (
            latest_billing_event
        ),
        "latest_provider_event": (
            latest_provider_event
        ),
        "onboarding_progress": onboarding_progress,
        "trial_days_remaining": (
            trial_days_remaining
        ),
        "trial_monthly_price": trial_monthly_price,
        "billing_events": billing_events,
        "billing_event_count": billing_event_count,
    }
    return render(
        request,
        "operations/organisation_account.html",
        context,
    )
@login_required
def organisation_property_create(
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
        current_property_count = (
            organisation.properties.count()
        )
        if (
            current_property_count
            >= subscription.property_limit
        ):
            raise PermissionDenied(
                "This organisation has reached "
                "its property limit."
            )
    current_property = (
        organisation.properties
        .filter(is_active=True)
        .order_by("name")
        .first()
    )
    if request.method == "POST":
        form = PropertyForm(
            request.POST,
        )
        if form.is_valid():
            property_obj = form.save(
                commit=False
            )
            property_obj.organisation = (
                organisation
            )
            base_slug = slugify(
                property_obj.name
            )
            slug = base_slug
            counter = 2
            while Property.objects.filter(
                slug=slug
            ).exists():
                slug = (
                    f"{base_slug}-{counter}"
                )
                counter += 1
            property_obj.slug = slug
            property_obj.save()
            # Give the creator management access
            # to the new property.
            PropertyMembership.objects.get_or_create(
                property=property_obj,
                user=request.user,
                defaults={
                    "role": PropertyMembership.Role.OWNER,
                    "is_active": True,
                },
            )
            return redirect(
                "operations:dashboard",
                property_slug=property_obj.slug,
            )
    else:
        form = PropertyForm()
    context = {
        "organisation": organisation,
        "property": current_property,
        "form": form,
        "active_page": "account",
    }
    return render(
        request,
        "operations/organisation_property_form.html",
        context,
    )
@login_required
def subscription_history(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    events = (
        organisation.subscription_events
        .select_related(
            "changed_by",
        )
        .order_by(
            "-created_at",
        )
    )
    return render(
        request,
        "operations/subscription_history.html",
        {
            "organisation": organisation,
            "subscription_events": events,
            "active_page": "account",
        },
    )
@login_required
def property_home(request):
    # --------------------------------------------------
    # SUPERUSER
    # --------------------------------------------------
    if request.user.is_superuser:
        property_obj = (
            Property.objects
            .filter(
                is_active=True,
                organisation__is_active=True,
                organisation__subscription__status__in=[
                    OrganisationSubscription.Status.ACTIVE,
                    OrganisationSubscription.Status.TRIAL,
                    OrganisationSubscription.Status.PAST_DUE,
                ],
            )
            .select_related(
                "organisation",
                "organisation__subscription",
            )
            .order_by("name")
            .first()
        )
        if not property_obj:
            return redirect(
                "operations:account_home"
            )
        return redirect(
            "operations:dashboard",
            property_slug=property_obj.slug,
        )
    # --------------------------------------------------
    # NORMAL USER
    # --------------------------------------------------
    memberships = (
        PropertyMembership.objects
        .filter(
            user=request.user,
            is_active=True,
            property__is_active=True,
            property__organisation__is_active=True,
            property__organisation__memberships__user=request.user,
            property__organisation__memberships__is_active=True,
            property__organisation__subscription__status__in=[
                OrganisationSubscription.Status.ACTIVE,
                OrganisationSubscription.Status.TRIAL,
                OrganisationSubscription.Status.PAST_DUE,
            ],
        )
        .select_related(
            "property",
            "property__organisation",
        )
        .distinct()
        .order_by("property__name")
    )
    membership = memberships.first()
    if not membership:
        has_organisation_access = (
            OrganisationMembership.objects
            .filter(
                user=request.user,
                is_active=True,
                organisation__is_active=True,
            )
            .exists()
        )
        if has_organisation_access:
            return redirect(
                "operations:account_home"
            )
        return redirect(
            "operations:organisation_create"
        )
    return redirect(
        "operations:dashboard",
        property_slug=membership.property.slug,
    )
@login_required
def billing_history(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    billing_events = (
        OrganisationBillingEvent.objects
        .filter(
            organisation=organisation
        )
        .order_by("-created_at")
    )
    return render(
        request,
        "operations/billing_history.html",
        {
            "organisation": organisation,
            "billing_events": billing_events,
            "active_page": "account",
        },
    )