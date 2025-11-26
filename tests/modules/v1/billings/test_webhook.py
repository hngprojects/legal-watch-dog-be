import sys
print('Updated Python Path:', sys.path)
import os

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))
print("Updated Python Path:", sys.path)

import pytest
from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch, MagicMock

# Initialize the test client
client = TestClient(app)

@pytest.fixture
def stripe_webhook_payload():
    """Fixture for a sample Stripe webhook payload."""
    return {
        "id": "evt_test_webhook",
        "object": "event",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_test",
                "amount": 2000,
                "currency": "usd",
                "status": "succeeded"
            }
        }
    }

# Mock the Stripe Webhook construct_event method to bypass signature verification
@patch("stripe.Webhook.construct_event")
def test_stripe_webhook_success(mock_construct_event, stripe_webhook_payload):
    """Test the Stripe webhook endpoint for a successful event."""
    # Create a mock event object with attributes
    mock_event = MagicMock()
    mock_event.type = "payment_intent.succeeded"
    mock_construct_event.return_value = mock_event

    response = client.post(
        "/api/v1/webhook/stripe",
        json=stripe_webhook_payload,
        headers={"Stripe-Signature": "test_signature"}  # Replace with a valid signature if needed
    )

    # Assert the response status code
    assert response.status_code == 200

    # Assert the response content
    assert response.json() == {"status": "success"}

@patch("stripe.Webhook.construct_event", side_effect=ValueError("Invalid payload"))
def test_stripe_webhook_invalid_payload(mock_construct_event):
    """Test the Stripe webhook endpoint with an invalid payload."""
    # Send a POST request with an invalid payload
    response = client.post(
        "/api/v1/webhook/stripe",
        json={},
        headers={"Stripe-Signature": "test_signature"}
    )

    # Assert the response status code
    assert response.status_code == 400

    # Assert the response content
    assert response.json()["message"] == "Invalid payload"