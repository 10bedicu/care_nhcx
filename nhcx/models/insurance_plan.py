from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models

from care.emr.models.base import EMRBaseModel


class PublicationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    RETIRED = "retired", "Retired"
    UNKNOWN = "unknown", "Unknown"


class ExtensionLevel(models.TextChoices):
    INSURANCE_PLAN = "insurance_plan", "InsurancePlan"
    COVERAGE = "coverage", "InsurancePlan.coverage"
    COVERAGE_BENEFIT = "coverage_benefit", "InsurancePlan.coverage.benefit"
    PLAN = "plan", "InsurancePlan.plan"
    PLAN_SPECIFIC_COST_BENEFIT = (
        "plan_specific_cost_benefit",
        "InsurancePlan.plan.specificCost.benefit",
    )


class CostQualifierType(models.TextChoices):
    STRATIFICATION = "stratification", "Stratification"
    IMPLANT = "implant", "Implant"
    INVESTIGATION = "investigation", "Investigation"
    MEDICINE = "medicine", "Medicine"
    OTHER = "other", "Other"


# Map ContentType.model (always lowercase) → ExtensionLevel. Drives
# ClaimExtensionBase auto-derivation of `level` from the polymorphic parent.
# Add a row whenever a new InsurancePlan* model becomes a valid attachment point.
_PARENT_MODEL_TO_LEVEL = {
    "insuranceplan": ExtensionLevel.INSURANCE_PLAN,
    "insuranceplancoverage": ExtensionLevel.COVERAGE,
    "insuranceplancoveragebenefit": ExtensionLevel.COVERAGE_BENEFIT,
    "insuranceplanplan": ExtensionLevel.PLAN,
    "insuranceplanplanspecificcostbenefit": ExtensionLevel.PLAN_SPECIFIC_COST_BENEFIT,
}


def _flatten_code(codeable_concept):
    """Return the first coding[].code of a FHIR CodeableConcept dict (list or dict), or ''."""
    if not codeable_concept:
        return ""
    if isinstance(codeable_concept, list):
        codeable_concept = codeable_concept[0] if codeable_concept else None
        if not codeable_concept:
            return ""
    if not isinstance(codeable_concept, dict):
        return ""
    coding = codeable_concept.get("coding") or []
    if not coding:
        return ""
    return coding[0].get("code") or ""


def _flatten_display(codeable_concept):
    """Return a human-readable label for a FHIR CodeableConcept. Prefers
    `text`, then first coding[].display, then first coding[].code, else ''."""
    if not codeable_concept:
        return ""
    if isinstance(codeable_concept, list):
        codeable_concept = codeable_concept[0] if codeable_concept else None
        if not codeable_concept:
            return ""
    if not isinstance(codeable_concept, dict):
        return ""
    text = codeable_concept.get("text")
    if text:
        return text
    coding = codeable_concept.get("coding") or []
    if not coding:
        return ""
    first = coding[0] or {}
    return first.get("display") or first.get("code") or ""


class InsurancePlan(EMRBaseModel):
    """FHIR R4 InsurancePlan resource root (NDHM profile)."""

    request = models.ForeignKey(
        "nhcx.Task", on_delete=models.CASCADE, null=False, blank=False
    )
    fhir_id = models.CharField(max_length=64, null=True, blank=True, unique=True)

    identifier_system = models.CharField(max_length=255, null=False, blank=False)
    identifier_value = models.CharField(
        max_length=128, null=False, blank=False, db_index=True
    )
    additional_identifiers = models.JSONField(default=list, null=True, blank=True)

    status = models.CharField(
        max_length=16,
        choices=PublicationStatus.choices,
        default=PublicationStatus.ACTIVE,
        db_index=True,
    )
    type = models.JSONField(default=dict, null=False, blank=False)
    type_code = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    name = models.CharField(max_length=512, null=False, blank=False, db_index=True)
    alias = models.JSONField(default=list, null=True, blank=True)

    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    # Insurer / TPA captured as full FHIR Organization payloads (display-only;
    # we do not query Organization fields directly).
    owned_by = models.JSONField(default=dict, null=False, blank=False)
    administered_by = models.JSONField(default=dict, null=True, blank=True)

    contact = models.JSONField(default=list, null=True, blank=True)

    source_system = models.CharField(
        max_length=128, null=True, blank=True, db_index=True
    )
    raw_bundle_id = models.CharField(max_length=128, null=True, blank=True)

    claim_exclusions = GenericRelation(
        "ClaimExclusion",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )
    claim_conditions = GenericRelation(
        "ClaimCondition",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )
    supporting_info_requirements = GenericRelation(
        "ClaimSupportingInfoRequirement",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )

    class Meta:
        indexes = [
            models.Index(fields=["identifier_value", "source_system"]),
            models.Index(fields=["status", "period_start", "period_end"]),
        ]

    def save(self, *args, **kwargs):
        if self.type:
            self.type_code = _flatten_code(self.type)
        super().save(*args, **kwargs)


