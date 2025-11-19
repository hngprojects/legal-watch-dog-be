import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

if __name__ == "__main__":
    from app.api.utils.email_verifier import BusinessEmailVerifier, EmailType

    verifier = BusinessEmailVerifier()

    # Test cases
    test_emails = [
        "john.doe@company.com",  # Business email
        "user@gmail.com",  # Personal email
        "support@company.com",  # Role-based business email
        "temp@mailinator.com",  # Disposable email
        "invalid-email",  # Invalid syntax
        "admin@startup.io",  # Role-based
        "contact@microsoft.com",  # Role-based business
        "admin@hng.tech",  # Test this domain
    ]

    print("=" * 80)
    print("EMAIL VERIFICATION RESULTS")
    print("=" * 80)

    for email in test_emails:
        result = verifier.verify_email(email)

        print(f"\nEmail: {result.email}")
        print(f"Valid: {result.is_valid}")
        print(f"Type: {result.email_type.value}")
        print(f"Domain: {result.domain}")
        print(f"MX Records: {result.has_mx_records}")
        print(f"Free Provider: {result.is_free_provider}")
        print(f"Disposable: {result.is_disposable}")
        print(f"Role-based: {result.is_role_based}")
        print(f"Confidence: {result.confidence_score:.2%}")

        if result.error_message:
            print(f"Error: {result.error_message}")

        print("-" * 80)

    # Demonstrate batch verification
    print("\n" + "=" * 80)
    print("BATCH VERIFICATION")
    print("=" * 80)

    batch_results = verifier.batch_verify(test_emails[:3])
    business_emails = [r for r in batch_results if r.email_type == EmailType.BUSINESS]

    print(f"\nTotal verified: {len(batch_results)}")
    print(f"Business emails found: {len(business_emails)}")

    for result in business_emails:
        print(f"  - {result.email} (confidence: {result.confidence_score:.2%})")
