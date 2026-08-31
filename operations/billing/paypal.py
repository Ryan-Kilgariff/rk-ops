import requests
import uuid
from django.conf import settings
from .base import BillingProviderAdapter
from properties.models import (
    OrganisationSubscription,
)
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
        response.raise_for_status()
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
            "PayPal subscription creation "
            "is not implemented yet."
        )
    def cancel_subscription(
        self,
        subscription,
    ):
        raise NotImplementedError(
            "PayPal cancellation is not "
            "implemented yet."
        )
    def reactivate_subscription(
        self,
        subscription,
    ):
        raise NotImplementedError(
            "PayPal reactivation is not "
            "implemented yet."
        )
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
        response.raise_for_status()
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
        response.raise_for_status()
        return response.json()