from abc import ABC, abstractmethod
class BillingProviderAdapter(ABC):
    @abstractmethod
    def create_customer(
        self,
        organisation,
    ):
        raise NotImplementedError
    @abstractmethod
    def create_subscription(
        self,
        subscription,
    ):
        raise NotImplementedError
    @abstractmethod
    def cancel_subscription(
        self,
        subscription,
    ):
        raise NotImplementedError
    @abstractmethod
    def reactivate_subscription(
        self,
        subscription,
    ):
        raise NotImplementedError
    @abstractmethod
    def change_plan(
        self,
        subscription,
        new_plan,
    ):
        raise NotImplementedError
    @abstractmethod
    def create_checkout_session(
        self,
        billing_session,
    ):
        raise NotImplementedError