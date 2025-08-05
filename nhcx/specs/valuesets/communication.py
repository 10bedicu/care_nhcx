from care.emr.registries.care_valueset.care_valueset import CareValueset
from care.emr.resources.common.valueset import ValueSetCompose, ValueSetInclude
from care.emr.resources.valueset.spec import ValueSetStatusOptions

NHCX_COMMUNICATION_CATEGORY_VALUESET = CareValueset(
    "Communication Category",
    "system-communication-category",
    ValueSetStatusOptions.active.value,
)

NHCX_COMMUNICATION_CATEGORY_VALUESET.register_valueset(
    ValueSetCompose(
        include=[
            ValueSetInclude(
                system="http://terminology.hl7.org/CodeSystem/communication-category",
            ),
        ]
    )
)

NHCX_COMMUNICATION_CATEGORY_VALUESET.register_as_system()
