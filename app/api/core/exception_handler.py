from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom exception handler for Pydantic's ValidationError.
    
    Returns a simplified and user-friendly error message.
    """
    errors = []
    for error in exc.errors():
        field = error["loc"][-1]
        message = error["msg"]
        errors.append({"field": field, "message": message})
        
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "failed",
            "message": "Validation failed. Please check the provided data.",
            "errors": errors,
        },
    )