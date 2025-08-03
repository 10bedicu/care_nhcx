from care.emr.registries.care_valueset.care_valueset import CareValueset
from care.emr.resources.common.valueset import ValueSetCompose, ValueSetInclude
from care.emr.resources.valueset.spec import ValueSetStatusOptions

NHCX_CLAIM_TYPE_VALUESET = CareValueset(
    "Claim Type", "system-claim-type", ValueSetStatusOptions.active.value
)

NHCX_CLAIM_TYPE_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="http://snomed.info/sct",
                concept=[
                    {
                        "code": "737481003",
                        "display": "Inpatient care management (procedure)",
                    },
                    {"code": "108241001", "display": "Dialysis procedure (procedure)"},
                    {"code": "367336001", "display": "Chemotherapy (procedure)"},
                    {
                        "code": "713603004",
                        "display": "Advance care planning (procedure)",
                    },
                    {
                        "code": "710967003",
                        "display": "Management of health status after discharge from hospital (procedure)",
                    },
                    {"code": "409972000", "display": "Pre-hospital care (situation)"},
                    {
                        "code": "51032003",
                        "display": "Hospital admission, donor for transplant organ (procedure)",
                    },
                    {
                        "code": "49122002",
                        "display": "Ambulance, device (physical object)",
                    },
                    {
                        "code": "275926002",
                        "display": "Screening - health check (procedure)",
                    },
                    {
                        "code": "33879002",
                        "display": "Administration of vaccine to produce active immunity (procedure)",
                    },
                    {
                        "code": "60689008",
                        "display": "Home care of patient (regime/therapy)",
                    },
                    {
                        "code": "410225009",
                        "display": "Mental health care management (procedure)",
                    },
                    {
                        "code": "410083007",
                        "display": "Rehabilitation therapy management (procedure)",
                    },
                    {
                        "code": "737492002",
                        "display": "Outpatient care management (procedure)",
                    },
                    {"code": "15220000", "display": "Laboratory test (procedure)"},
                    {"code": "763158003", "display": "Medicinal product (product)"},
                    {
                        "code": "410345004",
                        "display": "Medical/dental care case management (procedure)",
                    },
                    {"code": "385907003", "display": "Eye care management (procedure)"},
                    {
                        "code": "737850002",
                        "display": "Day care case management (procedure)",
                    },
                    {
                        "code": "1259939000",
                        "display": "Ayurveda medicine (qualifier value)",
                    },
                    {
                        "code": "1259938008",
                        "display": "Homeopathic medicine (qualifier value)",
                    },
                    {
                        "code": "1259940003",
                        "display": "Yoga medicine (qualifier value)",
                    },
                    {
                        "code": "1259218001",
                        "display": "Unani medicine (qualifier value)",
                    },
                    {
                        "code": "1259219009",
                        "display": "Siddha medicine (qualifier value)",
                    },
                ],
            ),
        ]
    )
)

NHCX_CLAIM_TYPE_VALUESET.register_as_system()


NHCX_CLAIM_ITEM_CATEGORY_VALUESET = CareValueset(
    "Claim Item Category",
    "system-claim-item-category",
    ValueSetStatusOptions.active.value,
)

NHCX_CLAIM_ITEM_CATEGORY_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="http://snomed.info/sct",
                concept=[
                    {
                        "code": "63653004",
                        "display": "Biomedical device (physical object)",
                    },
                    {
                        "code": "43741000",
                        "display": "Site of care (environment)",
                    },
                    {
                        "code": "373873005",
                        "display": "Pharmaceutical / biologic product (product)",
                    },
                    {
                        "code": "14734007",
                        "display": "Administrative procedure (procedure)",
                    },
                    {
                        "code": "105455006",
                        "display": "Donor for medical or surgical procedure (person)",
                    },
                ],
            ),
            ValueSetInclude(
                system="http://snomed.info/sct",
                filter=[{"property": "concept", "op": "is-a", "value": "224891009"}],
            ),
        ],
        exclude=[
            ValueSetInclude(
                system="http://snomed.info/sct",
                concept=[
                    {
                        "code": "224891009",
                        "display": "Healthcare services (qualifier value)",
                    },
                ],
            )
        ],
    )
)

NHCX_CLAIM_ITEM_CATEGORY_VALUESET.register_as_system()


NHCX_CLAIM_PRODUCT_OR_SERVICE_VALUESET = CareValueset(
    "Claim Product or Service",
    "system-claim-product-or-service",
    ValueSetStatusOptions.active.value,
)

