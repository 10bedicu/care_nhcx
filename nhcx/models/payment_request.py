payment = {
    "resourceType": "Bundle",
    "id": "5e96fc24-ae90-4390-8b76-2c3b24c73f8c",
    "meta": {
        "lastUpdated": "2025-08-05T10:41:56.043+05:30",
        "tag": [
            {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
                "code": "SUBSETTED",
                "display": "subsetted",
            }
        ],
    },
    "identifier": {
        "system": "https://dummypayer.nha.gov.in",
        "value": "0fa5ce71-13ce-4909-9f08-c2fe274a5ea4",
    },
    "type": "collection",
    "timestamp": "2025-08-05T10:41:56.043+05:30",
    "entry": [
        {
            "id": "7fb75d96-c92b-41c4-b44e-cabe419e3fbc",
            "fullUrl": "https://dummypayer.nha.gov.in/Task/7fb75d96-c92b-41c4-b44e-cabe419e3fbc",
            "resource": {
                "resourceType": "Task",
                "id": "7fb75d96-c92b-41c4-b44e-cabe419e3fbc",
                "meta": {
                    "tag": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
                            "code": "SUBSETTED",
                            "display": "subsetted",
                        }
                    ]
                },
                "identifier": [
                    {
                        "system": "https://dummypayer.nha.gov.in/Task/5e96fc24-ae90-4390-8b76-2c3b24c73f8c",
                        "value": "5e96fc24-ae90-4390-8b76-2c3b24c73f8c",
                    }
                ],
                "status": "completed",
                "intent": "proposal",
                "code": {
                    "coding": [
                        {
                            "system": "http://hl7.org/fhir/CodeSystem/task-code",
                            "code": "approve",
                            "display": "Activate/approve the focal resource",
                        }
                    ]
                },
                "requester": {
                    "reference": "https://dummypayer.nha.gov.in/Organization/1000003538",
                    "display": "Organization",
                },
                "input": [
                    {
                        "type": {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/financialtaskinputtype",
                                    "code": "reference",
                                    "display": "Reference Number",
                                }
                            ]
                        },
                        "valueReference": {
                            "reference": "https://dummypayer.nha.gov.in/PaymentNotice/e98f6440-18d7-480f-a46c-ca44bc4ec1ed",
                            "display": "PaymentNotice",
                        },
                    }
                ],
            },
        },
        {
            "id": "1000003538",
            "fullUrl": "https://dummypayer.nha.gov.in/Organization/1000003538",
            "resource": {
                "resourceType": "Organization",
                "id": "1000003538",
                "meta": {
                    "tag": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
                            "code": "SUBSETTED",
                            "display": "subsetted",
                        }
                    ]
                },
                "identifier": [
                    {
                        "type": {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                    "code": "NIIP",
                                    "display": "National Insurance Payor Identifier (Payor)",
                                }
                            ]
                        },
                        "system": "https://facility.abdm.gov.in",
                        "value": "1000003538",
                    }
                ],
                "active": True,
                "type": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                                "code": "pay",
                                "display": "Payer",
                            }
                        ]
                    }
                ],
                "name": "NHCX Payer",
            },
        },
        {
            "id": "e98f6440-18d7-480f-a46c-ca44bc4ec1ed",
            "fullUrl": "https://dummypayer.nha.gov.in/PaymentNotice/e98f6440-18d7-480f-a46c-ca44bc4ec1ed",
            "resource": {
                "resourceType": "PaymentNotice",
                "id": "e98f6440-18d7-480f-a46c-ca44bc4ec1ed",
                "meta": {
                    "tag": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
                            "code": "SUBSETTED",
                            "display": "subsetted",
                        }
                    ]
                },
                "identifier": [
                    {
                        "system": "https://dummypayer.nha.gov.in/PaymentNotice/5e96fc24-ae90-4390-8b76-2c3b24c73f8c",
                        "value": "5e96fc24-ae90-4390-8b76-2c3b24c73f8c",
                    }
                ],
                "status": "active",
                "created": "2025-08-05T10:41:56+05:30",
                "payment": {
                    "reference": "https://dummypayer.nha.gov.in/PaymentReconciliation/8475d283-a3f8-4732-890b-9411099841fe",
                    "display": "PaymentReconciliation",
                },
                "payee": {
                    "reference": "https://dummypayer.nha.gov.in/Organization/1000003538",
                    "display": "Organization",
                },
                "recipient": {
                    "reference": "urn:uuid:7a9e1df9-f340-4267-911e-6245602fc086",
                    "display": "Organization",
                },
                "amount": {"value": 609453, "currency": "INR"},
                "paymentStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/paymentstatus",
                            "code": "paid",
                            "display": "Paid",
                        }
                    ]
                },
            },
        },
        {
            "id": "7a9e1df9-f340-4267-911e-6245602fc086",
            "fullUrl": "urn:uuid:7a9e1df9-f340-4267-911e-6245602fc086",
            "resource": {
                "resourceType": "Organization",
                "id": "7a9e1df9-f340-4267-911e-6245602fc086",
                "meta": {
                    "tag": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
                            "code": "SUBSETTED",
                            "display": "subsetted",
                        }
                    ]
                },
                "identifier": [
                    {
                        "type": {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                    "code": "PRN",
                                    "display": "Provider number",
                                }
                            ]
                        },
                        "system": "https://provider.in",
                        "value": "1000004181@hcx",
                    }
                ],
                "active": True,
                "type": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                                "code": "prov",
                                "display": "Healthcare Provider",
                            }
                        ]
                    }
                ],
                "name": "1000004181@hcx Provider",
            },
        },
        {
            "id": "8475d283-a3f8-4732-890b-9411099841fe",
            "fullUrl": "https://dummypayer.nha.gov.in/PaymentReconciliation/8475d283-a3f8-4732-890b-9411099841fe",
            "resource": {
                "resourceType": "PaymentReconciliation",
                "id": "8475d283-a3f8-4732-890b-9411099841fe",
                "meta": {
                    "tag": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationValue",
                            "code": "SUBSETTED",
                            "display": "subsetted",
                        }
                    ]
                },
                "identifier": [
                    {
                        "system": "https://dummypayer.nha.gov.in/PaymentReconciliation/5e96fc24-ae90-4390-8b76-2c3b24c73f8c",
                        "value": "5e96fc24-ae90-4390-8b76-2c3b24c73f8c",
                    }
                ],
                "status": "active",
                "created": "2025-08-05T10:41:56+05:30",
                "paymentIssuer": {
                    "reference": "https://dummypayer.nha.gov.in/Organization/1000003538",
                    "display": "Organization",
                },
                "request": {
                    "reference": "https://dummypayer.nha.gov.in/Task/5e96fc24-ae90-4390-8b76-2c3b24c73f8c",
                    "display": "Task",
                },
                "requestor": {
                    "reference": "urn:uuid:7a9e1df9-f340-4267-911e-6245602fc086",
                    "display": "Organization",
                },
                "outcome": "complete",
                "paymentDate": "2025-08-05",
                "paymentAmount": {"value": 609453, "currency": "INR"},
            },
        },
    ],
}
