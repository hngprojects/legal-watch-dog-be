# LOGIN ENDPOINT DOCS
login_responses = {
    200: {
        "description": "Login Successful",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "User Authenticated",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Login successful",
                            "status_code": 200,
                            "data": {
                                "access_token": "<access_token>",
                                "refresh_token": "<refresh_token>",
                                "token_type": "bearer",
                                "expires_in": 3600,
                            },
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Account Issues",
        "content": {
            "application/json": {
                "examples": {
                    "unverified_account": {
                        "summary": "Wrong Credentials",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid email or password 4 atempts remaining",
                            "status_code": 401,
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
                            "errors": {"email": ["Field required"], "code": ["Field required"]},
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
                        "summary": "Unexpected Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Internal server error",
                            "status_code": 500,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

login_custom_errors = ["401", "422", "500"]
login_custom_success = {"status_code": 200, "description": "Login successful and tokens issued."}

# REFRESH TOKEN ENDPOINT DOCS
refresh_token_responses = {
    200: {
        "description": "Refresh Token Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "New Tokens Issued",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Token refreshed successfully",
                            "data": {
                                "access_token": "<new_access_token>",
                                "refresh_token": "<new_refresh_token>",
                                "token_type": "bearer",
                                "expires_in": 3600,
                            },
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Invalid Refresh Token",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_token": {
                        "summary": "Refresh Token Invalid or Expired",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid or expired refresh token",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
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
                        "summary": "Request Validation Failed - Missing Fields",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "refresh_token": ["Field required"],
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
                        "summary": "Unexpected Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Internal server error",
                            "status_code": 500,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

refresh_custom_errors = ["401", "422", "500"]
refresh_custom_success = {
    "status_code": 200,
    "description": "Refresh token validated and new tokens issued.",
}

# LOGOUT ENDPOINT DOCS
logout_responses = {
    200: {
        "description": "Logout Successful",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Tokens Blacklisted",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Logged out successfully",
                            "data": {},
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Invalid User",
        "content": {
            "application/json": {
                "examples": {
                    "unauthorized": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error": "HTTP_ERROR",
                            "message": "Invalid token or expired token",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                    "authentication_failed": {
                        "summary": "Authentication Failed",
                        "value": {
                            "error": "HTTP_ERROR",
                            "message": "Authentication failed",
                            "status_code": 401,
                            "errors": {},
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
                        "summary": "Unexpected Error",
                        "value": {
                            "status_code": 500,
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Internal server error",
                        },
                    }
                }
            }
        },
    },
}

logout_custom_errors = ["401", "500"]
logout_custom_success = {
    "status_code": 200,
    "description": "User logged out and tokens blacklisted successfully.",
}
