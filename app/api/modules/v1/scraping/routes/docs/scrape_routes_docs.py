"""
OpenAPI documentation for scrape job routes.

Provides response schemas and examples for:
- POST /scrapes/{source_id} - Trigger manual scrape
- GET /scrapes/{source_id}/{job_id} - Get scrape job status
"""

manual_scrape_trigger_responses = {
    202: {
        "description": "Scrape Job Queued Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Scrape Job Queued",
                        "value": {
                            "status": "success",
                            "status_code": 202,
                            "message": "Scrape job queued successfully",
                            "data": {
                                "job_id": "987e6543-e21c-34d5-b678-556655440000",
                                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "PENDING",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Source Inactive",
        "content": {
            "application/json": {
                "examples": {
                    "inactive_source": {
                        "summary": "Source Inactive",
                        "value": {
                            "status": "error",
                            "status_code": 400,
                            "message": "Cannot scrape inactive source. Please enable it first.",
                            "error_code": "SOURCE_INACTIVE",
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Source Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "source_not_found": {
                        "summary": "Source Not Found",
                        "value": {
                            "status": "error",
                            "status_code": 404,
                            "message": "Source not found",
                            "error_code": "SOURCE_NOT_FOUND",
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    409: {
        "description": "Conflict - Scrape Already In Progress",
        "content": {
            "application/json": {
                "examples": {
                    "scrape_in_progress": {
                        "summary": "Scrape Already Running",
                        "value": {
                            "status": "error",
                            "status_code": 409,
                            "message": "A scrape is already in progress for this source. "
                            "Please wait for it to complete.",
                            "error_code": "SCRAPE_IN_PROGRESS",
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

manual_scrape_trigger_custom_errors = ["400", "404", "409"]
manual_scrape_trigger_custom_success = {
    "status_code": 202,
    "description": "Scrape job queued successfully. Use job_id to poll for status.",
}


get_scrape_job_status_responses = {
    200: {
        "description": "Scrape Job Status Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "pending": {
                        "summary": "Job Pending",
                        "value": {
                            "status": "success",
                            "status_code": 200,
                            "message": "Scrape job status retrieved successfully",
                            "data": {
                                "id": "987e6543-e21c-34d5-b678-556655440000",
                                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "PENDING",
                                "result": None,
                                "error_message": None,
                                "data_revision_id": None,
                                "created_at": "2025-12-04T10:30:00Z",
                                "started_at": None,
                                "completed_at": None,
                            },
                        },
                    },
                    "in_progress": {
                        "summary": "Job In Progress",
                        "value": {
                            "status": "success",
                            "status_code": 200,
                            "message": "Scrape job status retrieved successfully",
                            "data": {
                                "id": "987e6543-e21c-34d5-b678-556655440000",
                                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "IN_PROGRESS",
                                "result": None,
                                "error_message": None,
                                "data_revision_id": None,
                                "created_at": "2025-12-04T10:30:00Z",
                                "started_at": "2025-12-04T10:30:05Z",
                                "completed_at": None,
                            },
                        },
                    },
                    "completed": {
                        "summary": "Job Completed",
                        "value": {
                            "status": "success",
                            "status_code": 200,
                            "message": "Scrape job status retrieved successfully",
                            "data": {
                                "id": "987e6543-e21c-34d5-b678-556655440000",
                                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "COMPLETED",
                                "result": {
                                    "status": "success",
                                    "change_detected": True,
                                    "change_summary": "New regulation added for data privacy",
                                },
                                "error_message": None,
                                "data_revision_id": "abc12345-d678-90ef-ghij-klmnopqrstuv",
                                "created_at": "2025-12-04T10:30:00Z",
                                "started_at": "2025-12-04T10:30:05Z",
                                "completed_at": "2025-12-04T10:31:15Z",
                            },
                        },
                    },
                    "failed": {
                        "summary": "Job Failed",
                        "value": {
                            "status": "success",
                            "status_code": 200,
                            "message": "Scrape job status retrieved successfully",
                            "data": {
                                "id": "987e6543-e21c-34d5-b678-556655440000",
                                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "FAILED",
                                "result": None,
                                "error_message": (
                                    "Scrape execution failed. Please try again or "
                                    "contact support if the issue persists."
                                ),
                                "data_revision_id": None,
                                "created_at": "2025-12-04T10:30:00Z",
                                "started_at": "2025-12-04T10:30:05Z",
                                "completed_at": "2025-12-04T10:30:45Z",
                            },
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Scrape Job Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "job_not_found": {
                        "summary": "Job Not Found",
                        "value": {
                            "status": "error",
                            "status_code": 404,
                            "message": "Scrape job not found",
                            "error_code": "JOB_NOT_FOUND",
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

get_scrape_job_status_custom_errors = ["404"]
get_scrape_job_status_custom_success = {
    "status_code": 200,
    "description": "Scrape job status retrieved successfully with current state and results.",
}
