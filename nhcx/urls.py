from rest_framework.routers import DefaultRouter

from nhcx.viewsets.callback import CallbackViewSet
from nhcx.viewsets.claim import ClaimViewSet
from nhcx.viewsets.communication import CommunicationViewSet
from nhcx.viewsets.coverage_eligibility import CoverageEligibilityRequestViewSet
from nhcx.viewsets.gateway import GatewayViewSet
from nhcx.viewsets.insurance_plan import (
    InsurancePlanBenefitViewSet,
    InsurancePlanCoverageViewSet,
    InsurancePlanQuestionnaireViewSet,
    InsurancePlanViewSet,
)
from nhcx.viewsets.member_biometric_auth import MemberBiometricAuthViewSet
from nhcx.viewsets.payment import PaymentViewSet
from nhcx.viewsets.provider import ProviderViewSet

router = DefaultRouter()

router.register("provider", ProviderViewSet, basename="nhcx-provider")
router.register("gateway", GatewayViewSet, basename="nhcx-gateway")
router.register(
    r"coverage-eligibility-request",
    CoverageEligibilityRequestViewSet,
    basename="nhcx-coverage-eligibility",
)
router.register(r"claim", ClaimViewSet, basename="nhcx-claim")
router.register(r"communication", CommunicationViewSet, basename="nhcx-communication")
router.register(r"payment", PaymentViewSet, basename="nhcx-payment")
router.register(r"insurance-plan", InsurancePlanViewSet, basename="nhcx-insurance-plan")
router.register(
    r"insurance-plan-coverage",
    InsurancePlanCoverageViewSet,
    basename="nhcx-insurance-plan-coverage",
)
router.register(
    r"insurance-plan-benefit",
    InsurancePlanBenefitViewSet,
    basename="nhcx-insurance-plan-benefit",
)
router.register(
    r"insurance-plan-questionnaire",
    InsurancePlanQuestionnaireViewSet,
    basename="nhcx-insurance-plan-questionnaire",
)
router.register(
    r"member-biometric-auth",
    MemberBiometricAuthViewSet,
    basename="nhcx-member-biometric-auth",
)


callback_router = DefaultRouter(trailing_slash=False)

callback_router.register("v1", CallbackViewSet, basename="nhcx-callback")


urlpatterns = [
    *router.urls,
    *callback_router.urls,
]