NHCX_CLAIM_PRODUCT_OR_SERVICE_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="http://snomed.info/sct",
                filter=[
                    {"property": "concept", "op": "is-a", "value": "387713003"},
                    {"property": "concept", "op": "is-a", "value": "305056002"},
                    {"property": "concept", "op": "is-a", "value": "43741000"},
                    {"property": "concept", "op": "is-a", "value": "285201006"},
                    {"property": "concept", "op": "is-a", "value": "63653004"},
                    {"property": "concept", "op": "is-a", "value": "440654001"},
                    {"property": "concept", "op": "is-a", "value": "440655000"},
                ],
            ),
        ],
        exclude=[
            ValueSetInclude(
                system="http://snomed.info/sct",
                concept=[
                    {
                        "code": "387713003",
                        "display": "Surgical procedure (procedure)",
                    },
                    {
                        "code": "63653004",
                        "display": "Biomedical device (physical object)",
                    },
                    {
                        "code": "305056002",
                        "display": "Admission procedure (procedure)",
                    },
                    {
                        "code": "43741000",
                        "display": "Site of care (environment)",
                    },
                ],
            ),
        ],
    )
)

NHCX_CLAIM_PRODUCT_OR_SERVICE_VALUESET.register_as_system()


NHCX_CLAIM_PROGRAM_CODE_VALUESET = CareValueset(
    "Claim Program Code",
    "system-claim-program-code",
    ValueSetStatusOptions.active.value,
)

NHCX_CLAIM_PROGRAM_CODE_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-program-code",
            )
        ]
    )
)

NHCX_CLAIM_PROGRAM_CODE_VALUESET.register_as_system()


NHCX_CLAIM_ACCIDENT_TYPE_VALUESET = CareValueset(
    "Claim Accident Type",
    "system-claim-accident-type",
    ValueSetStatusOptions.active.value,
)

NHCX_CLAIM_ACCIDENT_TYPE_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="http://terminology.hl7.org/CodeSystem/v3-ActCode",
                filter=[
                    {"property": "concept", "op": "is-a", "value": "_ActIncidentCode"}
                ],
            )
        ],
        exclude=[
            ValueSetInclude(
                system="http://terminology.hl7.org/CodeSystem/v3-ActCode",
                concept=[{"code": "_ActIncidentCode", "display": "ActIncidentCode"}],
            )
        ],
    )
)

NHCX_CLAIM_ACCIDENT_TYPE_VALUESET.register_as_system()


NHCX_CLAIM_CARE_TEAM_ROLE_VALUESET = CareValueset(
    "Claim Care Team Role",
    "system-claim-care-team-role",
    ValueSetStatusOptions.active.value,
)

NHCX_CLAIM_CARE_TEAM_ROLE_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="http://snomed.info/sct",
                concept=[
                    {
                        "code": "405623001",
                        "display": "Assigned practitioner (occupation)",
                    },
                    {"code": "768839008", "display": "Consultant (occupation)"},
                    {"code": "88189002", "display": "Anesthesiologist (occupation)"},
                    {
                        "code": "223366009",
                        "display": "Healthcare professional (occupation)",
                    },
                ],
            )
        ]
    )
)

NHCX_CLAIM_CARE_TEAM_ROLE_VALUESET.register_as_system()


NHCX_CLAIM_RELATED_RELATIONSHIP_VALUESET = CareValueset(
    "Claim Related Relationship",
    "system-claim-related-relationship",
    ValueSetStatusOptions.active.value,
)

NHCX_CLAIM_RELATED_RELATIONSHIP_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            # ValueSetInclude(
            #     system="https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-related-claim-relationship-code",
            # ),
            ValueSetInclude(
                system="http://terminology.hl7.org/CodeSystem/ex-relatedclaimrelationship",
                concept=[
                    {"code": "associated", "display": "Associated Claim"},
                    {"code": "prior", "display": "Prior Claim"},
                ],
            ),
        ]
    )
)

NHCX_CLAIM_RELATED_RELATIONSHIP_VALUESET.register_as_system()


NHCX_CLAIM_SUPPORTING_INFO_CATEGORY_VALUESET = CareValueset(
    "Claim Supporting Info Category",
    "system-claim-supporting-info-category",
    ValueSetStatusOptions.active.value,
)

NHCX_CLAIM_SUPPORTING_INFO_CATEGORY_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-supportinginfo-category",
            )
        ]
    )
)

NHCX_CLAIM_SUPPORTING_INFO_CATEGORY_VALUESET.register_as_system()


NHCX_CLAIM_SUPPORTING_INFO_CODE_VALUESET = CareValueset(
    "Claim Supporting Info Code",
    "system-claim-supporting-info-code",
    ValueSetStatusOptions.active.value,
)

