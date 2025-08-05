from rest_framework.routers import DefaultRouter

from nhcx.viewsets.callback import CallbackViewSet
from nhcx.viewsets.claim import ClaimViewSet
from nhcx.viewsets.communication import CommunicationViewSet
from nhcx.viewsets.coverage_eligibility import CoverageEligibilityRequestViewSet
from nhcx.viewsets.gateway import GatewayViewSet
from nhcx.viewsets.payment import PaymentViewSet

router = DefaultRouter()

router.register("gateway", GatewayViewSet, basename="nhcx-gateway")
router.register(
    r"coverage-eligibility-request",
    CoverageEligibilityRequestViewSet,
    basename="nhcx-coverage-eligibility",
)
router.register(r"claim", ClaimViewSet, basename="nhcx-claim")
router.register(r"communication", CommunicationViewSet, basename="nhcx-communication")
router.register(r"payment", PaymentViewSet, basename="nhcx-payment")


callback_router = DefaultRouter(trailing_slash=False)

callback_router.register("v1", CallbackViewSet, basename="nhcx-callback")


urlpatterns = [
    *router.urls,
    *callback_router.urls,
]
