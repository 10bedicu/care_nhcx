from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from care.emr.models.base import EMRBaseModel
from care.emr.models.diagnostic_report import DiagnosticReport
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
}


def get_handler(resource_type: str) -> StructuredResourceHandler | None:
    return REGISTRY.get(resource_type)
