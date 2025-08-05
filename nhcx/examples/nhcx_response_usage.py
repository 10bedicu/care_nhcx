"""
Example usage of NHCX Response Pydantic models

This file demonstrates how to use the NHCX response models to create
standardized responses for NHCX callbacks.
"""

from nhcx.specs.nhcx_response import (
    EntityTypeChoices,
    NHCXResponse,
    ProtocolStatusChoices,
)
from rest_framework.response import Response


def example_success_response():
    """Example of creating a successful NHCX response"""

    # Method 1: Using create_success_response class method
    response = NHCXResponse.create_success_response(
        api_call_id="api-call-123",
        correlation_id="corr-456",
        sender_code="1000004181",
        recipient_code="1000003538@hcx",
        entity_type=EntityTypeChoices.COVERAGE_ELIGIBILITY,
        protocol_status=ProtocolStatusChoices.REQUEST_QUEUED,
    )

    print("Success Response:")
    print(response.model_dump_json(indent=2))

    return response


def example_error_response():
    """Example of creating an error NHCX response"""

    # Method 1: Using create_error_response class method
    response = NHCXResponse.create_error_response(
        api_call_id="api-call-123",
        correlation_id="corr-456",
        error_code="400",
        error_message="Decryption failed: Invalid payload",
    )

    print("Error Response:")
    print(response.model_dump_json(indent=2))

    return response


def example_from_headers():
    """Example of creating response from headers"""

    # Simulate headers from NHCX request
    headers = {
        "x-hcx-api_call_id": "api-call-789",
        "x-hcx-correlation_id": "corr-101",
        "x-hcx-sender_code": "1000004181",
        "x-hcx-recipient_code": "1000003538@hcx",
    }

    # Method 2: Using from_headers class method for success
    success_response = NHCXResponse.from_headers(
        headers=headers,
        entity_type=EntityTypeChoices.CLAIM,
        protocol_status=ProtocolStatusChoices.REQUEST_QUEUED,
        is_success=True,
    )

    print("Success Response from Headers:")
    print(success_response.model_dump_json(indent=2))

    # Method 2: Using from_headers class method for error
    error_response = NHCXResponse.from_headers(
        headers=headers,
        is_success=False,
        error_code="500",
        error_message="Internal server error",
    )

    print("Error Response from Headers:")
    print(error_response.model_dump_json(indent=2))

    return success_response, error_response


def example_django_viewset_usage():
    """Example of how to use in a Django ViewSet"""

    # This is how you would use it in your callback viewset
    def sample_callback_method(self, request):
        data = request.data
        payload = data.get("payload")

        if not payload:
            # Create error response
            error_response = NHCXResponse.create_error_response(
                api_call_id="",
                correlation_id="",
                error_code="400",
                error_message="Payload is required for decryption",
            )
            return Response(error_response.model_dump(), status=400)

        try:
            # Simulate decryption and processing
            headers = {
                "x-hcx-api_call_id": "api-call-123",
                "x-hcx-correlation_id": "corr-456",
            }

            # Process the request...
            # ... your business logic here ...

            # Create success response
            success_response = NHCXResponse.from_headers(
                headers=headers,
                entity_type=EntityTypeChoices.COVERAGE_ELIGIBILITY,
                protocol_status=ProtocolStatusChoices.REQUEST_QUEUED,
                is_success=True,
            )

            return Response(success_response.model_dump(), status=202)

        except Exception as e:
            # Create error response
            error_response = NHCXResponse.from_headers(
                headers=headers if "headers" in locals() else {},
                is_success=False,
                error_code="400",
                error_message=f"Decryption failed: {e!s}",
            )

            return Response(error_response.model_dump(), status=400)


if __name__ == "__main__":
    print("=== NHCX Response Examples ===\n")

    # Run examples
    example_success_response()
    print("\n" + "="*50 + "\n")

    example_error_response()
    print("\n" + "="*50 + "\n")

    example_from_headers()