class InsurancePlanCoverage(EMRBaseModel):
    """InsurancePlan.coverage 0..* — broad coverage category (IP / OP / ER / ...)."""

    insurance_plan = models.ForeignKey(
        InsurancePlan,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="coverages",
    )
    fhir_element_id = models.CharField(max_length=64, null=True, blank=True)
    type = models.JSONField(default=dict, null=False, blank=False)
    type_code = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    type_display = models.CharField(max_length=255, blank=True, default="")

    claim_exclusions = GenericRelation(
        "ClaimExclusion",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )
    claim_conditions = GenericRelation(
        "ClaimCondition",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )
    supporting_info_requirements = GenericRelation(
        "ClaimSupportingInfoRequirement",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )

    def save(self, *args, **kwargs):
        if self.type:
            self.type_code = _flatten_code(self.type)
            self.type_display = _flatten_display(self.type)
        super().save(*args, **kwargs)


class InsurancePlanCoverageBenefit(EMRBaseModel):
    """InsurancePlan.coverage.benefit 1..* — clinical benefit within a coverage."""

    coverage = models.ForeignKey(
        InsurancePlanCoverage,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="benefits",
    )
    fhir_element_id = models.CharField(max_length=64, null=True, blank=True)
    type = models.JSONField(default=dict, null=False, blank=False)
    type_code = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    type_display = models.CharField(
        max_length=255, blank=True, default="", db_index=True
    )
    requirement = models.TextField(null=True, blank=True)

    claim_exclusions = GenericRelation(
        "ClaimExclusion",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )
    claim_conditions = GenericRelation(
        "ClaimCondition",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )
    supporting_info_requirements = GenericRelation(
        "ClaimSupportingInfoRequirement",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )

    def save(self, *args, **kwargs):
        if self.type:
            self.type_code = _flatten_code(self.type)
            self.type_display = _flatten_display(self.type)
        super().save(*args, **kwargs)


class InsurancePlanCoverageBenefitLimit(EMRBaseModel):
    """InsurancePlan.coverage.benefit.limit 0..* — quantitative limit on a benefit."""

    benefit = models.ForeignKey(
        InsurancePlanCoverageBenefit,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="limits",
    )
    fhir_element_id = models.CharField(max_length=64, null=True, blank=True)
    value_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    value_unit = models.CharField(max_length=32, null=True, blank=True)
    value_system = models.CharField(max_length=255, null=True, blank=True)
    value_code = models.CharField(max_length=64, null=True, blank=True)
    code = models.JSONField(null=True, blank=True)


class InsurancePlanPlan(EMRBaseModel):
    """InsurancePlan.plan 0..* — coverage paired with a cost-sharing structure."""

    insurance_plan = models.ForeignKey(
        InsurancePlan,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="plans",
    )
    fhir_element_id = models.CharField(max_length=64, null=True, blank=True)
    identifiers = models.JSONField(default=list, null=True, blank=True)
    type = models.JSONField(default=dict, null=True, blank=True)
    type_code = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    claim_exclusions = GenericRelation(
        "ClaimExclusion",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )
    claim_conditions = GenericRelation(
        "ClaimCondition",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )
    supporting_info_requirements = GenericRelation(
        "ClaimSupportingInfoRequirement",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )

    def save(self, *args, **kwargs):
        if self.type:
            self.type_code = _flatten_code(self.type)
        super().save(*args, **kwargs)


