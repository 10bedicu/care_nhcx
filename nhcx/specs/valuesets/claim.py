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


NHCX_CLAIM_PRODUCT_OR_SERVICE_VALUESET = (
    NHCX_CLAIM_TYPE_VALUESET  # FIXME: Remove this after testing
)
