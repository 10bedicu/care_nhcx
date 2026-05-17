"""
Ingest an NDHM InsurancePlan FHIR bundle into the relational model split
defined in ``nhcx.models.insurance_plan``.

A single PMJAY payload expands to ~25-30k rows (see scaling notes in models).
Every level is materialised via ``bulk_create`` inside one transaction so the
end-to-end ingestion stays within a few seconds.
"""

from datetime import datetime

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from nhcx.models.insurance_plan import (
    ClaimCondition,
    ClaimExclusion,
    ClaimExtensionBase,
    ClaimSupportingInfoRequirement,
    CostQualifierType,
    InsurancePlan,
    InsurancePlanCoverage,
    InsurancePlanCoverageBenefit,
    InsurancePlanCoverageBenefitLimit,
    InsurancePlanPlan,
    InsurancePlanPlanGeneralCost,
    InsurancePlanPlanSpecificCost,
    InsurancePlanPlanSpecificCostBenefit,
    InsurancePlanPlanSpecificCostBenefitCost,
    InsurancePlanPlanSpecificCostBenefitCostQualifier,
    InsurancePlanQuestionnaire,
    _flatten_code,
)
from nhcx.models.task import Task

CLAIM_EXCLUSION_URL = (
    "https://nrces.in/ndhm/fhir/r4/StructureDefinition/Claim-Exclusion"
)
CLAIM_CONDITION_URL = (
    "https://nrces.in/ndhm/fhir/r4/StructureDefinition/Claim-Condition"
)
CLAIM_SUPPORTING_INFO_URL = (
    "https://nrces.in/ndhm/fhir/r4/StructureDefinition/Claim-SupportingInfoRequirement"
)

# Sub-extension URL aliases used across NDHM / PMJAY payloads.
_SUPPORTING_INFO_CATEGORY_KEYS = {"category", "SupportInfoCategory"}
_SUPPORTING_INFO_CODE_KEYS = {"code", "SupportInfoCode"}
_SUPPORTING_INFO_DOC_URL_KEYS = {
    "documentationUrl",
    "DocumentationUrl",
    "documentation",
}
_EXCLUSION_CATEGORY_KEYS = {"category", "ExclusionCategory"}
_EXCLUSION_STATEMENT_KEYS = {"statements", "ExclusionStatement", "statement"}
_EXCLUSION_ITEMS_KEYS = {"items", "ExclusionCode", "item"}

# Substring fragments in the qualifier system URI used to normalise the
# polymorphic CostQualifierType across insurers.
_QUALIFIER_SYSTEM_TO_TYPE = (
    ("stratification", CostQualifierType.STRATIFICATION),
    ("implant", CostQualifierType.IMPLANT),
    ("investigation", CostQualifierType.INVESTIGATION),
    ("medicine", CostQualifierType.MEDICINE),
)


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except (TypeError, ValueError):
        return None


def _resolve_reference(entries, reference):
    """Resolve a FHIR Reference dict against a Bundle's entries.

    NDHM bundles vary: the reference may match an entry's fullUrl exactly
    or its trailing path segment must match the resource id.
    """
    if not reference or not isinstance(reference, dict):
        return None
    ref = reference.get("reference")
    if not ref:
        return None
    tail = ref.rsplit("/", 1)[-1]
    for entry in entries:
        if entry.get("fullUrl") == ref:
            return entry.get("resource") or {}
        res = entry.get("resource") or {}
        if res.get("id") and res.get("id") == tail:
            return res
    return None


def _qualifier_type_for(qualifier_concept):
    if not qualifier_concept:
        return CostQualifierType.OTHER
    coding = (qualifier_concept.get("coding") or [{}])[0]
    system = (coding.get("system") or "").lower()
    for fragment, qualifier_type in _QUALIFIER_SYSTEM_TO_TYPE:
        if fragment in system:
            return qualifier_type
    return CostQualifierType.OTHER