NHCX_CLAIM_SUPPORTING_INFO_CODE_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-supportinginfo-code",
            ),
            ValueSetInclude(
                system="http://terminology.hl7.org/CodeSystem/v2-0203",
                concept=[
                    {"code": "DL", "display": "Driver's license number"},
                    {"code": "PPN", "display": "Passport number"},
                ],
            ),
            ValueSetInclude(
                system="https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-identifier-type-code",
            ),
        ]
    )
)

NHCX_CLAIM_SUPPORTING_INFO_CODE_VALUESET.register_as_system()


NHCX_CLAIM_DIAGNOSIS_TYPE_VALUESET = CareValueset(
    "Claim Diagnosis Type",
    "system-claim-diagnosis-type",
    ValueSetStatusOptions.active.value,
)

NHCX_CLAIM_DIAGNOSIS_TYPE_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="http://snomed.info/sct",
                concept=[
                    {
                        "code": "148006",
                        "display": "Preliminary diagnosis (contextual qualifier) (qualifier value)",
                    },
                    {
                        "code": "47965005",
                        "display": "Differential diagnosis (contextual qualifier) (qualifier value)",
                    },
                    {
                        "code": "89100005",
                        "display": "Final diagnosis (discharge) (contextual qualifier) (qualifier value)",
                    },
                    {
                        "code": "106229004",
                        "display": "Qualifier for type of diagnosis (qualifier value)",
                    },
                ],
            )
        ]
    )
)

NHCX_CLAIM_DIAGNOSIS_TYPE_VALUESET.register_as_system()


NHCX_CLAIM_DIAGNOSIS_CODE_VALUESET = CareValueset(
    "Claim Diagnosis Code",
    "system-claim-diagnosis-code",
    ValueSetStatusOptions.active.value,
)

NHCX_CLAIM_DIAGNOSIS_CODE_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="http://snomed.info/sct",
                filter=[{"property": "concept", "op": "is-a", "value": "404684003"}],
            )
        ]
    )
)

NHCX_CLAIM_DIAGNOSIS_CODE_VALUESET.register_as_system()


NHCX_CLAIM_PROCEDURE_CODE_VALUESET = CareValueset(
    "Claim Procedure Code",
    "system-claim-procedure-code",
    ValueSetStatusOptions.active.value,
)

NHCX_CLAIM_PROCEDURE_CODE_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="http://snomed.info/sct",
                filter=[{"property": "concept", "op": "is-a", "value": "71388002"}],
            )
        ]
    )
)

NHCX_CLAIM_PROCEDURE_CODE_VALUESET.register_as_system()


NHCX_CLAIM_PROCEDURE_TYPE_VALUESET = CareValueset(
    "Claim Procedure Type",
    "system-claim-procedure-type",
    ValueSetStatusOptions.active.value,
)

NHCX_CLAIM_PROCEDURE_TYPE_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="http://terminology.hl7.org/CodeSystem/ex-procedure-type"
            )
        ]
    )
)

NHCX_CLAIM_PROCEDURE_TYPE_VALUESET.register_as_system()


NHCX_CLAIM_ACCIDENT_TYPE_VALUESET = (
    NHCX_CLAIM_TYPE_VALUESET  # FIXME: Remove this after testing
)
NHCX_CLAIM_DIAGNOSIS_TYPE_VALUESET = (
    NHCX_CLAIM_TYPE_VALUESET  # FIXME: Remove this after testing
)
NHCX_CLAIM_ITEM_CATEGORY_VALUESET = (
    NHCX_CLAIM_TYPE_VALUESET  # FIXME: Remove this after testing
)
NHCX_CLAIM_PROCEDURE_CODE_VALUESET = (
    NHCX_CLAIM_TYPE_VALUESET  # FIXME: Remove this after testing
)
NHCX_CLAIM_PROCEDURE_TYPE_VALUESET = (
    NHCX_CLAIM_TYPE_VALUESET  # FIXME: Remove this after testing
)
NHCX_CLAIM_PRODUCT_OR_SERVICE_VALUESET = (
    NHCX_CLAIM_TYPE_VALUESET  # FIXME: Remove this after testing
)
NHCX_CLAIM_PROGRAM_CODE_VALUESET = (
    NHCX_CLAIM_TYPE_VALUESET  # FIXME: Remove this after testing
)
NHCX_CLAIM_RELATED_RELATIONSHIP_VALUESET = (
    NHCX_CLAIM_TYPE_VALUESET  # FIXME: Remove this after testing
)
NHCX_CLAIM_SUPPORTING_INFO_CATEGORY_VALUESET = (
    NHCX_CLAIM_TYPE_VALUESET  # FIXME: Remove this after testing
)
NHCX_CLAIM_SUPPORTING_INFO_CODE_VALUESET = (
    NHCX_CLAIM_TYPE_VALUESET  # FIXME: Remove this after testing
)
