get_user_profile_responses = {
    200: {
        "description": "User Profile Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "User Profile with OAuth Data",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "User profile retrieved successfully",
                            "data": {
                                "user": {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "email": "user@example.com",
                                    "name": "John Doe",
                                    "auth_provider": "google",
                                    "profile_picture_url": "https://lh3.googleusercontent.com/...",
                                    "provider_user_id": "107563041634719...",
                                    "provider_profile_data": {
                                        "name": "John Doe",
                                        "picture": "https://lh3.googleusercontent.com/...",
                                        "email_verified": True,
                                        "locale": "en",
                                    },
                                    "is_verified": True,
                                    "is_active": True,
                                    "created_at": "2024-01-15T10:30:00Z",
                                    "updated_at": "2024-01-15T10:30:00Z",
                                },
                                "organizations": [
                                    {
                                        "organization_id": "456e7890-e89b-12d3-a456-426614174001",
                                        "name": "Acme Corporation",
                                        "industry": "Technology",
                                        "role": "Admin",
                                        "is_active": True,
                                    }
                                ],
                                "statistics": {
                                    "total_organizations": 1,
                                    "active_memberships": 1,
                                    "admin_roles": 1,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication Required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
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
                        "summary": "Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to retrieve user profile",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_user_profile_custom_errors = ["401", "500"]
get_user_profile_custom_success = {
    "status_code": 200,
    "description": "User profile retrieved successfully with all organization memberships.",
}


get_user_organizations_responses = {
    200: {
        "description": "User Organizations Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "User Organizations List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Organizations retrieved successfully",
                            "data": [
                                {
                                    "organization_id": "123e4567-e89b-12d3-a456-426614174000",
                                    "name": "Acme Corporation",
                                    "industry": "Technology",
                                    "is_active": True,
                                    "user_role": "Admin",
                                    "created_at": "2024-01-15T10:30:00Z",
                                    "updated_at": "2024-01-15T10:30:00Z",
                                },
                                {
                                    "organization_id": "456e7890-e89b-12d3-a456-426614174001",
                                    "name": "Tech Innovations Ltd",
                                    "industry": "Software Development",
                                    "is_active": True,
                                    "user_role": "Member",
                                    "created_at": "2024-02-01T09:15:00Z",
                                    "updated_at": "2024-02-01T09:15:00Z",
                                },
                            ],
                        },
                    },
                    "success_empty": {
                        "summary": "User Has No Organizations",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Organizations retrieved successfully",
                            "data": [],
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication Required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Access Denied",
        "content": {
            "application/json": {
                "examples": {
                    "cannot_view_other_users": {
                        "summary": "Cannot View Other User's Organizations",
                        "value": {
                            "error": "FORBIDDEN",
                            "message": "You can only view your own organizations",
                            "status_code": 403,
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
                    "invalid_uuid": {
                        "summary": "Invalid User ID Format",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "user_id": ["Invalid UUID format"],
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
                            "message": "Failed to retrieve organizations",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_user_organizations_custom_errors = ["401", "403", "422", "500"]
get_user_organizations_custom_success = {
    "status_code": 200,
    "description": "User organizations retrieved successfully with role information.",
}
