# GET SOURCE REVISIONS DOCS
get_source_revisions_responses = {
    200: {
        "description": "Revisions Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Successful Retrieval",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Revisions retrieved successfully",
                            "data": {
                                "revisions": [
                                    {
                                        "id": "987e6543-e21c-34d5-b678-556655440000",
                                        "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "minio_object_key": "scrapes/2025/11/25/source-13e457.html",
                                        "content_hash": "abc123def456",
                                        "extracted_data": {
                                            "title": "New Regulation 2025-001",
                                            "content": "Full text of the regulation...",
                                            "effective_date": "2025-12-01",
                                        },
                                        "ai_summary": "New data privacy law effective March 2026",
                                        "ai_markdown_summary": "##New Regulation\n\nKey changes...",
                                        "ai_confidence_score": 0.95,
                                        "scraped_at": "2025-11-25T10:30:00Z",
                                        "was_change_detected": True,
                                    },
                                    {
                                        "id": "876e5432-d10b-23c4-a567-445544330000",
                                        "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "minio_object_key": "scrapes/2025/11/20/source-13e47.html",
                                        "content_hash": "def456ghi789",
                                        "extracted_data": {
                                            "title": "Previous Regulation Update",
                                            "content": "Updated text...",
                                            "effective_date": "2025-11-01",
                                        },
                                        "ai_summary": "Minor update to existing regulation",
                                        "ai_markdown_summary": "## Update\\n\\nMinor changes...",
                                        "ai_confidence_score": 0.88,
                                        "scraped_at": "2025-11-20T08:15:00Z",
                                        "was_change_detected": False,
                                    },
                                ],
                                "pagination": {
                                    "total": 150,
                                    "page": 1,
                                    "limit": 50,
                                    "total_pages": 3,
                                },
                            },
                        },
                    },
                    "empty_results": {
                        "summary": "No Revisions Found",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Revisions retrieved successfully",
                            "data": {
                                "revisions": [],
                                "pagination": {
                                    "total": 0,
                                    "page": 1,
                                    "limit": 50,
                                    "total_pages": 0,
                                },
                            },
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Source Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "source_not_found": {
                        "summary": "Source Does Not Exist",
                        "value": {
                            "error": "ERROR",
                            "status_code": 404,
                            "message": "Source not found",
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Validation Error",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_skip": {
                        "summary": "Invalid Skip Parameter",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "status_code": 422,
                            "message": "Validation failed",
                            "errors": {"skip": ["Input should be greater than or equal to 0"]},
                        },
                    },
                    "invalid_limit": {
                        "summary": "Invalid Limit Parameter",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "status_code": 422,
                            "message": "Validation failed",
                            "errors": {"limit": ["Input should be less than or equal to 200"]},
                        },
                    },
                }
            }
        },
    },
}

get_source_revisions_custom_errors = ["404", "422"]
get_source_revisions_custom_success = {
    "status_code": 200,
    "description": "Revisions retrieved successfully with pagination metadata",
}
