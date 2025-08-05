from rest_framework.exceptions import APIException


class NHCXAPIException(APIException):
    status_code = 400
    default_code = "NHCX_ERROR"
    default_detail = "An error occurred while trying to communicate with NHCX"


class NHCXInternalException(APIException):
    status_code = 400
    default_code = "NHCX_INTERNAL_ERROR"
    default_detail = "An internal error occurred while trying to communicate with NHCX"
