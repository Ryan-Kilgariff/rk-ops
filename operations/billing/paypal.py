import requests
import uuid
from django.conf import settings
from .base import BillingProviderAdapter
from properties.models import (
    OrganisationSubscription,
)
class PayPalAPIError(Exception):
    pass
class PayPalBillingAdapter(
    BillingProviderAdapter
):
    def __init__(self):
        self.base_url = (
            settings.PAYPAL_API_BASE_URL
        )
        self.client_id = (
            settings.PAYPAL_CLIENT_ID
        )
        self.client_secret = (
            settings.PAYPAL_CLIENT_SECRET
        )
    def _get_access_token(self):
        if (
            not self.client_id
            or not self.client_secret
        ):
            raise ValueError(
                "PayPal API credentials "
                "are not configured."
            )
        response = requests.post(
            (
                f"{self.base_url}"
                "/v1/oauth2/token"
            ),
            auth=(
                self.client_id,
                self.client_secret,
            ),
            headers={
                "Accept": "application/json",
                "Accept-Language": "en_GB",
            },
            data={
                "grant_type": (
                    "client_credentials"
                ),
            },
            timeout=20,
        )
        self._raise_for_paypal_error(
            response
        )
        data = response.json()
        return data["access_token"]
    def _headers(self):
        access_token = (
            self._get_access_token()
        )
        return {
            "Authorization": (
                f"Bearer {access_token}"
            ),
            "Content-Type": (
                "application/json"
            ),
            "Accept": (
                "application/json"
            ),
        }
    def create_customer(
        self,
        organisation,
    ):
        return {
            "customer_id": "",
        }
    def create_subscription(
        self,
        subscription,
    ):
        raise NotImplementedError(
            "Direct PayPal subscription "
            "creation is not implemented."
        )
    def suspend_subscription(
        self,
        subscription,
    ):
        paypal_subscription_id = (
            subscription.provider_subscription_id
        )
        if not paypal_subscription_id:
            raise ValueError(
                "PayPal subscription ID is missing."
            )
        response = requests.post(
            (
                f"{self.base_url}"
                f"/v1/billing/subscriptions/"
                f"{paypal_subscription_id}"
                "/suspend"
            ),
            headers=self._headers(),
            json={
                "reason": (
                    "RK Ops sandbox "
                    "suspension test."
                )
            },
            timeout=20,
        )
        if not response.ok:
            print(
                "PAYPAL SUSPEND ERROR:",
                response.status_code,
                response.text,
            )
        self._raise_for_paypal_error(
            response
        )
        return {
            "success": True,
            "subscription_id": (
                paypal_subscription_id
            ),
        }
    def cancel_subscription(
        self,
        subscription,
    ):
        paypal_subscription_id = (
            subscription.provider_subscription_id
        )
        if not paypal_subscription_id:
            raise ValueError(
                "PayPal subscription ID is missing."
            )
        paypal_data = self.get_subscription(
            paypal_subscription_id
        )
        paypal_status = paypal_data.get(
            "status",
            "",
        )
        if paypal_status in {
            "APPROVAL_PENDING",
            "APPROVED",
        }:
            return {
                "success": True,
                "provider_cancelled": False,
                "pending_subscription": True,
            }
        if paypal_status == "CANCELLED":
            return {
                "success": True,
                "provider_cancelled": False,
                "already_cancelled": True,
            }
        response = requests.post(
            (
                f"{self.base_url}"
                f"/v1/billing/subscriptions/"
                f"{paypal_subscription_id}"
                "/cancel"
            ),
            headers=self._headers(),
            json={
                "reason": (
                    "Subscription cancelled "
                    "from RK Ops."
                )
            },
            timeout=20,
        )
        self._raise_for_paypal_error(
            response
        )
        return {
            "success": True,
            "provider_cancelled": True,
            "subscription_id": (
                paypal_subscription_id
            ),
        }
    def reactivate_subscription(
        self,
        subscription,
    ):
        paypal_subscription_id = (
            subscription.provider_subscription_id
        )
        if (
            subscription.status
            == OrganisationSubscription.Status.CANCELLED
        ):
            return {
                "success": True,
                "requires_checkout": True,
            }
        if not paypal_subscription_id:
            raise ValueError(
                "PayPal subscription ID is missing."
            )
        paypal_data = self.get_subscription(
            paypal_subscription_id
        )
        paypal_status = paypal_data.get(
            "status",
            "",
        )
        if paypal_status == "ACTIVE":
            return {
                "success": True,
                "requires_checkout": False,
                "already_active": True,
            }
        if paypal_status == "CANCELLED":
            return {
                "success": True,
                "requires_checkout": True,
            }
        if paypal_status == "SUSPENDED":
            response = requests.post(
                (
                    f"{self.base_url}"
                    f"/v1/billing/subscriptions/"
                    f"{paypal_subscription_id}"
                    "/activate"
                ),
                headers=self._headers(),
                json={
                    "reason": (
                        "Subscription reactivated "
                        "from RK Ops."
                    )
                },
                timeout=20,
            )
            if not response.ok:
                print(
                    "PAYPAL ACTIVATE ERROR:",
                    response.status_code,
                    response.text,
                )
            self._raise_for_paypal_error(
                response
            )
            return {
                "success": True,
                "requires_checkout": False,
                "awaiting_provider_confirmation": True,
            }
        return {
            "success": False,
            "requires_checkout": False,
            "provider_status": paypal_status,
        }
    def change_plan(
        self,
        subscription,
        new_plan,
    ):
        raise NotImplementedError(
            "PayPal plan changes are not "
            "implemented yet."
        )
    def create_checkout_session(
        self,
        billing_session,
    ):
        if billing_session.metadata.get(
            "trial_signup"
        ):
            paypal_plan_id = (
                self._get_paypal_trial_plan_id(
                    billing_session.requested_plan
                )
            )
        else:
            paypal_plan_id = (
                self._get_paypal_plan_id(
                    billing_session.requested_plan
                )
            )
        return_url = (
            "http://127.0.0.1:8000"
            f"/account/{billing_session.organisation.slug}"
            "/billing/paypal/return/"
        )
        cancel_url = (
            "http://127.0.0.1:8000"
            f"/account/{billing_session.organisation.slug}"
            "/billing/paypal/cancel/"
        )
        response = requests.post(
            (
                f"{self.base_url}"
                "/v1/billing/subscriptions"
            ),
            headers={
                **self._headers(),
                "PayPal-Request-Id": str(
                    uuid.uuid4()
                ),
                "Prefer": "return=representation",
            },
            json={
                "plan_id": paypal_plan_id,
                "application_context": {
                    "brand_name": (
                        "RK Hospitality Studio"
                    ),
                    "locale": "en-GB",
                    "shipping_preference": (
                        "NO_SHIPPING"
                    ),
                    "user_action": (
                        "SUBSCRIBE_NOW"
                    ),
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                },
            },
            timeout=20,
        )
        self._raise_for_paypal_error(
            response
        )
        data = response.json()
        approval_url = ""
        for link in data.get(
            "links",
            [],
        ):
            if link.get("rel") == "approve":
                approval_url = link.get(
                    "href",
                    "",
                )
                break
        if not approval_url:
            raise ValueError(
                "PayPal did not return "
                "a subscription approval URL."
            )
        return {
            "session_id": data["id"],
            "checkout_url": approval_url,
            "reference": data["id"],
        }
    def create_product(self):
        response = requests.post(
            (
                f"{self.base_url}"
                "/v1/catalogs/products"
            ),
            headers={
                **self._headers(),
                "PayPal-Request-Id": str(
                    uuid.uuid4()
                ),
                "Prefer": "return=representation",
            },
            json={
                "name": "RK Ops",
                "description": (
                    "Hospitality operations management "
                    "software by RK Hospitality Studio."
                ),
                "type": "SERVICE",
                "category": "SOFTWARE",
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    def create_plan(
        self,
        *,
        name,
        description,
        amount,
    ):
        if not settings.PAYPAL_PRODUCT_ID:
            raise ValueError(
                "PAYPAL_PRODUCT_ID is not configured."
            )

        response = requests.post(
            (
                f"{self.base_url}"
                "/v1/billing/plans"
            ),
            headers={
                **self._headers(),
                "PayPal-Request-Id": str(
                    uuid.uuid4()
                ),
                "Prefer": "return=representation",
            },
            json={
                "product_id": (
                    settings.PAYPAL_PRODUCT_ID
                ),
                "name": name,
                "description": description,
                "status": "ACTIVE",
                "billing_cycles": [
                    {
                        "frequency": {
                            "interval_unit": "MONTH",
                            "interval_count": 1,
                        },
                        "tenure_type": "REGULAR",
                        "sequence": 1,
                        "total_cycles": 0,
                        "pricing_scheme": {
                            "fixed_price": {
                                "value": str(amount),
                                "currency_code": "GBP",
                            }
                        },
                    }
                ],
                "payment_preferences": {
                    "auto_bill_outstanding": True,
                    "payment_failure_threshold": 3,
                },
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    def _get_paypal_plan_id(
        self,
        plan,
    ):
        mapping = {
            OrganisationSubscription.Plan.STARTER: (
                settings.PAYPAL_STARTER_PLAN_ID
            ),
            OrganisationSubscription.Plan.GROWTH: (
                settings.PAYPAL_GROWTH_PLAN_ID
            ),
            OrganisationSubscription.Plan.PRO: (
                settings.PAYPAL_PRO_PLAN_ID
            ),
        }
        plan_id = mapping.get(
            plan,
            "",
        )
        if not plan_id:
            raise ValueError(
                (
                    "PayPal plan ID is not "
                    f"configured for {plan}."
                )
            )
        return plan_id
    def get_subscription(
        self,
        paypal_subscription_id,
    ):
        response = requests.get(
            (
                f"{self.base_url}"
                f"/v1/billing/subscriptions/"
                f"{paypal_subscription_id}"
            ),
            headers=self._headers(),
            timeout=20,
        )
        self._raise_for_paypal_error(
            response
        )
        return response.json()
    def verify_webhook(
        self,
        *,
        headers,
        event,
    ):
        webhook_id = (
            settings.PAYPAL_WEBHOOK_ID
        )
        if not webhook_id:
            raise ValueError(
                "PAYPAL_WEBHOOK_ID "
                "is not configured."
            )
        payload = {
            "auth_algo": (
                headers.get(
                    "PAYPAL-AUTH-ALGO",
                    "",
                )
            ),
            "cert_url": (
                headers.get(
                    "PAYPAL-CERT-URL",
                    "",
                )
            ),
            "transmission_id": (
                headers.get(
                    "PAYPAL-TRANSMISSION-ID",
                    "",
                )
            ),
            "transmission_sig": (
                headers.get(
                    "PAYPAL-TRANSMISSION-SIG",
                    "",
                )
            ),
            "transmission_time": (
                headers.get(
                    "PAYPAL-TRANSMISSION-TIME",
                    "",
                )
            ),
            "webhook_id": webhook_id,
            "webhook_event": event,
        }
        response = requests.post(
            (
                f"{self.base_url}"
                "/v1/notifications/"
                "verify-webhook-signature"
            ),
            headers=self._headers(),
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        return (
            data.get(
                "verification_status"
            )
            == "SUCCESS"
        )
    def suspend_subscription(
        self,
        subscription,
    ):
        paypal_subscription_id = (
            subscription.provider_subscription_id
        )
        if not paypal_subscription_id:
            raise ValueError(
                "PayPal subscription ID is missing."
            )
        response = requests.post(
            (
                f"{self.base_url}"
                f"/v1/billing/subscriptions/"
                f"{paypal_subscription_id}"
                "/suspend"
            ),
            headers=self._headers(),
            json={
                "reason": (
                    "RK Ops sandbox "
                    "suspension test."
                )
            },
            timeout=20,
        )
        self._raise_for_paypal_error(
            response
        )
        return {
            "success": True,
        }
    def _raise_for_paypal_error(
        self,
        response,
        *,
        fallback_message=(
            "PayPal could not complete "
            "the billing request."
        ),
    ):
        if response.ok:
            return
        try:
            data = response.json()
        except ValueError:
            data = {}
        message = (
            data.get("message")
            or fallback_message
        )
        details = data.get(
            "details",
            [],
        )
        if details:
            detail_message = (
                details[0].get(
                    "description"
                )
                or details[0].get(
                    "issue"
                )
            )
            if detail_message:
                message = detail_message
        raise PayPalAPIError(
            message
        )
    def _request(
        self,
        method,
        url,
        **kwargs,
    ):
        try:
            return requests.request(
                method,
                url,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise PayPalAPIError(
                "PayPal is temporarily unavailable."
            ) from exc
    def create_trial_plan(
        self,
        *,
        name,
        description,
        amount,
    ):
        if not settings.PAYPAL_PRODUCT_ID:
            raise ValueError(
                "PAYPAL_PRODUCT_ID is not configured."
            )
        response = requests.post(
            (
                f"{self.base_url}"
                "/v1/billing/plans"
            ),
            headers={
                **self._headers(),
                "PayPal-Request-Id": str(
                    uuid.uuid4()
                ),
                "Prefer": "return=representation",
            },
            json={
                "product_id": (
                    settings.PAYPAL_PRODUCT_ID
                ),
                "name": name,
                "description": description,
                "status": "ACTIVE",
                "billing_cycles": [
                    {
                        "frequency": {
                            "interval_unit": "DAY",
                            "interval_count": 14,
                        },
                        "tenure_type": "TRIAL",
                        "sequence": 1,
                        "total_cycles": 1,
                    },
                    {
                        "frequency": {
                            "interval_unit": "MONTH",
                            "interval_count": 1,
                        },
                        "tenure_type": "REGULAR",
                        "sequence": 2,
                        "total_cycles": 0,
                        "pricing_scheme": {
                            "fixed_price": {
                                "value": str(amount),
                                "currency_code": "GBP",
                            }
                        },
                    },
                ],
                "payment_preferences": {
                    "auto_bill_outstanding": True,
                    "payment_failure_threshold": 3,
                },
            },
            timeout=20,
        )
        self._raise_for_paypal_error(
            response,
            fallback_message=(
                "PayPal could not create "
                "the trial subscription plan."
            ),
        )
        return response.json()
    def _get_paypal_trial_plan_id(
        self,
        plan,
    ):
        mapping = {
            OrganisationSubscription.Plan.STARTER: (
                settings.PAYPAL_STARTER_TRIAL_PLAN_ID
            ),
            OrganisationSubscription.Plan.GROWTH: (
                settings.PAYPAL_GROWTH_TRIAL_PLAN_ID
            ),
            OrganisationSubscription.Plan.PRO: (
                settings.PAYPAL_PRO_TRIAL_PLAN_ID
            ),
        }
        plan_id = mapping.get(
            plan,
            "",
        )
        if not plan_id:
            raise ValueError(
                (
                    "PayPal trial plan ID "
                    f"is not configured for {plan}."
                )
            )
        return plan_id
    def revise_subscription_plan(
        self,
        subscription,
        new_plan,
        *,
        trial_plan=False,
    ):
        if not subscription.provider_subscription_id:
            raise PayPalAPIError(
                "Subscription does not have a PayPal subscription ID."
            )
        if trial_plan:
            paypal_plan_id = (
                self._get_paypal_trial_plan_id(
                    new_plan
                )
            )
        else:
            paypal_plan_id = (
                self._get_paypal_plan_id(
                    new_plan
                )
            )
        response = requests.post(
            (
                f"{self.base_url}"
                f"/v1/billing/subscriptions/"
                f"{subscription.provider_subscription_id}"
                "/revise"
            ),
            headers=self._headers(),
            json={
                "plan_id": paypal_plan_id,
            },
            timeout=20,
        )
        self._raise_for_paypal_error(
            response,
            fallback_message=(
                "PayPal could not update "
                "the subscription plan."
            ),
        )
        data = response.json()
        print(
            "PAYPAL REVISE RESPONSE:",
            data,
        )
        approval_url = None
        for link in data.get("links", []):
            if link.get("rel") == "approve":
                approval_url = link.get("href")
                break
        return {
            "approval_url": approval_url,
            "provider_response": data,
        }