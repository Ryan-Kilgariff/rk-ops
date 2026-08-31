from properties.models import (
    OrganisationSubscription,
)
from .manual import (
    ManualBillingAdapter,
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
    raise ValueError(
        (
            "Unsupported billing provider: "
            f"{provider}"
        )
    )