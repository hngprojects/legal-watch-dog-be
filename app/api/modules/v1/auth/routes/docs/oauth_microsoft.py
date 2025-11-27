microsoft_login_responses = {
    200: {
        "description": "Authorization URL Generated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Authorization URL Created",
                        "value": {
                            "authorization_url": "https://login.microsoftonline.com/tenant-id/oauth2/v2.0/authorize?client_id=...&state=...",
                            "state": "randomStateString123",
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
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to initiate Microsoft login",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

microsoft_login_custom_errors = ["500"]
microsoft_login_custom_success = {
    "status_code": 200,
    "description": "Authorization URL generated successfully. Redirect user to this URL.",
}


microsoft_callback_responses = {
    302: {
        "description": "Authentication Successful - Redirecting to Frontend",
        "content": {
            "application/json": {
                "examples": {
                    "new_user_redirect": {
                        "summary": "New User Registered via Microsoft",
                        "value": {
                            "message": "Redirecting to new user onboarding page",
                            "redirect_url": "https://app.example.com/onboarding",
                            "cookies_set": ["lwd_access_token", "lwd_refresh_token"],
                        },
                    },
                    "existing_user_redirect": {
                        "summary": "Existing User Logged In",
                        "value": {
                            "message": "Redirecting to dashboard",
                            "redirect_url": "https://app.example.com/dashboard",
                            "cookies_set": ["lwd_access_token", "lwd_refresh_token"],
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Bad Request - OAuth Error from Microsoft",
        "content": {
            "application/json": {
                "examples": {
                    "oauth_error": {
                        "summary": "Microsoft OAuth Error",
                        "value": {
                            "error": "access_denied",
                            "error_description": "User denied the authorization request",
                            "redirect_url": "https://app.example.com/signup?error=access_denied",
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Invalid State or Token",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_state": {
                        "summary": "Invalid or Expired State Parameter",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Invalid or expired state parameter",
                            "redirect_url": "https://app.example.com/signup?error=validation_failed",
                        },
                    },
                    "token_exchange_failed": {
                        "summary": "Failed to Exchange Authorization Code",
                        "value": {
                            "error": "AUTHENTICATION_ERROR",
                            "message": "Failed to exchange code for access token",
                            "redirect_url": "https://app.example.com/signup?error=validation_failed",
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
                        "summary": "Server Error During OAuth Flow",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to complete Microsoft OAuth flow",
                            "redirect_url": "https://app.example.com/signup?error=authentication_failed",
                        },
                    },
                    "graph_api_error": {
                        "summary": "Failed to Fetch User Info from Microsoft",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to communicate with Microsoft Graph API",
                            "redirect_url": "https://app.example.com/signup?error=authentication_failed",
                        },
                    },
                }
            }
        },
    },
}

microsoft_callback_custom_errors = ["400", "401", "500"]
microsoft_callback_custom_success = {
    "status_code": 302,
    "description": "Logged in successfully. Tokens set as httpOnly cookies and user redirected.",
}
