from properties.models import (
    OrganisationSubscription,
)
from .manual import (
    ManualBillingAdapter,
)
from .paypal import (
    PayPalBillingAdapter,
)
def get_billing_adapter(
    subscription,
):
    provider = (
        subscription.billing_provider
    )
    if (
        provider
        == OrganisationSubscription
        .BillingProvider
        .MANUAL
    ):
        return ManualBillingAdapter()
    if (
        provider
        == OrganisationSubscription
        .BillingProvider
        .PAYPAL
    ):
        return PayPalBillingAdapter()
    raise ValueError(
        (
            "Unsupported billing provider: "
            f"{provider}"
        )
    )