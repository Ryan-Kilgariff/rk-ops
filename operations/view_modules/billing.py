from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
from properties.models import (
    OrganisationSubscription,
    OrganisationBillingSession,
)
from accounts.models import (
    OrganisationInvitation,
    OrganisationMembership,
)
from operations.billing import (
    get_billing_adapter,
)
from operations.utils import (
    require_organisation_management_access,
)
from datetime import timedelta
from operations.services import (
    cancel_subscription,
    change_subscription_plan,
    change_subscription_status,
    reactivate_subscription,
    change_subscription_plan,
    create_billing_session,
    process_paypal_webhook_event,
)
from operations.billing.paypal import (
    PayPalBillingAdapter,
    PayPalAPIError,
)
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import logging
logger = logging.getLogger(__name__)
@login_required
@require_POST
def organisation_subscription_cancel(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    try:
        subscription = organisation.subscription
    except OrganisationSubscription.DoesNotExist:
        raise PermissionDenied(
            "This organisation does not have "
            "a subscription."
        )
    if subscription.status in {
        OrganisationSubscription.Status.CANCELLED,
        OrganisationSubscription.Status.SUSPENDED,
    }:
        messages.info(
            request,
            "This subscription is already inactive.",
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    try:
        cancel_subscription(
            subscription,
            reason=(
                "Subscription cancelled "
                "by organisation administrator."
            ),
            changed_by=request.user,
        )
    except PayPalAPIError as exc:
        logger.exception(
            "PayPal billing operation failed."
        )
        messages.error(
            request,
            (
                "PayPal could not cancel "
                "the subscription right now. "
                "Please try again."
            ),
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    messages.success(
        request,
        "The RK Ops subscription has been cancelled.",
    )
    return redirect(
        "operations:organisation_account",
        organisation_slug=organisation.slug,
    )
@login_required
@require_POST
def organisation_subscription_reactivate(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    try:
        subscription = organisation.subscription
    except OrganisationSubscription.DoesNotExist:
        raise PermissionDenied(
            "This organisation does not have "
            "a subscription."
        )
    if subscription.status not in {
        OrganisationSubscription.Status.CANCELLED,
        OrganisationSubscription.Status.SUSPENDED,
    }:
        messages.info(
            request,
            "This subscription is already active.",
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    try:
        result = reactivate_subscription(
            subscription,
            reason=(
                "Subscription reactivated "
                "by organisation administrator."
            ),
            changed_by=request.user,
        )
    except PayPalAPIError as exc:
        logger.exception(
            "PayPal billing operation failed."
        )
        messages.error(
            request,
            (
                "PayPal could not reactivate "
                "the subscription right now. "
                "Please try again."
            ),
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    # ------------------------------------------
    # PAYPAL SUSPENDED → AWAIT CONFIRMATION
    # ------------------------------------------
    if result.get(
        "awaiting_provider_confirmation"
    ):
        messages.info(
            request,
            (
                "PayPal is reactivating the "
                "subscription. RK Ops will "
                "update automatically once "
                "PayPal confirms activation."
            ),
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    # ------------------------------------------
    # PAYPAL CANCELLED → NEW CHECKOUT
    # ------------------------------------------
    if result.get(
        "requires_checkout"
    ):
        try:
            billing_session = (
                create_billing_session(
                    subscription,
                    subscription.plan,
                )
            )
        except PayPalAPIError as exc:
            logger.exception(
                "PayPal billing operation failed."
            )
            messages.error(
                request,
                (
                    "PayPal checkout could not "
                    "be started. Please try again."
                ),
            )
            return redirect(
                "operations:organisation_account",
                organisation_slug=organisation.slug,
            )
        if billing_session.provider_checkout_url:
            return redirect(
                billing_session.provider_checkout_url
            )
        messages.error(
            request,
            (
                "A PayPal checkout could "
                "not be created."
            ),
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    # ------------------------------------------
    # MANUAL / ALREADY ACTIVE PROVIDER
    # ------------------------------------------
    messages.success(
        request,
        "The RK Ops subscription has been reactivated.",
    )
    return redirect(
        "operations:organisation_account",
        organisation_slug=organisation.slug,
    )
@login_required
def organisation_subscription_cancel_confirm(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    try:
        subscription = organisation.subscription
    except OrganisationSubscription.DoesNotExist:
        raise PermissionDenied(
            "This organisation does not have "
            "a subscription."
        )
    return render(
        request,
        "operations/subscription_cancel_confirm.html",
        {
            "organisation": organisation,
            "subscription": subscription,
            "active_page": "account",
        },
    )
@login_required
@require_POST
def organisation_subscription_change_plan(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    new_plan = request.POST.get("plan")
    valid_plans = {
        choice[0]
        for choice in OrganisationSubscription.Plan.choices
    }
    if new_plan not in valid_plans:
        raise PermissionDenied(
            "Invalid subscription plan."
        )
    new_config = OrganisationSubscription.PLAN_CONFIG[
        new_plan
    ]
    if not new_config["public"]:
        raise PermissionDenied(
            "This subscription plan cannot be selected directly."
        )
    try:
        subscription = organisation.subscription
    except OrganisationSubscription.DoesNotExist:
        raise PermissionDenied(
            "This organisation does not have "
            "a subscription."
        )
    # ------------------------------------------
    # CURRENT USAGE
    # ------------------------------------------
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
    # ------------------------------------------
    # NEW PLAN LIMITS
    # ------------------------------------------
    new_config = (
        OrganisationSubscription.PLAN_CONFIG[
            new_plan
        ]
    )
    new_property_limit = (
        new_config["property_limit"]
    )
    new_member_limit = (
        new_config["member_limit"]
    )
    # ------------------------------------------
    # DOWNGRADE SAFETY
    # ------------------------------------------
    if property_count > new_property_limit:
        messages.error(
            request,
            (
                "This plan cannot be selected because "
                f"the organisation currently has "
                f"{property_count} active properties."
            ),
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    if allocated_member_count > new_member_limit:
        messages.error(
            request,
            (
                "This plan cannot be selected because "
                f"the organisation currently has "
                f"{allocated_member_count} allocated "
                "team member places."
            ),
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    # ------------------------------------------
    # NO CHANGE
    # ------------------------------------------
    if subscription.plan == new_plan:
        messages.info(
            request,
            "This is already your current plan.",
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    # ------------------------------------------
    # CHANGE PLAN
    # ------------------------------------------
    previous_plan = (
        subscription.get_plan_display()
    )
    if (
        subscription.billing_provider
        == OrganisationSubscription.BillingProvider.MANUAL
    ):
        change_subscription_plan(
            subscription,
            new_plan,
            reason=(
                "Subscription plan changed "
                "by account administrator."
            ),
            changed_by=request.user,
        )
        messages.success(
            request,
            (
                f"Subscription changed from "
                f"{previous_plan} to "
                f"{subscription.get_plan_display()}."
            ),
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    try:
        billing_session = (
            create_billing_session(
                subscription,
                new_plan,
            )
        )
    except PayPalAPIError:
        messages.error(
            request,
            (
                "PayPal checkout could not "
                "be started. Please try again."
            ),
        )
    if billing_session.provider_checkout_url:
        return redirect(
            billing_session.provider_checkout_url
        )
    messages.info(
        request,
        (
            "A billing session has been created. "
            "The plan will change after payment "
            "has been confirmed."
        ),
    )
    return redirect(
        "operations:organisation_account",
        organisation_slug=organisation.slug,
    )
@login_required
def organisation_subscription_change_plan_confirm(
    request,
    organisation_slug,
    plan_value,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    try:
        subscription = organisation.subscription
    except OrganisationSubscription.DoesNotExist:
        raise PermissionDenied(
            "This organisation does not have "
            "a subscription."
        )
    valid_plans = {
        choice[0]
        for choice in OrganisationSubscription.Plan.choices
    }
    if plan_value not in valid_plans:
        raise PermissionDenied(
            "Invalid subscription plan."
        )
    plan_config = (
        OrganisationSubscription.PLAN_CONFIG[
            plan_value
        ]
    )
    if not plan_config["public"]:
        raise PermissionDenied(
            "This subscription plan cannot "
            "be selected directly."
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
    can_change_plan = True
    blocking_reason = ""
    if (
        property_count
        > plan_config["property_limit"]
    ):
        can_change_plan = False
        blocking_reason = (
            "This plan supports "
            f"{plan_config['property_limit']} "
            "properties, but this organisation "
            f"currently has {property_count}."
        )
    elif (
        allocated_member_count
        > plan_config["member_limit"]
    ):
        can_change_plan = False
        blocking_reason = (
            "This plan supports "
            f"{plan_config['member_limit']} "
            "team members, but this organisation "
            f"currently has {allocated_member_count} "
            "allocated places."
        )
    if subscription.status in {
        OrganisationSubscription.Status.CANCELLED,
        OrganisationSubscription.Status.SUSPENDED,
    }:
        messages.warning(
            request,
            (
                "Reactivate the subscription before "
                "changing plans."
            ),
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    return render(
        request,
        "operations/subscription_change_plan_confirm.html",
        {
            "organisation": organisation,
            "subscription": subscription,
            "plan_value": plan_value,
            "plan_label": dict(
                OrganisationSubscription.Plan.choices
            )[plan_value],
            "plan_config": plan_config,
            "property_count": property_count,
            "allocated_member_count": allocated_member_count,
            "can_change_plan": can_change_plan,
            "blocking_reason": blocking_reason,
            "active_page": "account",
        },
    )
@login_required
def paypal_billing_return(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    try:
        subscription = organisation.subscription
    except OrganisationSubscription.DoesNotExist:
        raise PermissionDenied(
            "This organisation does not have "
            "a subscription."
        )
    billing_session = (
        OrganisationBillingSession.objects
        .filter(
            organisation=organisation,
            subscription=subscription,
            status=(
                OrganisationBillingSession
                .Status
                .PENDING
            ),
        )
        .order_by("-created_at")
        .first()
    )
    if not billing_session:
        messages.warning(
            request,
            "No pending PayPal billing session was found.",
        )
        return redirect(
            "operations:organisation_account",
            organisation_slug=organisation.slug,
        )
    adapter = get_billing_adapter(
        subscription
    )
    paypal_data = adapter.get_subscription(
        billing_session.provider_session_id
    )
    paypal_status = paypal_data.get(
        "status",
        ""
    )
    if paypal_status == "ACTIVE":
        # ------------------------------------------
        # STORE THE NEW ACTIVE PAYPAL SUBSCRIPTION
        # ------------------------------------------
        if (
            subscription.provider_subscription_id
            != billing_session.provider_session_id
        ):
            subscription.provider_subscription_id = (
                billing_session.provider_session_id
            )
            subscription.save(
                update_fields=[
                    "provider_subscription_id",
                    "updated_at",
                ]
            )
        # ------------------------------------------
        # APPLY THE REQUESTED PLAN
        # ------------------------------------------
        change_subscription_plan(
            subscription,
            billing_session.requested_plan,
            reason=(
                "Subscription plan changed "
                "after PayPal confirmation."
            ),
            changed_by=request.user,
            sync_provider=False,
        )
        # ------------------------------------------
        # COMPLETE BILLING SESSION
        # ------------------------------------------
        billing_session.status = (
            OrganisationBillingSession
            .Status
            .COMPLETED
        )
        billing_session.completed_at = (
            timezone.now()
        )
        billing_session.save(
            update_fields=[
                "status",
                "completed_at",
                "updated_at",
            ]
        )
        # ------------------------------------------
        # CLEAR OLD CANCELLATION STATE
        # ------------------------------------------
        if subscription.cancelled_at:
            subscription.cancelled_at = None
            subscription.save(
                update_fields=[
                    "cancelled_at",
                    "updated_at",
                ]
            )
        # ------------------------------------------
        # ENSURE RK OPS IS ACTIVE
        # ------------------------------------------
        is_trial_signup = bool(
            billing_session.metadata.get(
                "trial_signup"
            )
        )
        if is_trial_signup:
            if not subscription.trial_ends_at:
                subscription.trial_ends_at = (
                    timezone.now()
                    + timedelta(days=14)
                )
                subscription.save(
                    update_fields=[
                        "trial_ends_at",
                        "updated_at",
                    ]
                )
            change_subscription_status(
                subscription,
                OrganisationSubscription.Status.TRIAL,
                reason=(
                    "PayPal subscription approved "
                    "and 14-day trial started."
                ),
                changed_by=request.user,
            )
        else:
            change_subscription_status(
                subscription,
                OrganisationSubscription.Status.ACTIVE,
                reason=(
                    "PayPal subscription activated."
                ),
                changed_by=request.user,
            )
        messages.success(
            request,
            (
                "PayPal confirmed the subscription. "
                "Your RK Ops subscription is active."
            ),
        )
    else:
        messages.info(
            request,
            (
                "PayPal approval was received, "
                "but the subscription is not active yet. "
                f"Current PayPal status: {paypal_status or 'Unknown'}."
            ),
        )
    return redirect(
        "operations:organisation_account",
        organisation_slug=organisation.slug,
    )
@login_required
def paypal_billing_cancel(
    request,
    organisation_slug,
):
    organisation = (
        require_organisation_management_access(
            request.user,
            organisation_slug,
        )
    )
    billing_session = (
        OrganisationBillingSession.objects
        .filter(
            organisation=organisation,
            provider=(
                OrganisationSubscription
                .BillingProvider
                .PAYPAL
            ),
            status=(
                OrganisationBillingSession
                .Status
                .PENDING
            ),
        )
        .order_by("-created_at")
        .first()
    )
    if billing_session:
        billing_session.status = (
            OrganisationBillingSession
            .Status
            .CANCELLED
        )
        billing_session.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )
    messages.warning(
        request,
        "PayPal checkout was cancelled.",
    )
    return redirect(
        "operations:organisation_account",
        organisation_slug=(
            organisation.slug
        ),
    )
@csrf_exempt
def paypal_webhook(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "detail": "Method not allowed."
            },
            status=405,
        )
    try:
        event = json.loads(
            request.body.decode("utf-8")
        )
    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):
        return JsonResponse(
            {
                "detail": "Invalid JSON."
            },
            status=400,
        )
    adapter = PayPalBillingAdapter()
    try:
        verified = adapter.verify_webhook(
            headers=request.headers,
            event=event,
        )
    except Exception as exc:
        logger.info(
            "PayPal webhook processed: "
            "event_type=%s event_id=%s processed=%s",
            event_type,
            event_id,
            processed,
        )
        return JsonResponse(
            {
                "detail": (
                    "Webhook verification "
                    "failed."
                )
            },
            status=400,
        )
    if not verified:
        return JsonResponse(
            {
                "detail": (
                    "Invalid PayPal "
                    "webhook signature."
                )
            },
            status=400,
        )
    event_type = event.get(
        "event_type",
        "",
    )
    event_id = event.get(
        "id",
        "",
    )
    resource = event.get(
        "resource",
        {},
    )
    try:
        processed = (
            process_paypal_webhook_event(
                event
            )
        )
    except Exception as exc:
        logger.info(
            "PayPal webhook processed: "
            "event_type=%s event_id=%s processed=%s",
            event_type,
            event_id,
            processed,
        )
        return JsonResponse(
            {
                "detail": (
                    "Webhook processing failed."
                )
            },
            status=500,
        )
    logger.info(
        "PayPal webhook processed: "
        "event_type=%s event_id=%s processed=%s",
        event_type,
        event_id,
        processed,
    )
    return JsonResponse(
        {
            "received": True,
            "processed": processed,
        }
    )