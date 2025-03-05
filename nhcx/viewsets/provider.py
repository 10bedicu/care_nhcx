from base64 import b64encode

from care.emr.api.viewsets.base import (
    EMRBaseViewSet,
    EMRCreateMixin,
    EMRRetrieveMixin,
)
from nhcx.models.provider import Provider
from nhcx.resources.provider.spec import ProviderCreateSpec, ProviderRetrieveSpec
from nhcx.services.participant import ParticipantService
from nhcx.services.types.participant import (
    CreateParticipantBody,
    ParticipantRegistryChoices,
    ParticipantRoleChoices,
)
from nhcx.settings import settings as plugin_settings
from nhcx.utils.crypt import generate_encryption_certificate


class ProviderViewSet(
    EMRCreateMixin,
    EMRRetrieveMixin,
    EMRBaseViewSet,
):
    database_model = Provider
    pydantic_model = ProviderCreateSpec
    pydantic_retrieve_model = ProviderRetrieveSpec
    lookup_field = "facility__external_id"

    def perform_create(self, instance):
        private_key, certificate = generate_encryption_certificate(instance.facility)

        response = ParticipantService.create_participant(
            CreateParticipantBody(
                linked_registry_codes=[ParticipantRegistryChoices.HFR],
                registryid=instance.facility.healthfacility.hf_id,
                participant_name=instance.facility.name,
                roles=[ParticipantRoleChoices.PROVIDER],
                primaryEmail="support@ohc.network",
                phone=[instance.facility.phone_number[-10:]],
                primaryMobile=instance.facility.phone_number[-10:],
                encryption_cert=b64encode(bytes(certificate, "utf-8")).decode("utf-8"),
                endpoint_url=plugin_settings.BACKEND_DOMAIN + "/api/nhcx",
            )
        )

        instance.participant_code = response.participant_code
        instance.encryption_private_key = private_key
        instance.save()
