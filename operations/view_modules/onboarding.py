from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.utils import timezone
from accounts.forms import SignUpForm
from accounts.models import (
    OrganisationInvitation,
    OrganisationMembership,
)
from properties.models import (
    Organisation,
    OrganisationSubscription,
)
from operations.billing.paypal import (
    PayPalBillingAdapter,
    PayPalAPIError,
)
from operations.services import (
    create_billing_session,
)
from operations.utils import (
    require_organisation_management_access,
)
import logging
logger = logging.getLogger(__name__)
def signup(request):
    if request.user.is_authenticated:
        return redirect(
            "operations:property_home"
        )
    if request.method == "POST":
        form = SignUpForm(
            request.POST
        )
        if form.is_valid():
            user = form.save()
            login(
                request,
                user,
                backend="accounts.backends.UsernameOrEmailBackend",
            )
            messages.success(
                request,
                (
                    "Your RK Ops account "
                    "has been created."
                ),
            )
            return redirect(
                "operations:organisation_create"
            )
    else:
        form = SignUpForm()
    return render(
        request,
        "operations/signup.html",
        {
            "form": form,
        },
    )
@login_required
def organisation_create(request):
    existing_membership = (
        OrganisationMembership.objects
        .filter(
            user=request.user,
            is_active=True,
        )
        .exists()
    )
    if existing_membership:
        return redirect(
            "operations:account_home"
        )
    if request.method == "POST":
        name = request.POST.get(
            "name",
            ""
        ).strip()
        if not name:
            messages.error(
                request,
                "Enter an organisation name.",
            )
            return render(
                request,
                "operations/organisation_create.html",
                {
                    "active_page": "account",
                },
            )
        base_slug = slugify(name)
        slug = base_slug
        counter = 2
        while Organisation.objects.filter(
            slug=slug
        ).exists():
            slug = (
                f"{base_slug}-{counter}"
            )
            counter += 1
        organisation = (
            Organisation.objects.create(
                name=name,
                slug=slug,
                owner=request.user,
            )
        )
        OrganisationMembership.objects.create(
            organisation=organisation,
            user=request.user,
            role=(
                OrganisationMembership
                .Role
                .OWNER
            ),
            is_active=True,
        )
        messages.success(
            request,
            (
                "Your RK Ops organisation "
                "has been created."
            ),
        )
        return redirect(
            "operations:organisation_trial_choose_plan",
            organisation_slug=organisation.slug,
        )
    return render(
        request,
        "operations/organisation_create.html",
        {
            "active_page": "account",
        },
    )
