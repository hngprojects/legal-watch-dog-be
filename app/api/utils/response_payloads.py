from typing import Optional

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
            - status: "success"
            - status_code: same as HTTP status code
            - message: same message passed
            - data: payload object (never null)
    """

    response_data = {
        "status": "success",
        "status_code": status_code,
        "message": message,
        "data": data or {},
    }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(response_data))


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
        "status": "success",
        "status_code": status_code,
        "message": message,
        "data": {"access_token": access_token, **(data or {})},
    }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(response_data))


def fail_response(status_code: int, message: str, error: Optional[dict] = None):
    """
    Create a standardized JSON response for failed requests.

    Args:
        status_code (int): HTTP status code (e.g. 400, 404, 500).
        message (str): Human-readable description of the error.
        error (Optional[dict]): Optional details about the failure.

    Returns:
        JSONResponse: Contains:
            - status: "failure"
            - status_code: error HTTP code
            - message: description of failure
            - error: extra error details (always a dict)
    """

    response_data = {
        "status": "failure",
        "status_code": status_code,
        "message": message,
        "error": error or {},
    }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(response_data))