class InsurancePlanPlanGeneralCost(EMRBaseModel):
    """InsurancePlan.plan.generalCost 0..* — overall sum insured for the plan."""

    plan = models.ForeignKey(
        InsurancePlanPlan,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="general_costs",
    )
    fhir_element_id = models.CharField(max_length=64, null=True, blank=True)
    type = models.JSONField(null=True, blank=True)
    group_size = models.PositiveIntegerField(null=True, blank=True)
    cost_value = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    cost_currency = models.CharField(max_length=8, default="INR")
    comment = models.TextField(null=True, blank=True)


class InsurancePlanPlanSpecificCost(EMRBaseModel):
    """InsurancePlan.plan.specificCost 0..* — specialty / benefit category bucket."""

    plan = models.ForeignKey(
        InsurancePlanPlan,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="specific_costs",
    )
    fhir_element_id = models.CharField(max_length=64, null=True, blank=True)
    category = models.JSONField(default=dict, null=False, blank=False)
    category_code = models.CharField(
        max_length=64, null=True, blank=True, db_index=True
    )

    def save(self, *args, **kwargs):
        if self.category:
            self.category_code = _flatten_code(self.category)
        super().save(*args, **kwargs)


class InsurancePlanPlanSpecificCostBenefit(EMRBaseModel):
    """InsurancePlan.plan.specificCost.benefit 0..* — package / procedure within a specialty."""

    specific_cost = models.ForeignKey(
        InsurancePlanPlanSpecificCost,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="benefits",
    )
    fhir_element_id = models.CharField(max_length=64, null=True, blank=True)
    type = models.JSONField(default=dict, null=False, blank=False)
    type_code = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    type_display = models.CharField(
        max_length=255, blank=True, default="", db_index=True
    )

    claim_exclusions = GenericRelation(
        "ClaimExclusion",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )
    claim_conditions = GenericRelation(
        "ClaimCondition",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )
    supporting_info_requirements = GenericRelation(
        "ClaimSupportingInfoRequirement",
        content_type_field="parent_content_type",
        object_id_field="parent_object_id",
    )

    def save(self, *args, **kwargs):
        if self.type:
            self.type_code = _flatten_code(self.type)
            self.type_display = _flatten_display(self.type)
        super().save(*args, **kwargs)


class InsurancePlanPlanSpecificCostBenefitCost(EMRBaseModel):
    """InsurancePlan.plan.specificCost.benefit.cost 0..* — package rate / add-on."""

    benefit = models.ForeignKey(
        InsurancePlanPlanSpecificCostBenefit,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="costs",
    )
    fhir_element_id = models.CharField(max_length=64, null=True, blank=True)
    type = models.JSONField(default=dict, null=False, blank=False)
    type_code = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    applicability = models.JSONField(null=True, blank=True)
    value_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    value_unit = models.CharField(max_length=32, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.type:
            self.type_code = _flatten_code(self.type)
        super().save(*args, **kwargs)


class InsurancePlanPlanSpecificCostBenefitCostQualifier(EMRBaseModel):
    """InsurancePlan.plan.specificCost.benefit.cost.qualifiers 0..* — add-on code."""

    cost = models.ForeignKey(
        InsurancePlanPlanSpecificCostBenefitCost,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="qualifiers",
    )
    qualifier = models.JSONField(default=dict, null=False, blank=False)
    qualifier_code = models.CharField(
        max_length=64, null=True, blank=True, db_index=True
    )
    qualifier_type = models.CharField(
        max_length=32,
        choices=CostQualifierType.choices,
        default=CostQualifierType.OTHER,
        db_index=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["qualifier_type", "qualifier_code"]),
        ]

    def save(self, *args, **kwargs):
        if self.qualifier:
            self.qualifier_code = _flatten_code(self.qualifier)
        super().save(*args, **kwargs)


