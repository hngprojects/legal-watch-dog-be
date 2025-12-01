# COMPANY SIGNUP DOCS
company_signup_responses = {
    201: {
        "description": "Registration Initiated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Registration Initiated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "Registration initiated. Verify the OTP sent to your email.",
                            "data": {
                                "email": "company@example.com",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Registration Error",
        "content": {
            "application/json": {
                "examples": {
                    "email_exists": {
                        "summary": "Email Already Registered",
                        "value": {
                            "error": "ERROR",
                            "message": "An organization with this email already exists.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "pending_registration": {
                        "summary": "Email Already Has Pending Registration",
                        "value": {
                            "error": "ERROR",
                            "message": "A registration with this email is already pending"
                            " OTP verification.",
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
                    "validation_error": {
                        "summary": "Request Validation Failed",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "email": ["Only company email addresses are allowed."],
                                "password": [
                                    "Password must contain: one uppercase letter, one digit,"
                                    " one special character."
                                ],
                            },
                        },
                    },
                    "password_mismatch": {
                        "summary": "Password Confirmation Mismatch",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"confirm_password": ["Passwords do not match"]},
                        },
                    },
                    "missing_fields": {
                        "summary": "Missing Required Fields",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "email": ["Field required"],
                                "password": ["Field required"],
                                "name": ["Field required"],
                            },
                        },
                    },
                    "invalid_code_format": {
                        "summary": "Invalid Email Format",
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
                            "message": "Registration failed. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

company_signup_custom_errors = ["400", "422", "500"]
company_signup_custom_success = {
    "status_code": 201,
    "description": "Registration initiated successfully. OTP sent to email.",
}


# VERIFY OTP DOCS
verify_otp_responses = {
    201: {
        "description": "OTP Verified Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Registration Completed",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Registration completed successfully",
                            "status_code": 201,
                            "data": {
                                "email": "company@example.com",
                                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - OTP Verification Error",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_otp": {
                        "summary": "Invalid OTP Code",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid or expired OTP code",
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
                            "errors": {"email": ["Field required"], "code": ["Field required"]},
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
                    "invalid_code_format": {
                        "summary": "Invalid OTP Format",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "validation failed",
                            "status_code": 422,
                            "errors": {"code": ["String should have at least 6 characters"]},
                        },
                    },
                }
            }
        },
    },
    429: {
        "description": "Rate limit exceeded",
        "content": {
            "application/json": {
                "examples": {
                    "email_rate_limit": {
                        "summary": "Rate Limit Exceeded for Email",
                        "value": {
                            "error": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many OTP verification attempts for this email. "
                            "Please retry in 1 hour.",
                            "status_code": 429,
                            "errors": {},
                        },
                    },
                    "ip_rate_limit": {
                        "summary": "Rate Limit Exceeded for IP",
                        "value": {
                            "error": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many OTP verification attempts from this IP. "
                            "Please retry in 1 hour.",
                            "status_code": 429,
                            "errors": {},
                        },
                    },
                }
            },
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
                            "message": "OTP verification failed. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

verify_otp_custom_errors = ["400", "422", "429", "500"]
verify_otp_custom_success = {
    "status_code": 201,
    "description": "OTP verified successfully. Registration completed.",
}


# REQUEST NEW OTP DOCS
request_new_otp_responses = {
    200: {
        "description": "OTP Resent Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "New OTP Sent",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "A new OTP has been sent to your email, "
                            "expiring in 5 minutes.",
                            "data": {
                                "email": "company@example.com",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Resend Error",
        "content": {
            "application/json": {
                "examples": {
                    "no_pending_registration": {
                        "summary": "No Pending Registration",
                        "value": {
                            "error": "ERROR",
                            "message": "No pending registration found for this email."
                            " Please sign up again.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "registration_already_verified": {
                        "summary": "Registration Already Verified",
                        "value": {
                            "error": "ERROR",
                            "message": "Registration already completed for this email."
                            " Please log in instead.",
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
                    "validation_error": {
                        "summary": "Request Validation Failed",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"email": ["Field required"]},
                        },
                    },
                    "invalid_email": {
                        "summary": "Invalid Email Format",
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
                }
            }
        },
    },
    429: {
        "description": "Rate limit exceeded",
        "content": {
            "application/json": {
                "examples": {
                    "email_rate_limit": {
                        "summary": "Rate Limit Exceeded for Email",
                        "value": {
                            "error": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many OTP requests for this email. "
                            "Please retry in 1 hour.",
                            "status_code": 429,
                            "errors": {},
                        },
                    },
                    "ip_rate_limit": {
                        "summary": "Rate Limit Exceeded for IP",
                        "value": {
                            "error": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many OTP requests from this IP. "
                            "Please retry in 1 hour.",
                            "status_code": 429,
                            "errors": {},
                        },
                    },
                }
            },
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
                            "message": "Failed to resend OTP. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

request_new_otp_custom_errors = ["400", "422", "429", "500"]
request_new_otp_custom_success = {
    "status_code": 200,
    "description": "New OTP sent successfully to the registered email.",
}
