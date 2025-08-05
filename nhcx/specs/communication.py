from datetime import datetime
from enum import Enum

from django.shortcuts import get_object_or_404
from pydantic import UUID4, BaseModel, Field, field_validator, model_validator
from rest_framework.exceptions import ValidationError

from care.emr.models.file_upload import FileUpload
from care.emr.resources.base import EMRResource
from care.emr.resources.file_upload.spec import FileUploadRetrieveSpec
from care.emr.resources.user.spec import UserSpec
from care.emr.utils.valueset_coding_type import ValueSetBoundCoding
from nhcx.models.communication import Communication, CommunicationRequest
from nhcx.specs.valuesets.communication import NHCX_COMMUNICATION_CATEGORY_VALUESET


class CommunicationStatusChoices(str, Enum):
    PREPARATION = "preparation"
    IN_PROGRESS = "in-progress"
    NOT_DONE = "not-done"
    ON_HOLD = "on-hold"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ENTERED_IN_ERROR = "entered-in-error"
    UNKNOWN = "unknown"


class CommunicationPriorityChoices(str, Enum):
    ROUTINE = "routine"
    URGENT = "urgent"
    ASAP = "asap"
    STAT = "stat"


class CommunicationPayloadSpec(BaseModel):
    content_string: str | None = None
    content_attachment: UUID4 | None = None

    @field_validator("content_attachment")
    @classmethod
    def validate_content_attachment(cls, value):
        if value and not FileUpload.objects.filter(external_id=value).exists():
            raise ValidationError("File upload not found")
        return value

    @model_validator(mode="after")
    def validate_content_string_or_attachment(self):
        if self.content_string is None and self.content_attachment is None:
            raise ValidationError(
                "Either content_string or content_attachment must be present"
            )
        if self.content_string is not None and self.content_attachment is not None:
            raise ValidationError(
                "Only one of content_string or content_attachment must be present"
            )
        return self


class CommunicationBaseSpec(EMRResource):
    __model__ = Communication
    __exclude__ = ["based_on", "part_of", "about"]
    id: UUID4 | None = None

    created_date: datetime | None = None
    modified_date: datetime | None = None


class CommunicationCreateSpec(CommunicationBaseSpec):
    status: CommunicationStatusChoices | None = None
    priority: CommunicationPriorityChoices | None = None
    category: list[ValueSetBoundCoding[NHCX_COMMUNICATION_CATEGORY_VALUESET.slug]] = []
    payload: list[CommunicationPayloadSpec] = Field([], min_length=1)
    based_on: UUID4

    @field_validator("based_on")
    @classmethod
    def validate_based_on(cls, value):
        if not CommunicationRequest.objects.filter(external_id=value).exists():
            raise ValidationError("Communication Request not found")
        return value

    def perform_extra_deserialization(self, is_update, obj):
        obj.based_on = get_object_or_404(
            CommunicationRequest, external_id=self.based_on
        )

        if not self.status:
            obj.status = CommunicationStatusChoices.PREPARATION

        if not self.priority:
            obj.priority = obj.based_on.priority

        if len(self.category) == 0:
            obj.category = [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/communication-category",
                    "code": "notification",
                }
            ]

        obj.about = obj.based_on.about


class CommunicationListSpec(CommunicationBaseSpec):
    status: str
    priority: str | None = None
    category: list[dict] = []
    sent: datetime | None = None
    payload: list[dict] = []

    based_on: UUID4
    part_of: UUID4
    about: UUID4
    created_by: dict | None = None
    updated_by: dict | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["based_on"] = obj.based_on.external_id
        mapping["about"] = obj.about.external_id
        mapping["part_of"] = obj.part_of.external_id if obj.part_of else None

        if obj.created_by:
            mapping["created_by"] = UserSpec.serialize(obj.created_by).to_json()
        if obj.updated_by:
            mapping["updated_by"] = UserSpec.serialize(obj.updated_by).to_json()


class CommunicationRetrieveSpec(CommunicationListSpec):
    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        super().perform_extra_serialization(mapping, obj)

        if obj.payload:
            mapping["payload"] = []
            for payload in obj.payload:
                parsed = {**payload}
                if payload.get("attachment"):
                    attachment = FileUpload.objects.get(
                        external_id=payload.get("attachment")
                    )
                    parsed["attachment"] = FileUploadRetrieveSpec.serialize(
                        attachment
                    ).to_json()
                mapping["payload"].append(parsed)


class CommunicationRequestRetrieveSpec(EMRResource):
    __model__ = CommunicationRequest
    __exclude__ = ["based_on", "part_of", "about"]

    id: UUID4 | None = None

    identifier: str
    status: str
    priority: str | None = None
    category: list[dict] = []
    authored_on: datetime | None = None
    payload: list[dict] = []
    replaces: UUID4 | None = None
    based_on: UUID4
    about: UUID4

    created_date: datetime | None = None
    modified_date: datetime | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["based_on"] = obj.based_on.external_id
        mapping["about"] = obj.about.external_id
        mapping["replaces"] = obj.replaces.external_id if obj.replaces else None
