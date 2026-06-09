from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from care.emr.api.viewsets.base import EMRBaseViewSet, EMRRetrieveMixin
from nhcx.models.claim_consent import ClaimConsent, ClaimConsentStage
from nhcx.specs.claim_consent import ClaimConsentRetrieveSpec


class ClaimConsentViewSet(EMRRetrieveMixin, EMRBaseViewSet):
    database_model = ClaimConsent
    pydantic_retrieve_model = ClaimConsentRetrieveSpec

    def get_queryset(self):
        return (
            self.database_model.objects.filter(deleted=False)
            .select_related("encounter", "patient", "encounter__facility")
            .order_by("-modified_date")
        )

    @action(detail=False, methods=["GET"], url_path="lookup")
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="payerId",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
            ),
            OpenApiParameter(
                name="encounterId",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=True,
            ),
            OpenApiParameter(
                name="stage",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                enum=[stage.value for stage in ClaimConsentStage],
            ),
        ],
        responses={200: ClaimConsentRetrieveSpec},
    )
    def lookup(self, request, *args, **kwargs):
        params = request.query_params
        payer_id = params.get("payer_id")
        encounter_id = params.get("encounter_id")
        stage = params.get("stage", ClaimConsentStage.PREAUTHORIZATION.value)
        if not payer_id or not encounter_id:
            raise ValidationError(
                "Query parameters payerId and encounterId are required "
                "(aliases: payer_id, encounter_id, encounter)."
            )

        instance = get_object_or_404(
            self.get_queryset(),
            payer_id=payer_id,
            encounter__external_id=encounter_id,
            stage=stage,
        )
        self.authorize_retrieve(instance)
        data = (
            self.get_retrieve_pydantic_model()
            .serialize(
                instance,
                request.user,
                **self.get_serializer_retrieve_context(),
            )
            .to_json()
        )
        return Response(data)
