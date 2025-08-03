from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from care.emr.api.viewsets.base import EMRBaseViewSet
from nhcx.services.participant import ParticipantService
from nhcx.services.types.participant import GetPoliciesBody, GetPoliciesResponse


class GatewayViewSet(EMRBaseViewSet):
    @extend_schema(
        request=GetPoliciesBody,
        responses={200: GetPoliciesResponse},
    )
    @action(detail=False, methods=["POST"], url_path="get_policies")
    def get_policies(self, request, *args, **kwargs):
        payload = GetPoliciesBody(**request.data)
        response = ParticipantService.get_policies(payload)
        return Response(response.model_dump(mode="json"), status=status.HTTP_200_OK)
