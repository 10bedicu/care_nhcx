from rest_framework.routers import DefaultRouter

from nhcx.viewsets.claim import ClaimViewSet
from nhcx.viewsets.coverage_eligibility import CoverageEligibilityRequestViewSet

router = DefaultRouter()

router.register(
    r"coverage-eligibility-request",
    CoverageEligibilityRequestViewSet,
    basename="nhcx-coverage-eligibility",
)
router.register(r"claim", ClaimViewSet, basename="nhcx-claim")


urlpatterns = router.urls