class ClaimExtensionBase(EMRBaseModel):
    """
    Abstract base for FHIR Claim-* extensions (Claim-Exclusion,
    Claim-Condition, Claim-SupportingInfoRequirement). Uses a polymorphic
    GenericForeignKey so a single extension table can attach to any
    InsurancePlan tree level without coupling its schema to the parent type.
    `level` is derived from `parent_content_type` for fast filtering.

    NOTE: cascade-on-delete from the parent side requires each parent to
    declare a matching GenericRelation — see the InsurancePlan* models above.
    """

    parent_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="+",
        null=False,
        blank=False,
    )
    parent_object_id = models.PositiveBigIntegerField(db_index=True)
    parent = GenericForeignKey("parent_content_type", "parent_object_id")

    level = models.CharField(
        max_length=32,
        choices=ExtensionLevel.choices,
        null=True,
        blank=True,
        db_index=True,
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["parent_content_type", "parent_object_id"]),
        ]

    def save(self, *args, **kwargs):
        self.level = self._resolve_level() or self.level
        super().save(*args, **kwargs)

    def _resolve_level(self):
        if not self.parent_content_type_id:
            return ""
        ct = ContentType.objects.get_for_id(self.parent_content_type_id)
        return _PARENT_MODEL_TO_LEVEL.get(ct.model, "")

    @classmethod
    def resolve_level_for_parent_model(cls, parent_model):
        """Bulk-create helper: return the ExtensionLevel for a parent model class."""
        ct = ContentType.objects.get_for_model(parent_model)
        return _PARENT_MODEL_TO_LEVEL.get(ct.model, "")


class ClaimExclusion(ClaimExtensionBase):
    """Claim-Exclusion extension — excluded coverage details."""

    category = models.JSONField(null=True, blank=True)
    category_code = models.CharField(
        max_length=64, null=True, blank=True, db_index=True
    )
    statements = models.JSONField(default=list, null=True, blank=True)
    items = models.JSONField(null=True, blank=True)
    items_codes = models.JSONField(default=list, null=True, blank=True)

    class Meta(ClaimExtensionBase.Meta):
        abstract = False
        indexes = [
            *ClaimExtensionBase.Meta.indexes,
            models.Index(fields=["level", "category_code"]),
        ]


