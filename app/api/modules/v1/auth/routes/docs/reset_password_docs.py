# REQUEST PASSWORD RESET ENDPOINT DOCS
request_reset_responses = {
    200: {
        "description": "Password reset code sent",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Reset code sent",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Reset code sent to email.",
                            "data": {"email": "user@example.com"},
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Account inactive",
        "content": {
            "application/json": {
                "examples": {
                    "inactive_user": {
                        "summary": "Account is inactive",
                        "value": {
                            "error": "ERROR",
                            "message": "Account is inactive. Please contact support.",
                            "status_code": 403,
                            "errors": {},
                        },
                    }
                }
            },
        },
    },
    404: {
        "description": "Email does not exist",
        "content": {
            "application/json": {
                "examples": {
                    "email_not_found": {
                        "summary": "User not found",
                        "value": {
                            "error": "ERROR",
                            "message": "Email does not exist.",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Validation error",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Invalid input",
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
                                ]
                            },
                        },
                    },
                    "missing_field": {
                        "summary": "Missing required field",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"email": ["Field required."]},
                        },
                    },
                }
            }
        },
    },
    500: {
        "description": "Internal server error",
        "content": {
            "application/json": {
                "examples": {
                    "server_error": {
                        "summary": "Unexpected error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Password reset request failed",
                            "status_code": 500,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

request_reset_custom_errors = ["403", "404", "422", "500"]
request_reset_custom_success = {
    "status_code": 200,
    "description": "Password reset code sent successfully to the registered email.",
}

# VERIFY RESET TOKEN ENDPOINT DOCS
verify_reset_responses = {
    200: {
        "description": "Reset token verified successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Token verified",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Token verified successfully.",
                            "data": {"reset_token": "<temporary_reset_token>"},
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Invalid or expired token",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_token": {
                        "summary": "Reset code invalid or expired",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid or expired token.",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Validation error",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Invalid input",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "email": [
                                    "value is not a valid email address: "
                                    "An email address must have an @-sign.",
                                    "value is not a valid email address: "
                                    "An email address cannot have a period immediately after "
                                    "the @-sign.",
                                    "value is not a valid email address: "
                                    "The part after the @-sign is not valid. "
                                    "It should have a period.",
                                ]
                            },
                        },
                    },
                    "missing_field": {
                        "summary": "Missing required field",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"email": ["Field required."], "code": ["Field required."]},
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
    500: {
        "description": "Internal server error",
        "content": {
            "application/json": {
                "examples": {
                    "server_error": {
                        "summary": "Unexpected error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Internal server error.",
                            "status_code": 500,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

verify_reset_custom_errors = ["400", "422", "500"]
verify_reset_custom_success = {
    "status_code": 200,
    "description": "Reset token verified successfully.",
}


# CONFIRM RESET PASSWORD ENDPOINT DOCS
confirm_reset_responses = {
    200: {
        "description": "Password reset successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Password updated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Password reset successful.",
                            "data": {},
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Invalid token or password reuse",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_token": {
                        "summary": "Token invalid or expired",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid or expired reset token.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "password_reuse": {
                        "summary": "Old password reuse attempt",
                        "value": {
                            "error": "ERROR",
                            "message": "Cannot reuse old password.",
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
                    "missing_fields": {
                        "summary": "Missing Required Fields",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "reset_token": ["Field required"],
                                "password": ["Field required"],
                                "confirm_password": ["Field required"],
                            },
                        },
                    },
                    "validation_error": {
                        "summary": "Request Validation Failed",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "password": [
                                    "String should have at least 8 characters",
                                    "Password must contain: one uppercase letter, "
                                    "one digit, one special character."
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
                }
            }
        },
    },
    500: {
        "description": "Internal server error",
        "content": {
            "application/json": {
                "examples": {
                    "server_error": {
                        "summary": "Unexpected error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Internal server error.",
                            "status_code": 500,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

confirm_reset_custom_errors = ["400", "422", "500"]
confirm_reset_custom_success = {
    "status_code": 200,
    "description": "Password reset completed successfully.",
}
