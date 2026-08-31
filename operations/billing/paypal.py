import requests
from django.conf import settings
from .base import BillingProviderAdapter
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
        raise NotImplementedError(
            "PayPal checkout is not "
            "implemented yet."
        )