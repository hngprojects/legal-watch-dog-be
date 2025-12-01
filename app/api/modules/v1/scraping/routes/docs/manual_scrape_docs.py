"""Documentation for manual scraping endpoints."""

trigger_manual_scrape_responses = {
    202: {
        "description": "Scrape Task Queued Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Task Queued",
                        "value": {
                            "status": "success",
                            "status_code": 202,
                            "message": "Scrape job queued successfully",
                            "data": {
                                "task_id": "abc123def456-789xyz-0123",
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
        "description": "Bad Request - Source Inactive or Deleted",
        "content": {
            "application/json": {
                "examples": {
                    "inactive_source": {
                        "summary": "Source Inactive or Deleted",
                        "value": {
                            "status": "failure",
                            "status_code": 400,
                            "message": "Cannot scrape inactive or deleted source",
                            "error_code": "SOURCE_INACTIVE_OR_DELETED",
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
                            "status": "failure",
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
    500: {
        "description": "Internal Server Error - Task Queue Failed",
        "content": {
            "application/json": {
                "examples": {
                    "queue_error": {
                        "summary": "Task Queue Error",
                        "value": {
                            "status": "failure",
                            "status_code": 500,
                            "message": "Failed to queue scrape task",
                            "error_code": "TASK_QUEUE_ERROR",
                            "errors": {"details": "Redis connection error or Celery unavailable"},
                        },
                    },
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "status": "failure",
                            "status_code": 500,
                            "message": "Failed to queue scrape task",
                            "error_code": "TASK_QUEUE_ERROR",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

trigger_manual_scrape_custom_errors = ["400", "404", "500"]
trigger_manual_scrape_custom_success = {
    "status_code": 202,
    "description": "Scrape task queued successfully for asynchronous processing.",
}
