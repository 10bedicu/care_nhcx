from typing import Literal

from pydantic import BaseModel


class AbhaBiometricAuthInitBody(BaseModel):
    authMode: Literal["FINGERPRINT", "IRIS", "FACE_AUTH"] = "FINGERPRINT"
    abhaNumber: str
    payerId: str
    process: Literal["Preauth", "Discharge"] = "Preauth"


class AbhaBiometricAuthInitResponse(BaseModel):
    txnId: str
    authMode: Literal["FINGERPRINT", "IRIS", "FACE_AUTH"] | None
    message: str
    status: Literal["success", "error"] | None


class AbhaBiometricAuthVerifyBody(BaseModel):
    txnId: str
    authMode: Literal["FINGERPRINT", "IRIS", "FACE_AUTH"] = "FINGERPRINT"
    authData: str
    payerId: str
    process: Literal["Preauth", "Discharge"] = "Preauth"


class Account(BaseModel):
    ABHANumber: str
    preferredAbhaAddress: str
    name: str
    gender: str | None
    dob: str | None
    verifiedStatus: str | None
    verificationType: str | None
    status: Literal["ACTIVE"]
    profilePhoto: str | None


class AbhaBiometricAuthVerifyResponse(BaseModel):
    txnId: str
    authResult: Literal["success", "error"]
    message: str
    token: str
    refreshToken: str
    expiresIn: int
    refreshExpiresIn: int
    accounts: list[Account]
