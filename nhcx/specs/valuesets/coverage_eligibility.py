from care.emr.registries.care_valueset.care_valueset import CareValueset
from care.emr.resources.common.valueset import ValueSetCompose, ValueSetInclude
from care.emr.resources.valueset.spec import ValueSetStatusOptions

NHCX_COVERAGE_ELIGIBILITY_REQUEST_ITEM_DIAGNOSIS_CODE_VALUESET = CareValueset(
    "Coverage Eligibility Request Item Diagnosis Code",
    "system-coverage-eligibility-request-item-diagnosis-code",
    ValueSetStatusOptions.active.value,
)

NHCX_COVERAGE_ELIGIBILITY_REQUEST_ITEM_DIAGNOSIS_CODE_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="http://snomed.info/sct",
                filter=[{"property": "concept", "op": "is-a", "value": "404684003"}],
            )
        ]
    )
)

NHCX_COVERAGE_ELIGIBILITY_REQUEST_ITEM_DIAGNOSIS_CODE_VALUESET.register_as_system()


NHCX_COVERAGE_ELIGIBILITY_REQUEST_ITEM_CATEGORY_VALUESET = CareValueset(
    "Coverage Eligibility Request Item Category",
    "system-coverage-eligibility-request-item-category",
    ValueSetStatusOptions.active.value,
)

NHCX_COVERAGE_ELIGIBILITY_REQUEST_ITEM_CATEGORY_VALUESET.register_valueset(
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
        # FIXME: Enable this after testing and fix it
        # exclude=[
        #     ValueSetInclude(
        #         system="http://snomed.info/sct",
        #         concept=[
        #             {
        #                 "code": "224891009",
        #                 "display": "Healthcare services (qualifier value)",
        #             },
        #         ],
        #     )
        # ],
    )
)

NHCX_COVERAGE_ELIGIBILITY_REQUEST_ITEM_CATEGORY_VALUESET.register_as_system()


NHCX_COVERAGE_ELIGIBILITY_REQUEST_PRODUCT_OR_SERVICE_VALUESET = CareValueset(
    "Coverage Eligibility Request Product or Service",
    "system-coverage-eligibility-request-product-or-service",
    ValueSetStatusOptions.active.value,
)

NHCX_COVERAGE_ELIGIBILITY_REQUEST_PRODUCT_OR_SERVICE_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="http://snomed.info/sct",
                filter=[{"property": "concept", "op": "is-a", "value": "387713003"}],
            ),
            ValueSetInclude(
                system="http://snomed.info/sct",
                filter=[{"property": "concept", "op": "is-a", "value": "305056002"}],
            ),
            ValueSetInclude(
                system="http://snomed.info/sct",
                filter=[{"property": "concept", "op": "is-a", "value": "43741000"}],
            ),
            ValueSetInclude(
                system="http://snomed.info/sct",
                filter=[{"property": "concept", "op": "is-a", "value": "285201006"}],
            ),
            ValueSetInclude(
                system="http://snomed.info/sct",
                filter=[{"property": "concept", "op": "is-a", "value": "63653004"}],
            ),
            ValueSetInclude(
                system="http://snomed.info/sct",
                filter=[{"property": "concept", "op": "is-a", "value": "440654001"}],
            ),
            ValueSetInclude(
                system="http://snomed.info/sct",
                filter=[{"property": "concept", "op": "is-a", "value": "440655000"}],
            ),
        ],
        # FIXME: Enable this after testing and fix it
        # exclude=[
        #     ValueSetInclude(
        #         system="http://snomed.info/sct",
        #         concept=[
        #             {
        #                 "code": "387713003",
        #                 "display": "Surgical procedure (procedure)",
        #             },
        #             {
        #                 "code": "63653004",
        #                 "display": "Biomedical device (physical object)",
        #             },
        #             {
        #                 "code": "305056002",
        #                 "display": "Admission procedure (procedure)",
        #             },
        #             {
        #                 "code": "43741000",
        #                 "display": "Site of care (environment)",
        #             },
        #         ],
        #     ),
        # ],
    )
)

NHCX_COVERAGE_ELIGIBILITY_REQUEST_PRODUCT_OR_SERVICE_VALUESET.register_as_system()
