from typing import Dict, List, Optional

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def success_response(status_code: int, message: str, data: Optional[dict] = None):
    """
    Create a standardized JSON response for successful requests.

    Args:
        status_code (int): HTTP status code to return (e.g. 200, 201).
        message (str): Human-readable description of the result.
        data (Optional[dict]): Optional payload data. Defaults to an empty dict.

    Returns:
        JSONResponse: Contains:
<<<<<<< HEAD
<<<<<<< HEAD
            - status: "success"
=======
            - status: "SUCCESS"
>>>>>>> fix/billing-model-cleanup
=======
            - status: "SUCCESS"
>>>>>>> 92e9e9285276ed3d5b58eebfb6e8e42aca67935e
            - status_code: same as HTTP status code
            - message: same message passed
            - data: payload object (never null)
    """

    response_data = {
        "status": "SUCCESS",
        "status_code": status_code,
        "message": message,
<<<<<<< HEAD
<<<<<<< HEAD
        "data": data or {}
=======
        "data": data or {},
>>>>>>> fix/billing-model-cleanup
=======
        "data": data or {},
>>>>>>> 92e9e9285276ed3d5b58eebfb6e8e42aca67935e
    }

    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(response_data)
    )


def auth_response(status_code: int, message: str, access_token: str, data: Optional[dict] = None):
    """
    Create a standardized JSON response for authentication-related successes.

    Args:
        status_code (int): HTTP status code to return.
        message (str): Human-readable result message.
        access_token (str): The JWT/bearer token string.
        data (Optional[dict]): Additional payload merged into the data block.

    Returns:
        JSONResponse: Same structure as success_response but with:
            - access_token added inside the data object
    """

    response_data = {
        "status": "SUCCESS",
        "status_code": status_code,
        "message": message,
<<<<<<< HEAD
<<<<<<< HEAD
        "data": {
            "access_token": access_token,
            **(data or {})
        }
=======
        "data": {"access_token": access_token, **(data or {})},
>>>>>>> fix/billing-model-cleanup
    }

    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(response_data)
    )


<<<<<<< HEAD
def fail_response(status_code: int, message: str, data: Optional[dict] = None):
=======
def error_response(
    *,
    status_code: int,
    message: str,
    error: str = "ERROR",
    errors: Optional[Dict[str, List[str]]] = None,
) -> JSONResponse:
>>>>>>> fix/billing-model-cleanup
    """
    Create a standardized JSON response for failed requests.

    Args:
<<<<<<< HEAD
        status_code (int): HTTP status code (e.g. 400, 404, 500).
        message (str): Human-readable description of the error.
        data (Optional[dict]): Optional details about the failure.

    Returns:
        JSONResponse: Contains:
            - status: "failure"
            - status_code: error HTTP code
            - message: description of failure
            - data: extra error details (always a dict)
=======
        status_code (int): HTTP status code representing the error (e.g. 400, 401, 404, 422).
        message (str): High-level human-readable error description.
        error (str): Machine-readable error code (e.g. "VALIDATION_ERROR", "BAD_REQUEST").
            Defaults to "ERROR".
        errors (Optional[Dict[str, List[str]]]): Optional field-level validation errors
            in the form:
                {
                    "field_name": ["error message 1", "error message 2"],
                    ...
                }

    Returns:
        JSONResponse: Standard error structure:
            {
                "error": "<ERROR_CODE>",
                "message": "<message>",
                "status_code": <status_code>,
                "errors": {
                    "field": ["error1", "error2"],
                    ...
                }
            }
>>>>>>> fix/billing-model-cleanup
    """

    response_data = {
        "error": error,
        "message": message,
<<<<<<< HEAD
        "data": data or {}
    }

    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(response_data)
    )
=======
        "status_code": status_code,
        "errors": errors or {},
    }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(response_data))
>>>>>>> fix/billing-model-cleanup
=======
        "data": {"access_token": access_token, **(data or {})},
    }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(response_data))


def error_response(
    *,
    status_code: int,
    message: str,
    error: str = "ERROR",
    errors: Optional[Dict[str, List[str]]] = None,
) -> JSONResponse:
    """
    Create a standardized JSON response for failed requests.

    Args:
        status_code (int): HTTP status code representing the error (e.g. 400, 401, 404, 422).
        message (str): High-level human-readable error description.
        error (str): Machine-readable error code (e.g. "VALIDATION_ERROR", "BAD_REQUEST").
            Defaults to "ERROR".
        errors (Optional[Dict[str, List[str]]]): Optional field-level validation errors
            in the form:
                {
                    "field_name": ["error message 1", "error message 2"],
                    ...
                }

    Returns:
        JSONResponse: Standard error structure:
            {
                "error": "<ERROR_CODE>",
                "message": "<message>",
                "status_code": <status_code>,
                "errors": {
                    "field": ["error1", "error2"],
                    ...
                }
            }
    """

    response_data = {
        "error": error,
        "message": message,
        "status_code": status_code,
        "errors": errors or {},
    }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(response_data))
>>>>>>> 92e9e9285276ed3d5b58eebfb6e8e42aca67935e