@login_required
def organisation_trial_choose_plan(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    existing_subscription = (
        OrganisationSubscription.objects
        .filter(
            organisation=organisation
        )
        .first()
    )
    if (
        existing_subscription
        and existing_subscription.status
        in {
            OrganisationSubscription.Status.TRIAL,
            OrganisationSubscription.Status.ACTIVE,
            OrganisationSubscription.Status.PAST_DUE,
        }
    ):
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    if request.method == "POST":
        selected_plan = request.POST.get(
            "plan",
            ""
        )
        valid_plans = {
            plan_value
            for plan_value, _ in (
                OrganisationSubscription
                .Plan
                .choices
            )
            if (
                OrganisationSubscription
                .PLAN_CONFIG[
                    plan_value
                ]["public"]
            )
        }
        if selected_plan not in valid_plans:
            messages.error(
                request,
                "Select a valid RK Ops plan.",
            )
            return redirect(
                "operations:organisation_trial_choose_plan",
                organisation_slug=organisation.slug,
            )
        subscription, created = (
            OrganisationSubscription.objects
            .get_or_create(
                organisation=organisation,
                defaults={
                    "plan": selected_plan,
                    "status": (
                        OrganisationSubscription
                        .Status
                        .PENDING
                    ),
                    "billing_provider": (
                        OrganisationSubscription
                        .BillingProvider
                        .PAYPAL
                    ),
                },
            )
        )
        if not created:
            subscription.plan = selected_plan
            subscription.status = (
                OrganisationSubscription
                .Status
                .PENDING
            )
            subscription.billing_provider = (
                OrganisationSubscription
                .BillingProvider
                .PAYPAL
            )
            subscription.trial_ends_at = None
            subscription.save(
                update_fields=[
                    "plan",
                    "status",
                    "billing_provider",
                    "trial_ends_at",
                    "updated_at",
                ]
            )
        try:
            billing_session = (
                create_billing_session(
                    subscription,
                    selected_plan,
                    trial_signup=True,
                )
            )
        except PayPalAPIError as exc:
            logger.exception(
                "PayPal trial checkout "
                "could not be created."
            )
            messages.error(
                request,
                (
                    "PayPal checkout could not "
                    "be started. Please try again."
                ),
            )
            return redirect(
                "operations:organisation_trial_choose_plan",
                organisation_slug=organisation.slug,
            )
        if billing_session.provider_checkout_url:
            return redirect(
                billing_session.provider_checkout_url
            )
        messages.error(
            request,
            "PayPal checkout could not be started.",
        )
        return redirect(
            "operations:organisation_trial_choose_plan",
            organisation_slug=organisation.slug,
        )
    public_plans = []
    for plan_value, plan_label in (
        OrganisationSubscription.Plan.choices
    ):
        config = (
            OrganisationSubscription
            .PLAN_CONFIG[
                plan_value
            ]
        )
        if not config["public"]:
            continue
        public_plans.append(
            {
                "value": plan_value,
                "label": plan_label,
                "price": config[
                    "monthly_price"
                ],
                "property_limit": config[
                    "property_limit"
                ],
                "member_limit": config[
                    "member_limit"
                ],
                "features": config[
                    "features"
                ],
            }
        )
    return render(
        request,
        "operations/trial_choose_plan.html",
        {
            "organisation": organisation,
            "public_plans": public_plans,
            "active_page": "account",
        },
    )
@login_required
def organisation_trial_change_plan(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    subscription = (
        OrganisationSubscription.objects
        .filter(
            organisation=organisation
        )
        .first()
    )
    if (
        not subscription
        or subscription.status
        != OrganisationSubscription.Status.TRIAL
    ):
        messages.error(
            request,
            "This subscription is not currently on trial.",
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    if request.method != "POST":
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    new_plan = request.POST.get(
        "plan",
        ""
    )
    valid_plans = {
        value
        for value, _ in (
            OrganisationSubscription.Plan.choices
        )
        if (
            OrganisationSubscription
            .PLAN_CONFIG[value]["public"]
        )
    }
    if new_plan not in valid_plans:
        messages.error(
            request,
            "Select a valid plan.",
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    if new_plan == subscription.plan:
        messages.info(
            request,
            "This is already your current trial plan.",
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    # ------------------------------------------
    # TARGET PLAN LIMITS
    # ------------------------------------------
    plan_config = (
        OrganisationSubscription.PLAN_CONFIG[
            new_plan
        ]
    )
    property_count = (
        organisation.properties.count()
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
    # ------------------------------------------
    # TRIAL DOWNGRADE SAFETY
    # ------------------------------------------
    if (
        property_count
        > plan_config["property_limit"]
    ):
        messages.error(
            request,
            (
                "This plan cannot be selected because "
                f"the organisation currently has "
                f"{property_count} properties, but "
                f"the plan supports "
                f"{plan_config['property_limit']}."
            ),
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    if (
        allocated_member_count
        > plan_config["member_limit"]
    ):
        messages.error(
            request,
            (
                "This plan cannot be selected because "
                f"the organisation currently has "
                f"{allocated_member_count} allocated "
                "team member places, but the plan "
                f"supports {plan_config['member_limit']}."
            ),
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    adapter = PayPalBillingAdapter()
    try:
        result = adapter.revise_subscription_plan(
            subscription,
            new_plan,
            trial_plan=True,
        )
    except PayPalAPIError:
        logger.exception(
            "PayPal trial plan change failed."
        )
        messages.error(
            request,
            (
                "PayPal could not update your "
                "trial plan. Please try again."
            ),
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    approval_url = result.get(
        "approval_url"
    )
    if approval_url:
        metadata = (
            subscription.billing_metadata
            or {}
        )
        metadata[
            "pending_trial_plan_change"
        ] = {
            "new_plan": new_plan,
            "requested_at": (
                timezone.now().isoformat()
            ),
        }
        subscription.billing_metadata = (
            metadata
        )
        subscription.save(
            update_fields=[
                "billing_metadata",
                "updated_at",
            ]
        )
        return redirect(
            approval_url
        )
    messages.error(
        request,
        (
            "PayPal did not return an "
            "approval link."
        ),
    )
    return redirect(
        "operations:organisation_account",
        organisation_slug=organisation.slug,
    )
@login_required
def paypal_trial_plan_return(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    subscription = (
        OrganisationSubscription.objects
        .filter(
            organisation=organisation
        )
        .first()
    )
    if not subscription:
        messages.error(
            request,
            "Subscription could not be found.",
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    if (
        subscription.status
        != OrganisationSubscription.Status.TRIAL
    ):
        messages.info(
            request,
            "Subscription update received.",
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    metadata = (
        subscription.billing_metadata
        or {}
    )
    pending_change = metadata.get(
        "pending_trial_plan_change"
    )
    if not pending_change:
        messages.info(
            request,
            (
                "PayPal approval was received. "
                "RK Ops is waiting for confirmation."
            ),
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    messages.success(
        request,
        (
            "PayPal approved your plan change. "
            "It may take up to a minute for the "
            "new plan to appear on your RK Ops account."
        ),
    )
    return redirect(
        "operations:organisation_account",
        organisation_slug=organisation.slug,
    )