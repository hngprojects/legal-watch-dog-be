from typing import Optional, Dict, Any
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


def success_response(status_code: int, message: str, data: Optional[dict] = None):
    """Create a standardized JSON response for successful requests.

    Args:
        status_code (int): HTTP status code to return (e.g. 200).
        message (str): Human-readable description of the result.
        data (Optional[dict]): Optional additional payload data. If omitted,
        an empty dictionary is used.

    Returns:
        JSONResponse: A FastAPI JSONResponse instance with status/status_code/
        message/data keys. The function applies jsonable_encoder to ensure
        all values are JSON serializable before being sent to the client.
    """

    response_data = {
        "status": "success",
        "status_code": status_code,
        "message": message,
        "data": data or {}  # Ensure data is always a dictionary
    }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(response_data))


def auth_response(status_code: int, message: str, access_token: str, data: Optional[dict] = None):
    """Create a JSON response for authentication-related successes.

    Args:
        status_code (int): HTTP status code to return (e.g. 201).
        message (str): Human-readable description of the result.
        access_token (str): The JWT or bearer token string to return.
        data (Optional[dict]): Optional additional payload data to merge
            into the data object alongside the token.

    Returns:
        JSONResponse: A FastAPI JSONResponse where the data object contains
            the access_token plus any additional merged keys from the input data.
    """

    response_data = {
        "status": "success",
        "status_code": status_code,
        "message": message,
        "data": {
            "access_token": access_token,
            **(data or {})  # Merge additional data if provided
        }
    }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(response_data))


def fail_response(status_code: int, message: str, data: Optional[dict] = None):
    """Create a standardized JSON response for failed requests.

    Args:
        status_code (int): HTTP status code to return (e.g. 400, 404, 500).
        message (str): Human-readable description of the error.
        data (Optional[dict]): Optional dictionary with extra error details.

    Returns:
        JSONResponse: A FastAPI JSONResponse with status/status_code/message/
            data keys representing the failure response.
    """

    response_data = {
        "status": "failure",
        "status_code": status_code,
        "message": message,
        "data": data or {}  # Ensure data is always a dictionary
    }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(response_data))