def _value_string(sub_extension):
    """Return the first populated value* of a FHIR sub-extension as a string."""
    for key in (
        "valueString",
        "valueCode",
        "valueUrl",
        "valueUri",
        "valueInteger",
        "valueBoolean",
        "valueDecimal",
    ):
        if key in sub_extension:
            value = sub_extension[key]
            return value if isinstance(value, str) else str(value)
    return None


class _ExtensionParser:
    """Convert FHIR `extension[]` lists into unsaved Claim-* model instances.

    Caches ContentType + ExtensionLevel lookups per parent model so a 2,400-
    benefit payload doesn't hit ``django_content_type`` thousands of times.
    """

    def __init__(self):
        self._ct_cache = {}
        self._level_cache = {}

    def parse(self, fhir_node, parent_model_cls, parent_pk):
        """Yield (model_cls, instance) for each Claim-* extension on `fhir_node`."""
        extensions = fhir_node.get("extension") or []
        if not extensions:
            return
        ct = self._ct_for(parent_model_cls)
        level = self._level_for(parent_model_cls)
        common = {
            "parent_content_type": ct,
            "parent_object_id": parent_pk,
            "level": level,
        }
        for ext in extensions:
            url = ext.get("url", "")
            if url == CLAIM_CONDITION_URL:
                yield ClaimCondition, self._build_claim_condition(ext, common)
            elif url == CLAIM_EXCLUSION_URL:
                yield ClaimExclusion, self._build_claim_exclusion(ext, common)
            elif url == CLAIM_SUPPORTING_INFO_URL:
                yield (
                    ClaimSupportingInfoRequirement,
                    self._build_supporting_info(ext, common),
                )

    def _ct_for(self, parent_cls):
        if parent_cls not in self._ct_cache:
            self._ct_cache[parent_cls] = ContentType.objects.get_for_model(parent_cls)
        return self._ct_cache[parent_cls]

    def _level_for(self, parent_cls):
        if parent_cls not in self._level_cache:
            self._level_cache[parent_cls] = (
                ClaimExtensionBase.resolve_level_for_parent_model(parent_cls)
            )
        return self._level_cache[parent_cls]

    def _build_claim_condition(self, ext, common):
        # PMJAY models a flat property bag of named sub-extensions (each url
        # ends with the property name, value lives in valueString).
        properties = {}
        for sub in ext.get("extension") or []:
            sub_url = sub.get("url") or ""
            key = sub_url.rsplit("/", 1)[-1] if "/" in sub_url else sub_url
            if not key:
                continue
            value = _value_string(sub)
            if value is None:
                value = sub.get("valueCodeableConcept") or sub.get("valueQuantity")
            properties[key] = value
        instance = ClaimCondition(**common, properties=properties)
        instance._populate_from_properties()
        return instance

    def _build_claim_exclusion(self, ext, common):
        category = None
        statements = []
        items = None
        items_codes = []
        for sub in ext.get("extension") or []:
            key = sub.get("url") or ""
            if key in _EXCLUSION_CATEGORY_KEYS:
                category = sub.get("valueCodeableConcept") or category
            elif key in _EXCLUSION_STATEMENT_KEYS:
                statement = (
                    sub.get("valueString")
                    or sub.get("valueMarkdown")
                    or sub.get("valueCode")
                )
                if statement:
                    statements.append(statement)
            elif key in _EXCLUSION_ITEMS_KEYS:
                concept = sub.get("valueCodeableConcept")
                if concept:
                    items = concept
                    code = _flatten_code(concept)
                    if code:
                        items_codes.append(code)
        return ClaimExclusion(
            **common,
            category=category,
            category_code=_flatten_code(category),
            statements=statements,
            items=items,
            items_codes=items_codes,
        )

    def _build_supporting_info(self, ext, common):
        category = None
        code = None
        documentation_url = None
        for sub in ext.get("extension") or []:
            key = sub.get("url") or ""
            if key in _SUPPORTING_INFO_CATEGORY_KEYS:
                category = sub.get("valueCodeableConcept") or category
            elif key in _SUPPORTING_INFO_CODE_KEYS:
                code = sub.get("valueCodeableConcept") or code
            elif key in _SUPPORTING_INFO_DOC_URL_KEYS:
                documentation_url = (
                    sub.get("valueUrl")
                    or sub.get("valueUri")
                    or sub.get("valueString")
                )
        return ClaimSupportingInfoRequirement(
            **common,
            category=category,
            category_code=_flatten_code(category),
            code=code,
            code_code=_flatten_code(code),
            documentation_url=documentation_url,
        )


