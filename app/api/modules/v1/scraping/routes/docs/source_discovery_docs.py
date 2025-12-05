"""OpenAPI documentation schemas for Source Discovery API endpoints.

This module defines response examples and HTTP status code documentation
for the AI-powered source suggestion and acceptance endpoints.
"""

suggest_sources_request_schema = {
    "type": "object",
    "properties": {
        "jurisdiction_name": {
            "type": "string",
            "nullable": True,
            "description": "Optional name of the jurisdiction (e.g., 'Nigeria').",
            "example": "Nigeria",
        },
        "jurisdiction_description": {
            "type": "string",
            "description": "Scope or description of the jurisdiction "
            "(e.g., 'Central Bank of Nigeria Regulations').",
            "example": "Central Bank of Nigeria Regulations",
        },
        "jurisdiction_prompt": {
            "type": "string",
            "nullable": True,
            "description": "Optional AI prompt guiding extraction, summarization, "
            "or classification tasks (e.g., 'Focus on crypto asset guidelines and "
            "licensing requirements').",
            "example": "Focus on crypto asset guidelines and licensing requirements",
        },
        "project_description": {
            "type": "string",
            "description": "Broader project goal (e.g., 'Monitor Crypto Asset Guidelines').",
            "example": "Monitor Crypto Asset Guidelines",
        },
        "search_query": {
            "type": "string",
            "nullable": True,
            "description": "Specific user input to narrow the search "
            "(e.g., '2024 crypto licensing requirements').",
            "example": "2024 crypto licensing requirements",
        },
    },
    "required": ["jurisdiction_description", "project_description"],
}

suggest_sources_responses = {
    200: {
        "description": "Sources Suggested Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Sources Suggested by AI",
                        "value": {
                            "status": "success",
                            "status_code": 200,
                            "message": "Sources suggested successfully",
                            "data": {
                                "sources": [
                                    {
                                        "title": "Central Bank of Nigeria - Crypto Guidelines",
                                        "url": "https://www.cbn.gov.ng/crypto-guidelines",
                                        "snippet": "Official CBN crypto asset regulations "
                                        "and guidelines",
                                        "confidence_reason": "Official government source",
                                        "is_official": True,
                                    },
                                    {
                                        "title": "CBN Licensing Requirements",
                                        "url": "https://www.cbn.gov.ng/licensing-requirements",
                                        "snippet": "Crypto asset licensing procedures "
                                        "and requirements",
                                        "confidence_reason": "Official source for licensing info",
                                        "is_official": True,
                                    },
                                ]
                            },
                        },
                    }
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "configuration_error": {
                        "summary": "Configuration Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "Configuration Error",
                            "error": "CONFIGURATION_ERROR",
                            "errors": {"details": "Missing API configuration or credentials"},
                        },
                    },
                    "agent_failed": {
                        "summary": "Discovery Agent Failed",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "Discovery Agent failed",
                            "error": "DISCOVERY_AGENT_FAILED",
                            "errors": {"details": "Error details from AI agent"},
                        },
                    },
                }
            }
        },
    },
}

suggest_sources_custom_errors = ["500"]
suggest_sources_custom_success = {
    "status_code": 200,
    "description": "AI-suggested sources retrieved successfully.",
}

accept_sources_responses = {
    201: {
        "description": "Suggested Sources Accepted Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Sources Created from Suggestions",
                        "value": {
                            "status": "success",
                            "status_code": 201,
                            "message": "Suggested sources accepted and created successfully",
                            "data": {
                                "sources": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                                        "name": "Federal Court Opinions",
                                        "url": "https://www.uscourts.gov/opinions/",
                                        "source_type": "web",
                                        "scrape_frequency": "DAILY",
                                        "is_active": True,
                                        "is_deleted": False,
                                        "has_auth": False,
                                        "created_at": "2025-11-29T10:30:00Z",
                                    },
                                    {
                                        "id": "223e4567-e89b-12d3-a456-426614174000",
                                        "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                                        "name": "Court Rules and Procedures",
                                        "url": "https://www.uscourts.gov/rules-policies/",
                                        "source_type": "web",
                                        "scrape_frequency": "DAILY",
                                        "is_active": True,
                                        "is_deleted": False,
                                        "has_auth": False,
                                        "created_at": "2025-11-29T10:30:00Z",
                                    },
                                ],
                                "count": 2,
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Duplicate URL or Invalid Data",
        "content": {
            "application/json": {
                "examples": {
                    "duplicate_url": {
                        "summary": "Duplicate Source URL",
                        "value": {
                            "status": "error",
                            "status_code": 400,
                            "message": "Source URLs already exist",
                            "error_code": "DUPLICATE_SOURCE",
                            "errors": {},
                        },
                    },
                    "invalid_data": {
                        "summary": "Invalid Suggestion Data",
                        "value": {
                            "status": "error",
                            "status_code": 400,
                            "message": "Invalid suggestion data",
                            "error_code": "INVALID_SUGGESTION_DATA",
                            "errors": {"details": "Invalid URL or missing required fields"},
                        },
                    },
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation Failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Request Validation Failed",
                        "value": {
                            "status": "error",
                            "status_code": 422,
                            "message": "Validation failed",
                            "error_code": "VALIDATION_ERROR",
                            "errors": {
                                "suggested_sources": ["ensure this value has at least 1 items"],
                                "jurisdiction_id": ["field required"],
                                "source_type": ["field required"],
                            },
                        },
                    }
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "Failed to accept suggested sources",
                            "error": "ACCEPT_SUGGESTIONS_FAILED",
                            "errors": {"details": "Database error or internal server error"},
                        },
                    }
                }
            }
        },
    },
}

accept_sources_custom_errors = ["400", "422", "500"]
accept_sources_custom_success = {
    "status_code": 201,
    "description": "Suggested sources converted to active sources successfully.",
}
