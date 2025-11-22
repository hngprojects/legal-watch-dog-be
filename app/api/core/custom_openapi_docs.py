from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api.modules.v1.schemas.error_schema import ErrorResponseModel


def custom_openapi(app: FastAPI):
    """
    Generate a custom OpenAPI schema that injects standardized error responses
    for all endpoints.

    This function ensures that every route in the API automatically includes
    common HTTP error responses (400, 401, 403, 404, 422, 500) with a
    standardized JSON schema defined in `ErrorResponseModel`. This helps
    maintain consistent API documentation and improves frontend error handling.

    Args:
        app (FastAPI): The FastAPI application instance for which the OpenAPI
                       schema will be generated.

    Returns:
        dict: The custom OpenAPI schema for the application, with injected
              standardized error responses.
    """
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    default_error = {
        "description": "Standardized Error Response",
        "content": {"application/json": {"schema": ErrorResponseModel.schema()}},
    }

    for path, path_item in list(schema["paths"].items()):
        new_path = app.root_path + path if app.root_path else path
        schema["paths"][new_path] = path_item
        if new_path != path:
            del schema["paths"][path]

        for method in path_item.values():
            method.setdefault("responses", {})
            for code in ["400", "401", "403", "404", "405", "409", "422", "500"]:
                method["responses"][code] = default_error

    app.openapi_schema = schema
    return app.openapi_schema