class InsurancePlanIngestor:
    """Materialise a FHIR InsurancePlan bundle into the relational tree.

    Usage::

        InsurancePlanIngestor(bundle, task, raw_response=..., raw_headers=...).run()
    """

    BATCH_SIZE = 1000

    def __init__(self, bundle, task: Task, raw_response=None, raw_headers=None):
        self.bundle = bundle or {}
        self.entries = self.bundle.get("entry") or []
        self.task = task
        self.raw_response = raw_response
        self.raw_headers = raw_headers or {}
        self._extension_parser = _ExtensionParser()

    @transaction.atomic
    def run(self) -> InsurancePlan:
        ip_resource = self._find_first("InsurancePlan")
        if not ip_resource:
            raise ValueError("Bundle contains no InsurancePlan resource")

        insurance_plan = self._create_insurance_plan(ip_resource)
        self._bulk_create_extensions(
            [(insurance_plan, ip_resource, InsurancePlan)]
        )
        self._ingest_coverages(ip_resource, insurance_plan)
        self._ingest_plans(ip_resource, insurance_plan)
        self._ingest_questionnaires(insurance_plan)
        return insurance_plan

    # ─── Bundle helpers ──────────────────────────────────────────────────

    def _find_first(self, resource_type):
        for entry in self.entries:
            res = entry.get("resource") or {}
            if res.get("resourceType") == resource_type:
                return res
        return None

    def _iter_resources(self, resource_type):
        for entry in self.entries:
            res = entry.get("resource") or {}
            if res.get("resourceType") == resource_type:
                yield res

    # ─── Top level ───────────────────────────────────────────────────────

    def _create_insurance_plan(self, ip_resource):
        identifiers = ip_resource.get("identifier") or []
        primary = identifiers[0] if identifiers else {}
        period = ip_resource.get("period") or {}
        owned_by = (
            _resolve_reference(self.entries, ip_resource.get("ownedBy")) or {}
        )
        administered_by = (
            _resolve_reference(self.entries, ip_resource.get("administeredBy")) or {}
        )
        return InsurancePlan.objects.create(
            request=self.task,
            fhir_id=ip_resource.get("id"),
            identifier_system=primary.get("system") or "",
            identifier_value=primary.get("value") or "",
            additional_identifiers=identifiers[1:],
            status=ip_resource.get("status") or "active",
            type=ip_resource.get("type") or [],
            name=ip_resource.get("name") or "",
            alias=ip_resource.get("alias") or [],
            period_start=_parse_date(period.get("start")),
            period_end=_parse_date(period.get("end")),
            owned_by=owned_by,
            administered_by=administered_by,
            contact=ip_resource.get("contact") or [],
            raw_bundle_id=self.bundle.get("id") or "",
            meta={
                "raw_response": self.raw_response,
                "raw_headers": self.raw_headers,
            },
        )

    # ─── Coverage subtree ────────────────────────────────────────────────

    def _ingest_coverages(self, ip_resource, insurance_plan):
        coverages_fhir = ip_resource.get("coverage") or []
        if not coverages_fhir:
            return

        coverage_rows = InsurancePlanCoverage.objects.bulk_create(
            [
                InsurancePlanCoverage(
                    insurance_plan=insurance_plan,
                    fhir_element_id=c.get("id") or "",
                    type=c.get("type") or {},
                    type_code=_flatten_code(c.get("type")),
                )
                for c in coverages_fhir
            ],
            batch_size=self.BATCH_SIZE,
        )

        benefit_rows = []
        benefit_fhir = []
        for cov_row, cov_fhir in zip(coverage_rows, coverages_fhir):
            for b in cov_fhir.get("benefit") or []:
                benefit_rows.append(
                    InsurancePlanCoverageBenefit(
                        coverage=cov_row,
                        fhir_element_id=b.get("id") or "",
                        type=b.get("type") or {},
                        type_code=_flatten_code(b.get("type")),
                        requirement=b.get("requirement") or "",
                    )
                )
                benefit_fhir.append(b)
        if benefit_rows:
            benefit_rows = InsurancePlanCoverageBenefit.objects.bulk_create(
                benefit_rows, batch_size=self.BATCH_SIZE
            )

        limit_rows = []
        for benefit_row, b_fhir in zip(benefit_rows, benefit_fhir):
            for lim in b_fhir.get("limit") or []:
                value = lim.get("value") or {}
                limit_rows.append(
                    InsurancePlanCoverageBenefitLimit(
                        benefit=benefit_row,
                        fhir_element_id=lim.get("id") or "",
                        value_amount=value.get("value"),
                        value_unit=value.get("unit") or "",
                        value_system=value.get("system") or "",
                        value_code=value.get("code") or "",
                        code=lim.get("code"),
                    )
                )
        if limit_rows:
            InsurancePlanCoverageBenefitLimit.objects.bulk_create(
                limit_rows, batch_size=self.BATCH_SIZE
            )

        targets = [
            (cov_row, cov_fhir, InsurancePlanCoverage)
            for cov_row, cov_fhir in zip(coverage_rows, coverages_fhir)
        ]
        targets += [
            (b_row, b_fhir, InsurancePlanCoverageBenefit)
            for b_row, b_fhir in zip(benefit_rows, benefit_fhir)
        ]
        self._bulk_create_extensions(targets)

    # ─── Plan subtree ────────────────────────────────────────────────────

    def _ingest_plans(self, ip_resource, insurance_plan):
        plans_fhir = ip_resource.get("plan") or []
        if not plans_fhir:
            return

        plan_rows = InsurancePlanPlan.objects.bulk_create(
            [
                InsurancePlanPlan(
                    insurance_plan=insurance_plan,
                    fhir_element_id=p.get("id") or "",
                    identifiers=p.get("identifier") or [],
                    type=p.get("type") or {},
                    type_code=_flatten_code(p.get("type")),
                )
                for p in plans_fhir
            ],
            batch_size=self.BATCH_SIZE,
        )

        general_cost_rows = []
        for plan_row, plan_fhir in zip(plan_rows, plans_fhir):
            for gc in plan_fhir.get("generalCost") or []:
                cost = gc.get("cost") or {}
                general_cost_rows.append(
                    InsurancePlanPlanGeneralCost(
                        plan=plan_row,
                        fhir_element_id=gc.get("id") or "",
                        type=gc.get("type"),
                        group_size=gc.get("groupSize"),
                        cost_value=cost.get("value"),
                        cost_currency=cost.get("currency") or "INR",
                        comment=gc.get("comment") or "",
                    )
                )
        if general_cost_rows:
            InsurancePlanPlanGeneralCost.objects.bulk_create(
                general_cost_rows, batch_size=self.BATCH_SIZE
            )

        specific_cost_rows = []
        specific_cost_fhir = []
        for plan_row, plan_fhir in zip(plan_rows, plans_fhir):
            for sc in plan_fhir.get("specificCost") or []:
                specific_cost_rows.append(
                    InsurancePlanPlanSpecificCost(
                        plan=plan_row,
                        fhir_element_id=sc.get("id") or "",
                        category=sc.get("category") or {},
                        category_code=_flatten_code(sc.get("category")),
                    )
                )
                specific_cost_fhir.append(sc)
        if specific_cost_rows:
            specific_cost_rows = (
                InsurancePlanPlanSpecificCost.objects.bulk_create(
                    specific_cost_rows, batch_size=self.BATCH_SIZE
                )
            )

        specific_cost_benefit_rows = []
        specific_cost_benefit_fhir = []
        for sc_row, sc_fhir in zip(specific_cost_rows, specific_cost_fhir):
            for b in sc_fhir.get("benefit") or []:
                specific_cost_benefit_rows.append(
                    InsurancePlanPlanSpecificCostBenefit(
                        specific_cost=sc_row,
                        fhir_element_id=b.get("id") or "",
                        type=b.get("type") or {},
                        type_code=_flatten_code(b.get("type")),
                    )
                )
                specific_cost_benefit_fhir.append(b)
        if specific_cost_benefit_rows:
            specific_cost_benefit_rows = (
                InsurancePlanPlanSpecificCostBenefit.objects.bulk_create(
                    specific_cost_benefit_rows, batch_size=self.BATCH_SIZE
                )
            )

        cost_rows = []
        cost_fhir = []
        for scb_row, b_fhir in zip(
            specific_cost_benefit_rows, specific_cost_benefit_fhir
        ):
            for c in b_fhir.get("cost") or []:
                value = c.get("value") or {}
                cost_rows.append(
                    InsurancePlanPlanSpecificCostBenefitCost(
                        benefit=scb_row,
                        fhir_element_id=c.get("id") or "",
                        type=c.get("type") or {},
                        type_code=_flatten_code(c.get("type")),
                        applicability=c.get("applicability"),
                        value_amount=value.get("value"),
                        value_unit=value.get("unit") or "",
                    )
                )
                cost_fhir.append(c)
        if cost_rows:
            cost_rows = (
                InsurancePlanPlanSpecificCostBenefitCost.objects.bulk_create(
                    cost_rows, batch_size=self.BATCH_SIZE
                )
            )

        qualifier_rows = []
        for cost_row, c_fhir in zip(cost_rows, cost_fhir):
            for q in c_fhir.get("qualifiers") or []:
                qualifier_rows.append(
                    InsurancePlanPlanSpecificCostBenefitCostQualifier(
                        cost=cost_row,
                        qualifier=q,
                        qualifier_code=_flatten_code(q),
                        qualifier_type=_qualifier_type_for(q),
                    )
                )
        if qualifier_rows:
            InsurancePlanPlanSpecificCostBenefitCostQualifier.objects.bulk_create(
                qualifier_rows, batch_size=self.BATCH_SIZE
            )

        targets = [
            (plan_row, plan_fhir, InsurancePlanPlan)
            for plan_row, plan_fhir in zip(plan_rows, plans_fhir)
        ]
        targets += [
            (scb_row, b_fhir, InsurancePlanPlanSpecificCostBenefit)
            for scb_row, b_fhir in zip(
                specific_cost_benefit_rows, specific_cost_benefit_fhir
            )
        ]
        self._bulk_create_extensions(targets)

    # ─── Polymorphic extensions ──────────────────────────────────────────

    def _bulk_create_extensions(self, targets):
        """Walk ``extension[]`` on each (parent_row, fhir_dict, model_cls) target
        and bulk-create the resulting Claim-* extension rows, one bucket per
        concrete extension model.
        """
        buckets = {
            ClaimExclusion: [],
            ClaimCondition: [],
            ClaimSupportingInfoRequirement: [],
        }
        for parent_row, parent_fhir, parent_cls in targets:
            for model_cls, instance in self._extension_parser.parse(
                parent_fhir, parent_cls, parent_row.pk
            ):
                buckets[model_cls].append(instance)
        for model_cls, rows in buckets.items():
            if rows:
                model_cls.objects.bulk_create(rows, batch_size=self.BATCH_SIZE)

    # ─── Questionnaires ──────────────────────────────────────────────────

    def _ingest_questionnaires(self, insurance_plan):
        rows = [
            InsurancePlanQuestionnaire(
                insurance_plan=insurance_plan,
                fhir_id=q.get("id") or "",
                url=q.get("url") or "",
                title=q.get("title") or "",
                status=q.get("status") or "active",
                subject_type=q.get("subjectType") or [],
                purpose=q.get("purpose") or "",
                items=q.get("item") or [],
            )
            for q in self._iter_resources("Questionnaire")
        ]
        if rows:
            InsurancePlanQuestionnaire.objects.bulk_create(
                rows, batch_size=self.BATCH_SIZE
            )
