from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from care.emr.models.base import EMRBaseModel
from care.emr.models.diagnostic_report import DiagnosticReport
from care.emr.models.encounter import Encounter
from care.emr.models.file_upload import FileUpload
from care.emr.models.invoice import Invoice
from care.emr.models.patient import Patient
from care.emr.models.questionnaire import QuestionnaireResponse

if TYPE_CHECKING:
    from uuid import UUID

    from abdm.utils.fhir.fhir import Fhir as AbdmFhir
    from fhir.resources.R4B.bundle import Bundle


@dataclass(frozen=True)
class StructuredResourceHandler:
    resource_type: str
    title: str
    resolve: Callable[[UUID, Patient], EMRBaseModel | None]
    build_record: Callable[[AbdmFhir, EMRBaseModel], Bundle]
    build_title: Callable[[EMRBaseModel], str | None]

    def resolve_title(self, model: EMRBaseModel) -> str:
        return self.build_title(model) or self.title


def _resolve_diagnostic_report(
    resource_id: UUID, patient: Patient
) -> DiagnosticReport | None:
    return DiagnosticReport.objects.filter(
        external_id=resource_id, patient=patient
    ).first()


def _resolve_questionnaire_response(
    resource_id: UUID, patient: Patient
) -> QuestionnaireResponse | None:
    return QuestionnaireResponse.objects.filter(
        external_id=resource_id, patient=patient
    ).first()


def _diagnostic_report_title(model: DiagnosticReport) -> str | None:
    code = model.code or {}
    return (
        code.get("display")
        or code.get("code")
        or getattr(model.service_request, "title", None)
    )


def _questionnaire_response_title(model: QuestionnaireResponse) -> str | None:
    return getattr(model.questionnaire, "title", None) if model.questionnaire else None


_INPATIENT_ENCOUNTER_CLASSES = ("imp", "obsenc", "emerg")


def _resolve_encounter(resource_id: UUID, patient: Patient) -> Encounter | None:
    return Encounter.objects.filter(external_id=resource_id, patient=patient).first()


def _encounter_is_inpatient(model: Encounter) -> bool:
    return (model.encounter_class or "") in _INPATIENT_ENCOUNTER_CLASSES


def _build_encounter_record(fhir: AbdmFhir, model: Encounter) -> Bundle:
    if _encounter_is_inpatient(model):
        return fhir.create_discharge_summary_record(model)
    return fhir.create_op_consult_record(model)


def _encounter_title(model: Encounter) -> str | None:
    return (
        "Discharge Summary"
        if _encounter_is_inpatient(model)
        else "OP Consultation Record"
    )


def _resolve_invoice(resource_id: UUID, patient: Patient) -> Invoice | None:
    return Invoice.objects.filter(external_id=resource_id, patient=patient).first()


def _invoice_title(model: Invoice) -> str | None:
    return model.title or model.number


def _resolve_file(resource_id: UUID, patient: Patient) -> FileUpload | None:
    file = FileUpload.objects.filter(external_id=resource_id).first()
    if not file:
        return None
    if file.file_type == "patient" and str(file.associating_id) == str(
        patient.external_id
    ):
        return file
    if (
        file.file_type == "encounter"
        and Encounter.objects.filter(
            external_id=file.associating_id, patient=patient
        ).exists()
    ):
        return file
    return None


def _file_title(model: FileUpload) -> str | None:
    return model.name or (model.internal_name or "").split(".")[0] or None


REGISTRY: dict[str, StructuredResourceHandler] = {
    "diagnostic_report": StructuredResourceHandler(
        resource_type="diagnostic_report",
        title="Diagnostic Report",
        resolve=_resolve_diagnostic_report,
        build_record=lambda fhir, model: fhir.create_diagnostic_report_record(model),
        build_title=_diagnostic_report_title,
    ),
    "questionnaire_response": StructuredResourceHandler(
        resource_type="questionnaire_response",
        title="Questionnaire Response",
        resolve=_resolve_questionnaire_response,
        build_record=lambda fhir, model: fhir.create_wellness_record(model),
        build_title=_questionnaire_response_title,
    ),
    "encounter": StructuredResourceHandler(
        resource_type="encounter",
        title="Encounter Record",
        resolve=_resolve_encounter,
        build_record=_build_encounter_record,
        build_title=_encounter_title,
    ),
    "invoice": StructuredResourceHandler(
        resource_type="invoice",
        title="Invoice Record",
        resolve=_resolve_invoice,
        build_record=lambda fhir, model: fhir.create_invoice_record(model),
        build_title=_invoice_title,
    ),
    "file": StructuredResourceHandler(
        resource_type="file",
        title="Document",
        resolve=_resolve_file,
        build_record=lambda fhir, model: fhir.create_health_document_record(model),
        build_title=_file_title,
    ),
}


def get_handler(resource_type: str) -> StructuredResourceHandler | None:
    return REGISTRY.get(resource_type)
