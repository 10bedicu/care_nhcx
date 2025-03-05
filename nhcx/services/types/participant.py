from enum import Enum
from typing import Literal

from pydantic import BaseModel, RootModel


class GetPoliciesBody(BaseModel):
    identifiertype: Literal["AbhaNumber", "MemberId", "MobileNo"]
    identifiervalue: str


class Policy(BaseModel):
    sno: str
    abhanumber: str
    mobilenumber: str
    memberid: str
    payerid: str
    productid: str
    productname: str
    processingid: str


class GetPoliciesResponse(RootModel[list[Policy]]):
    pass


class SearchParticipantBody(BaseModel):
    participant_code: str


class Participant(BaseModel):
    participant_id: int
    participant_code: str
    participant_name: str
    address: str | None
    primary_email: str
    additional_email: str | None
    phone: int
    primary_mobile: int
    additional_mobile: int | None
    status: int
    signing_cert_path: str | None
    encryption_cert: str
    endpoint_url: str
    registry_id: str
    state: str
    district: str | None
    authentication_applicable: Literal["Y", "N"]


class SearchParticipantResponse(RootModel[Participant]):
    pass


class FetchCertsBody(BaseModel):
    participantid: str


class FetchCertsResponse(BaseModel):
    encryption_cert: str


class ParticipantRegistryChoices(str, Enum):
    HFR = "10001"
    NIN = "10002"
    ROHINI = "10003"
    PAYER = "10004"


class ParticipantRoleChoices(str, Enum):
    PROVIDER = "10001"
    PAYER = "10002"
    AGENCY_TPA = "10003"
    AGENCY_REGULATOR = "10004"
    RESEARCH = "10005"
    MEMBER_ISNP = "10006"
    AGENCY_SPONSOR = "10007"
    HIE_HIO_HCX = "10008"


class CreateParticipantBody(BaseModel):
    linked_registry_codes: list[ParticipantRegistryChoices]
    registryid: str
    participant_name: str
    schema_code: str | None = None
    state: str | None = None
    district: str | None = None
    roles: list[ParticipantRoleChoices]
    primaryEmail: str
    phone: list[str]
    primaryMobile: str
    signing_cert_path: str | None = None
    encryption_cert: str
    endpoint_url: str


class CreateParticipantResponse(BaseModel):
    participant_code: str


class UpdateParticipantBody(CreateParticipantBody):
    pass


class UpdateParticipantResponse(BaseModel):
    pass
