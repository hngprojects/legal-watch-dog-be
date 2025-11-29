# CREATE CHECKOUT SESSION DOCS
create_checkout_responses = {
    200: {
        "description": "Checkout session created successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Checkout session created",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Checkout session created",
                            "data": {
                                "checkout_url": "https://checkout.stripe.com/c/test_123",
                                "session_id": "cs_test_1234567890",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid plan or request",
        "content": {
            "application/json": {
                "examples": {
                    "unsupported_plan": {
                        "summary": "Unsupported billing plan",
                        "value": {
                            "error": "ERROR",
                            "message": "Unsupported billing plan",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "invalid_request": {
                        "summary": "Invalid request payload",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid request",
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
                                "plan": ["Field required"],
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
                    "stripe_customer_error": {
                        "summary": "Failed to create Stripe customer",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to create Stripe customer",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "checkout_error": {
                        "summary": "Checkout session creation failed",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to create checkout session",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "config_error": {
                        "summary": "Billing configuration invalid",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": (
                                "Billing is not correctly configured. Please contact support."
                            ),
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

create_checkout_custom_errors = ["400", "422", "500"]
create_checkout_custom_success = {
    "status_code": 200,
    "description": "Checkout session created successfully.",
}

# CREATE CHECKOUT SESSION DOCS
create_checkout_responses = {
    200: {
        "description": "Checkout session created successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Checkout session created",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Checkout session created",
                            "data": {
                                "checkout_url": "https://checkout.stripe.com/c/test_123",
                                "session_id": "cs_test_1234567890",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid plan or request",
        "content": {
            "application/json": {
                "examples": {
                    "unsupported_plan": {
                        "summary": "Unsupported billing plan",
                        "value": {
                            "error": "ERROR",
                            "message": "Unsupported billing plan",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "invalid_request": {
                        "summary": "Invalid request payload",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid request",
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
                                "plan": ["Field required"],
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
                    "stripe_customer_error": {
                        "summary": "Failed to create Stripe customer",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to create Stripe customer",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "checkout_error": {
                        "summary": "Checkout session creation failed",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to create checkout session",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "config_error": {
                        "summary": "Billing configuration invalid",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": (
                                "Billing is not correctly configured. Please contact support."
                            ),
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

create_checkout_custom_errors = ["400", "422", "500"]
create_checkout_custom_success = {
    "status_code": 200,
    "description": "Checkout session created successfully.",
}


# GET SUBSCRIPTION STATUS DOCS
subscription_status_responses = {
    200: {
        "description": "Subscription status retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Subscription active",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Subscription status retrieved",
                            "data": {
                                "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                "stripe_customer_id": "cus_123456789",
                                "stripe_subscription_id": "sub_123456789",
                                "status": "active",
                                "cancel_at_period_end": False,
                                "trial_starts_at": "2025-01-01T00:00:00Z",
                                "trial_ends_at": "2025-01-14T00:00:00Z",
                                "current_period_start": "2025-01-01T00:00:00Z",
                                "current_period_end": "2025-02-01T00:00:00Z",
                                "next_billing_at": "2025-02-01T00:00:00Z",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No billing account",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found",
                            "status_code": 404,
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
                        "summary": "Invalid organisation id",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
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
                        "summary": "Failed to get subscription status",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to get subscription status",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

subscription_status_custom_errors = ["404", "422", "500"]
subscription_status_custom_success = {
    "status_code": 200,
    "description": "Subscription status retrieved successfully.",
}


# CHANGE SUBSCRIPTION PLAN DOCS
change_subscription_plan_responses = {
    200: {
        "description": "Subscription plan changed successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success_monthly": {
                        "summary": "Changed to monthly plan",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Subscription plan changed to monthly",
                            "data": {
                                "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                "stripe_customer_id": "cus_123456789",
                                "stripe_subscription_id": "sub_123456789",
                                "status": "active",
                                "cancel_at_period_end": False,
                                "trial_starts_at": "2025-01-01T00:00:00Z",
                                "trial_ends_at": "2025-01-14T00:00:00Z",
                                "current_period_start": "2025-01-01T00:00:00Z",
                                "current_period_end": "2025-02-01T00:00:00Z",
                                "next_billing_at": "2025-02-01T00:00:00Z",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid request or no active subscription",
        "content": {
            "application/json": {
                "examples": {
                    "no_active_subscription": {
                        "summary": "No active subscription",
                        "value": {
                            "error": "ERROR",
                            "message": "No active subscription to change",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "unsupported_plan": {
                        "summary": "Unsupported billing plan",
                        "value": {
                            "error": "ERROR",
                            "message": "Unsupported billing plan",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "validation_error": {
                        "summary": "Invalid request payload",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid request",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No billing account",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found",
                            "status_code": 404,
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
                        "summary": "Invalid plan code",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "plan": ["value is not a valid enumeration member"],
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
                    "config_error": {
                        "summary": "Billing configuration invalid",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": (
                                "Billing is not correctly configured. Please contact support."
                            ),
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "server_error": {
                        "summary": "Failed to change subscription plan",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to change subscription plan",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

change_subscription_plan_custom_errors = ["400", "404", "422", "500"]
change_subscription_plan_custom_success = {
    "status_code": 200,
    "description": "Subscription plan changed successfully.",
}


# CANCEL SUBSCRIPTION DOCS
cancel_subscription_responses = {
    200: {
        "description": "Subscription cancelled or scheduled for cancellation successfully",
        "content": {
            "application/json": {
                "examples": {
                    "cancel_immediately": {
                        "summary": "Cancelled immediately",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Subscription cancelled immediately",
                            "data": {
                                "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                "stripe_customer_id": "cus_123456789",
                                "stripe_subscription_id": "sub_123456789",
                                "status": "canceled",
                                "cancel_at_period_end": False,
                                "trial_starts_at": "2025-01-01T00:00:00Z",
                                "trial_ends_at": "2025-01-14T00:00:00Z",
                                "current_period_start": "2025-01-01T00:00:00Z",
                                "current_period_end": "2025-02-01T00:00:00Z",
                                "next_billing_at": None,
                            },
                        },
                    },
                    "cancel_at_period_end": {
                        "summary": "Set to cancel at period end",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Subscription set to cancel at period end",
                            "data": {
                                "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                "stripe_customer_id": "cus_123456789",
                                "stripe_subscription_id": "sub_123456789",
                                "status": "active",
                                "cancel_at_period_end": True,
                                "trial_starts_at": "2025-01-01T00:00:00Z",
                                "trial_ends_at": "2025-01-14T00:00:00Z",
                                "current_period_start": "2025-01-01T00:00:00Z",
                                "current_period_end": "2025-02-01T00:00:00Z",
                                "next_billing_at": "2025-02-01T00:00:00Z",
                            },
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Bad Request - No active subscription or invalid request",
        "content": {
            "application/json": {
                "examples": {
                    "no_active_subscription": {
                        "summary": "No active subscription",
                        "value": {
                            "error": "ERROR",
                            "message": "No active subscription to cancel",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "validation_error": {
                        "summary": "Invalid request payload",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid request",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No billing account",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found",
                            "status_code": 404,
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
                        "summary": "Invalid cancel_at_period_end flag or organisation id",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
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
                        "summary": "Failed to cancel subscription",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to cancel subscription",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

cancel_subscription_custom_errors = ["400", "404", "422", "500"]
cancel_subscription_custom_success = {
    "status_code": 200,
    "description": "Subscription cancelled or scheduled for cancellation successfully.",
}


# CREATE BILLING ACCOUNT DOCS
create_billing_account_responses = {
    201: {
        "description": "Billing account created successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Billing account created",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "Billing account created",
                            "data": {
                                "id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                "organization_id": "0c7c9f2b-7a67-4b37-9f42-5ff000000001",
                                "currency": "USD",
                                "stripe_customer_id": "cus_123456789",
                                "stripe_subscription_id": None,
                                "status": "inactive",
                                "cancel_at_period_end": False,
                                "trial_starts_at": None,
                                "trial_ends_at": None,
                                "current_period_start": None,
                                "current_period_end": None,
                                "next_billing_at": None,
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Validation or business rule error",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Validation / business rule failure",
                        "value": {
                            "error": "ERROR",
                            "message": "Currency XYZ is not supported",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_payload": {
                        "summary": "Invalid request payload",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
                                "currency": ["value is not a valid string"],
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
                        "summary": "Failed to create billing account",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to create billing account",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

create_billing_account_custom_errors = ["400", "422", "500"]
create_billing_account_custom_success = {
    "status_code": 201,
    "description": "Billing account created successfully.",
}


# GET BILLING ACCOUNT DOCS
get_billing_account_responses = {
    200: {
        "description": "Billing account retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Billing account found",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Billing account retrieved",
                            "data": {
                                "id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                "organization_id": "0c7c9f2b-7a67-4b37-9f42-5ff000000001",
                                "currency": "USD",
                                "stripe_customer_id": "cus_123456789",
                                "stripe_subscription_id": "sub_123456789",
                                "status": "active",
                                "cancel_at_period_end": False,
                                "trial_starts_at": "2025-01-01T00:00:00Z",
                                "trial_ends_at": "2025-01-14T00:00:00Z",
                                "current_period_start": "2025-01-01T00:00:00Z",
                                "current_period_end": "2025-02-01T00:00:00Z",
                                "next_billing_at": "2025-02-01T00:00:00Z",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No billing account for organisation",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found for organisation",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_organisation_id": {
                        "summary": "Invalid organisation ID",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
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
                        "summary": "Failed to fetch billing account",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to fetch billing account",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_billing_account_custom_errors = ["404", "422", "500"]
get_billing_account_custom_success = {
    "status_code": 200,
    "description": "Billing account retrieved successfully.",
}


# ADD PAYMENT METHOD DOCS
add_payment_method_responses = {
    201: {
        "description": "Payment method added successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Payment method added",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "Payment method added",
                            "data": {
                                "id": "e5b2dd4b-9a71-4d4f-9c11-bc4100000001",
                                "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                "stripe_payment_method_id": "pm_1PvABCDEF12345678",
                                "card_brand": "visa",
                                "last4": "4242",
                                "exp_month": 12,
                                "exp_year": 2030,
                                "is_default": True,
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Validation or business rule error",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Invalid payment method data",
                        "value": {
                            "error": "ERROR",
                            "message": "Card brand is not supported",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "billing_not_found": {
                        "summary": "No billing account",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_payload": {
                        "summary": "Invalid request payload",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
                                "stripe_payment_method_id": ["Field required"],
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
                        "summary": "Failed to add payment method",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to add payment method",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

add_payment_method_custom_errors = ["400", "404", "422", "500"]
add_payment_method_custom_success = {
    "status_code": 201,
    "description": "Payment method added successfully.",
}


# LIST PAYMENT METHODS DOCS
list_payment_methods_responses = {
    200: {
        "description": "Payment methods retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Multiple payment methods",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Payment methods retrieved",
                            "data": [
                                {
                                    "id": "e5b2dd4b-9a71-4d4f-9c11-bc4100000001",
                                    "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                    "stripe_payment_method_id": "pm_1PvABCDEF12345678",
                                    "card_brand": "visa",
                                    "last4": "4242",
                                    "exp_month": 12,
                                    "exp_year": 2030,
                                    "is_default": True,
                                },
                                {
                                    "id": "c7a3e0af-9d3e-4c55-8b97-cc4100000002",
                                    "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                    "stripe_payment_method_id": "pm_1PvXYZ1234567890",
                                    "card_brand": "mastercard",
                                    "last4": "5100",
                                    "exp_month": 11,
                                    "exp_year": 2029,
                                    "is_default": False,
                                },
                            ],
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "billing_not_found": {
                        "summary": "No billing account",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_organisation_id": {
                        "summary": "Invalid organisation ID",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
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
                        "summary": "Failed to list payment methods",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to list payment methods",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

list_payment_methods_custom_errors = ["404", "422", "500"]
list_payment_methods_custom_success = {
    "status_code": 200,
    "description": "Payment methods retrieved successfully.",
}


# SET DEFAULT PAYMENT METHOD DOCS
set_default_payment_method_responses = {
    200: {
        "description": "Default payment method set successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Default payment method set",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Default payment method set",
                            "data": {
                                "id": "e5b2dd4b-9a71-4d4f-9c11-bc4100000001",
                                "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                "stripe_payment_method_id": "pm_1PvABCDEF12345678",
                                "card_brand": "visa",
                                "last4": "4242",
                                "exp_month": 12,
                                "exp_year": 2030,
                                "is_default": True,
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Validation or ownership error",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_payment_method": {
                        "summary": "Payment method does not belong to account",
                        "value": {
                            "error": "ERROR",
                            "message": "Payment method does not belong to this billing account",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "billing_not_found": {
                        "summary": "No billing account",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_ids": {
                        "summary": "Invalid organisation or payment method ID",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
                                "payment_method_id": ["value is not a valid uuid"],
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
                        "summary": "Failed to set default payment method",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to set default payment method",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

set_default_payment_method_custom_errors = ["400", "404", "422", "500"]
set_default_payment_method_custom_success = {
    "status_code": 200,
    "description": "Default payment method set successfully.",
}


# DELETE PAYMENT METHOD DOCS
delete_payment_method_responses = {
    204: {
        "description": "Payment method deleted successfully (no content)",
    },
    404: {
        "description": "Payment method not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No such payment method",
                        "value": {
                            "error": "ERROR",
                            "message": "Payment method not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_ids": {
                        "summary": "Invalid organisation or payment method ID",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
                                "payment_method_id": ["value is not a valid uuid"],
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
                        "summary": "Failed to delete payment method",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to delete payment method",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

delete_payment_method_custom_errors = ["404", "422", "500"]
delete_payment_method_custom_success = {
    "status_code": 204,
    "description": "Payment method deleted successfully.",
}


# LIST PLANS DOCS
list_plans_responses = {
    200: {
        "description": "Subscription plans retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Available plans",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Plans retrieved",
                            "data": [
                                {
                                    "code": "monthly",
                                    "label": "Pro Monthly",
                                    "price_id": "price_123_monthly",
                                    "product_id": "prod_123_monthly",
                                    "interval": "month",
                                    "currency": "USD",
                                    "amount": 2900,
                                },
                                {
                                    "code": "yearly",
                                    "label": "Pro Yearly",
                                    "price_id": "price_123_yearly",
                                    "product_id": "prod_123_yearly",
                                    "interval": "year",
                                    "currency": "USD",
                                    "amount": 29000,
                                },
                            ],
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_organisation_id": {
                        "summary": "Invalid organisation ID",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
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
                        "summary": "Failed to retrieve plans",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to retrieve plans",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

list_plans_custom_errors = ["422", "500"]
list_plans_custom_success = {
    "status_code": 200,
    "description": "Subscription plans retrieved successfully.",
}


# CREATE INVOICE DOCS
create_invoice_record_responses = {
    201: {
        "description": "Invoice created successfully (Stripe + local history)",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Invoice created",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "Invoice record created",
                            "data": {
                                "id": "a2b3c4d5-0000-0000-0000-000000000001",
                                "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                "stripe_invoice_id": "in_123456789",
                                "stripe_price_id": "price_123",
                                "product_id": "prod_123",
                                "quantity": 1,
                                "amount": 2900,
                                "currency": "USD",
                                "status": "open",
                                "description": "Pro Monthly subscription",
                                "created_at": "2025-01-01T00:00:00Z",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid product or business rule error",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_product": {
                        "summary": "Unknown product",
                        "value": {
                            "error": "ERROR",
                            "message": "Unknown or unsupported product",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "billing_not_found": {
                        "summary": "No billing account",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_payload": {
                        "summary": "Invalid invoice payload",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
                                "product_id": ["Field required"],
                                "quantity": ["Input should be greater than 0"],
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
                        "summary": "Failed to create invoice record",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to create invoice record",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

create_invoice_record_custom_errors = ["400", "404", "422", "500"]
create_invoice_record_custom_success = {
    "status_code": 201,
    "description": "Invoice created successfully (Stripe + local history).",
}


# LIST INVOICES DOCS
list_invoices_responses = {
    200: {
        "description": "Invoices retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Invoice list",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Invoices retrieved",
                            "data": [
                                {
                                    "id": "a2b3c4d5-0000-0000-0000-000000000001",
                                    "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                    "stripe_invoice_id": "in_123456789",
                                    "stripe_price_id": "price_123",
                                    "product_id": "prod_123",
                                    "quantity": 1,
                                    "amount": 2900,
                                    "currency": "USD",
                                    "status": "open",
                                    "description": "Pro Monthly subscription",
                                    "created_at": "2025-01-01T00:00:00Z",
                                },
                                {
                                    "id": "a2b3c4d5-0000-0000-0000-000000000002",
                                    "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                    "stripe_invoice_id": "in_987654321",
                                    "stripe_price_id": "price_456",
                                    "product_id": "prod_456",
                                    "quantity": 10,
                                    "amount": 19900,
                                    "currency": "USD",
                                    "status": "paid",
                                    "description": "Usage-based overage",
                                    "created_at": "2025-01-15T00:00:00Z",
                                },
                            ],
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Billing account not found",
        "content": {
            "application/json": {
                "examples": {
                    "billing_not_found": {
                        "summary": "No billing account",
                        "value": {
                            "error": "ERROR",
                            "message": "Billing account not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_organisation_id": {
                        "summary": "Invalid organisation ID",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["value is not a valid uuid"],
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
                        "summary": "Failed to list invoices",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to list invoices",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

list_invoices_custom_errors = ["404", "422", "500"]
list_invoices_custom_success = {
    "status_code": 200,
    "description": "Invoices retrieved successfully.",
}
