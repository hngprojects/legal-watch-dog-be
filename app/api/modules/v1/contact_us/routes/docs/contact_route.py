contact_us_responses = {
    200: {
        "description": "Contact Form Submitted Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Message Sent Successfully",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Thank you for contacting us. We'll get back to you soon!",
                            "data": {
                                "email": "user@example.com",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Contact Form Error",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Validation Error",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid phone number format",
                            "status_code": 400,
                            "errors": {},
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
                    "validation_error_missing": {
                        "summary": "Request Validation Failed - Missing Fields",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "full_name": ["Field required"],
                                "email": ["Field required"],
                                "phone_number": ["Field required"],
                                "message": ["Field required"],
                            },
                        },
                    },
                    "validation_error_invalid_email": {
                        "summary": "Request Validation Failed - Invalid Email",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "email": [
                                    "value is not a valid email address: "
                                    "An email address must have an @-sign.",
                                    "value is not a valid email address: "
                                    "An email address cannot have a period immediately after the"
                                    " @-sign.",
                                    "value is not a valid email address: "
                                    "The part after the @-sign is not valid. "
                                    "It should have a period.",
                                ],
                            },
                        },
                    },
                    "validation_error_short_message": {
                        "summary": "Message Too Short",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"message": ["String should have at least 10 characters"]},
                        },
                    },
                    "validation_error_invalid_phone": {
                        "summary": "Invalid Phone Number",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "phone_number": [
                                    "Phone number must contain only digits and optional '+'"
                                ]
                            },
                        },
                    },
                    "validation_error_long_fields": {
                        "summary": "Field Length Exceeded",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "full_name": ["String should have at most 255 characters"],
                                "message": ["String should have at most 1000 characters"],
                            },
                        },
                    },
                }
            }
        },
    },
    429: {
        "description": "Too Many Requests - Rate Limit Exceeded",
        "content": {
            "application/json": {
                "examples": {
                    "rate_limit_email": {
                        "summary": "Rate Limit Exceeded - Email",
                        "value": {"detail": "Too many attempts. Please try again in 1 hour."},
                    },
                    "rate_limit_ip": {
                        "summary": "Rate Limit Exceeded - IP Address",
                        "value": {"detail": "Too many attempts from this IP. Try again in 1 hour."},
                    },
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
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to submit your message. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

contact_us_custom_errors = ["400", "422", "429", "500"]
contact_us_custom_success = {
    "status_code": 200,
    "description": "Contact form submitted successfully. Confirmation email sent.",
}