class ClaimCondition(ClaimExtensionBase):
    """
    Claim-Condition extension — conditions to satisfy for benefit eligibility.

    PMJAY sends ONE block per benefit carrying ~15 named sub-extensions
    (ProcedureType, ApprovalNotRequired, ImplantApplicable, ...). The full
    sub-extension map lands in `properties` for lossless round-trip; the
    flags most commonly queried in eligibility / pre-auth flows are also
    mirrored into typed columns by `_populate_from_properties()` so they
    can be indexed. Non-PMJAY insurers should use the generic
    `condition_type` / `code` / `description` / `value` fields instead.
    """

    properties = models.JSONField(default=dict, null=True, blank=True)

    procedure_type = models.CharField(
        max_length=64, null=True, blank=True, db_index=True
    )
    govt_reserved = models.BooleanField(null=True, blank=True)
    approval_not_required = models.BooleanField(null=True, blank=True, db_index=True)
    scheduled_tat_approval = models.BooleanField(null=True, blank=True)
    enhancement_allowed = models.BooleanField(null=True, blank=True)
    quantity_allowed = models.PositiveSmallIntegerField(null=True, blank=True)
    is_day_care = models.BooleanField(null=True, blank=True, db_index=True)
    implant_applicable = models.BooleanField(null=True, blank=True, db_index=True)
    multiple_implants_allowed = models.BooleanField(null=True, blank=True)
    maximum_implants_allowed = models.PositiveSmallIntegerField(null=True, blank=True)
    stratification_allowed = models.BooleanField(null=True, blank=True, db_index=True)
    multiple_stratification_allowed = models.BooleanField(null=True, blank=True)
    maximum_stratification_allowed = models.PositiveSmallIntegerField(
        null=True, blank=True
    )
    cyclic_procedure = models.BooleanField(null=True, blank=True)
    maximum_cycles_allowed = models.PositiveSmallIntegerField(null=True, blank=True)

    condition_type = models.JSONField(null=True, blank=True)
    code = models.JSONField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    value = models.JSONField(null=True, blank=True)

    class Meta(ClaimExtensionBase.Meta):
        abstract = False
        indexes = [
            *ClaimExtensionBase.Meta.indexes,
            models.Index(fields=["level", "procedure_type"]),
        ]

    def save(self, *args, **kwargs):
        if self.properties:
            self._populate_from_properties()
        super().save(*args, **kwargs)

    def _populate_from_properties(self):
        """Mirror PMJAY string flags from `properties` into typed columns."""
        p = self.properties or {}
        yn = self._yn_to_bool

        self.procedure_type = p.get("ProcedureType") or ""
        self.govt_reserved = yn(p.get("GovtReserved"))
        self.approval_not_required = yn(p.get("ApprovalNotRequired"))
        self.scheduled_tat_approval = yn(p.get("ScheduledTATApproval"))
        self.enhancement_allowed = yn(p.get("EnhancementAllowed"))
        self.is_day_care = yn(p.get("IsDayCare"))
        self.implant_applicable = yn(p.get("ImplantApplicable"))
        self.multiple_implants_allowed = yn(p.get("MultipleImplantsAllowed"))
        self.stratification_allowed = yn(p.get("StratificationAllowed"))
        self.multiple_stratification_allowed = yn(
            p.get("MultipleStratificationAllowed")
        )
        self.cyclic_procedure = yn(p.get("CyclicProcedure"))

        for attr, key in (
            ("quantity_allowed", "QuantityAllowed"),
            ("maximum_implants_allowed", "MaximumImplantsAllowed"),
            ("maximum_stratification_allowed", "MaximumStratificationAllowed"),
            ("maximum_cycles_allowed", "MaximumCyclesAllowed"),
        ):
            raw = p.get(key)
            if raw is None or raw == "":
                continue
            try:
                setattr(self, attr, int(raw))
            except (ValueError, TypeError):
                pass

    @staticmethod
    def _yn_to_bool(value):
        """PMJAY 'Y'/'N' → bool; anything else (including '') → None."""
        if value == "Y":
            return True
        if value == "N":
            return False
        return None


class ClaimSupportingInfoRequirement(ClaimExtensionBase):
    """Claim-SupportingInfoRequirement extension — documentation required for claim processing."""

    category = models.JSONField(null=True, blank=True)
    category_code = models.CharField(
        max_length=64, null=True, blank=True, db_index=True
    )
    code = models.JSONField(null=True, blank=True)
    code_code = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    documentation_url = models.URLField(max_length=512, null=True, blank=True)

    class Meta(ClaimExtensionBase.Meta):
        abstract = False
        indexes = [
            *ClaimExtensionBase.Meta.indexes,
            models.Index(fields=["code_code", "level"]),
        ]

    def save(self, *args, **kwargs):
        if self.category:
            self.category_code = _flatten_code(self.category)
        if self.code:
            self.code_code = _flatten_code(self.code)
        super().save(*args, **kwargs)


class InsurancePlanQuestionnaire(EMRBaseModel):
    """FHIR Questionnaire bundled alongside InsurancePlan (STGs, Past/Family History, ...)."""

    insurance_plan = models.ForeignKey(
        InsurancePlan,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="questionnaires",
    )
    fhir_id = models.CharField(max_length=64, null=True, blank=True)
    # `full_url` is the bundle entry's fullUrl (typically `urn:uuid:...` in
    # NDHM/PMJAY) — distinct from `url` (canonical). It's the join key against
    # ClaimSupportingInfoRequirement.documentation_url.
    full_url = models.CharField(max_length=512, null=True, blank=True, db_index=True)
    url = models.CharField(max_length=512, null=True, blank=True)
    title = models.CharField(max_length=512, null=False, blank=False)
    status = models.CharField(
        max_length=16,
        choices=PublicationStatus.choices,
        default=PublicationStatus.ACTIVE,
    )
    subject_type = models.JSONField(default=list, null=True, blank=True)
    purpose = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    items = models.JSONField(default=list, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["insurance_plan", "fhir_id"],
                name="uniq_ip_questionnaire_fhir_id",
            ),
        ]


