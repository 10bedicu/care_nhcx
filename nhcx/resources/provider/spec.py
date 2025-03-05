from abdm.models.health_facility import HealthFacility
from pydantic import UUID4, field_validator

from care.emr.resources.base import EMRResource
from care.emr.resources.facility.spec import FacilityRetrieveSpec
from care.facility.models.facility import Facility
from nhcx.models.provider import Provider


class BaseProviderSpec(EMRResource):
    __model__ = Provider
    __exclude__ = ["facility"]
    id: UUID4 = None


class ProviderCreateSpec(BaseProviderSpec):
    facility: UUID4

    @field_validator("facility")
    @classmethod
    def validate_facility(cls, facility):
        if not Facility.objects.filter(external_id=facility).exists():
            raise ValueError("Facility not found")

        if Provider.objects.filter(facility=facility).exists():
            raise ValueError("Provider already exists for this facility")

        if not HealthFacility.objects.filter(facility__external_id=facility).exists():
            raise ValueError(
                "Health Facility not found for the given facility, please create a health facility first"
            )

        return facility

    def perform_extra_deserialization(self, is_update, obj):
        if not is_update:
            obj.facility = Facility.objects.get(external_id=self.facility)


class ProviderUpdateSpec(BaseProviderSpec):
    regenerate_keys: bool = False


class ProviderRetrieveSpec(BaseProviderSpec):
    participant_code: str | None
    facility: FacilityRetrieveSpec

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id

        mapping["facility"] = FacilityRetrieveSpec.serialize(obj.facility).to_json()
