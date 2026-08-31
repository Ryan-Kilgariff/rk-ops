from .base import BillingProviderAdapter
class ManualBillingAdapter(
    BillingProviderAdapter
):
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
        return {
            "subscription_id": "",
            "status": subscription.status,
        }
    def cancel_subscription(
        self,
        subscription,
    ):
        return {
            "success": True,
        }
    def reactivate_subscription(
        self,
        subscription,
    ):
        return {
            "success": True,
        }
    def change_plan(
        self,
        subscription,
        new_plan,
    ):
        return {
            "success": True,
            "plan": new_plan,
        }
    def create_checkout_session(
        self,
        billing_session,
    ):

        return {
            "session_id": (
                f"manual-{billing_session.pk}"
            ),
            "checkout_url": "",
            "reference": (
                f"manual-{billing_session.pk}"
            ),
        }