class InsurancePlanBenefit(EMRBaseModel):
    """Denormalized per-plan benefit row that fuses CoverageBenefit (catalog)
    with PlanSpecificCostBenefit (pricing) for a single (insurance_plan, plan,
    coverage_type_code, type_code) tuple. Materialised by the ingestor so
    list/search/filter endpoints can hit a single indexed table.

    Source rows remain accessible via `coverage`, `specific_cost_benefit`, and
    the FHIR id list on `coverage_benefit_fhir_ids` for detail views and
    extension rollups.
    """

    insurance_plan = models.ForeignKey(
        InsurancePlan,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="benefits",
    )
    plan = models.ForeignKey(
        InsurancePlanPlan,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="benefits",
    )
    coverage = models.ForeignKey(
        InsurancePlanCoverage,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="fused_benefits",
    )

    coverage_type_code = models.CharField(max_length=64, db_index=True)
    coverage_type_display = models.CharField(max_length=255, blank=True, default="")
    type_code = models.CharField(max_length=64, db_index=True)
    type_display = models.CharField(
        max_length=255, blank=True, default="", db_index=True
    )
    plan_type_code = models.CharField(
        max_length=64, null=True, blank=True, db_index=True
    )
    plan_type_display = models.CharField(max_length=255, blank=True, default="")
    specialty_category_code = models.CharField(
        max_length=64, null=True, blank=True, db_index=True
    )
    specialty_category_display = models.CharField(max_length=255, blank=True, default="")

    # Nullable: a catalog-only row may have no priced SCB under this plan tier.
    specific_cost_benefit = models.ForeignKey(
        InsurancePlanPlanSpecificCostBenefit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fused_rows",
    )
    coverage_benefit_fhir_ids = models.JSONField(default=list, blank=True)

    min_cost = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, db_index=True
    )
    max_cost = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, db_index=True
    )
    max_limit_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, db_index=True
    )
    cost_count = models.PositiveSmallIntegerField(default=0)
    qualifier_count = models.PositiveSmallIntegerField(default=0)

    # Merge rule for the next block: SpecificCostBenefit wins on non-null,
    # then CoverageBenefit, else default.
    authorization_required = models.BooleanField(default=True, db_index=True)
    is_day_care = models.BooleanField(null=True, blank=True, db_index=True)
    implant_applicable = models.BooleanField(null=True, blank=True, db_index=True)
    stratification_allowed = models.BooleanField(null=True, blank=True, db_index=True)
    procedure_type = models.CharField(
        max_length=64, null=True, blank=True, db_index=True
    )
    has_copayment = models.BooleanField(default=False, db_index=True)
    has_deductible = models.BooleanField(default=False, db_index=True)
    has_waiting_period = models.BooleanField(default=False, db_index=True)

    has_stratification_qualifier = models.BooleanField(default=False, db_index=True)
    has_implant_qualifier = models.BooleanField(default=False, db_index=True)
    has_consumable_qualifier = models.BooleanField(default=False, db_index=True)

    has_questionnaire = models.BooleanField(default=False, db_index=True)
    questionnaire_fhir_ids = models.JSONField(default=list, blank=True)
    requires_supporting_info = models.BooleanField(default=False, db_index=True)
    supporting_info_count = models.PositiveSmallIntegerField(default=0)
    condition_count = models.PositiveSmallIntegerField(default=0)
    exclusion_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["insurance_plan", "plan", "coverage_type_code", "type_code"],
                name="uniq_ipb_per_plan",
            ),
        ]
        indexes = [
            models.Index(fields=["insurance_plan", "plan", "type_display"]),
            models.Index(fields=["insurance_plan", "plan_type_code"]),
            models.Index(fields=["insurance_plan", "coverage_type_code", "type_code"]),
        ]
