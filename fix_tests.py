#!/usr/bin/env python3
"""
Script to add Organization and Project setup to all tests in test_ticket_notification_services.py
"""

import re

# Read the file
with open(
    r"c:\Users\DanielsFega\legal-watch-dog-be\tests\modules\v1\notifications\service\test_ticket_notification_services.py",
    "r",
    encoding="utf-8",
) as f:
    content = f.read()

# Pattern to find where we need to insert org/project setup
# Look for lines like: org_id = uuid4() followed by project_id = uuid4()
# and NOT already having org = Organization

setup_code = """    # Create Organization and Project to satisfy foreign key constraints
    org = Organization(id=org_id, name="Test Org")
    project = Project(id=project_id, org_id=org_id, title="Test Project")
    
    async_session.add_all([org, project])
    await async_session.commit()

"""

# Find all occurrences where we have org_id and project_id but no Organization creation
pattern = (
    r"(    org_id = uuid4\(\)\r?\n    project_id = uuid4\(\)\r?\n)(?!.*?# Create Organization)"
)

# Replace with the pattern plus the setup code
replacement = r"\1" + setup_code

content_new = re.sub(pattern, replacement, content)

# Write back
with open(
    r"c:\Users\DanielsFega\legal-watch-dog-be\tests\modules\v1\notifications\service\test_ticket_notification_services.py",
    "w",
    encoding="utf-8",
) as f:
    f.write(content_new)

print("Done! Added Organization and Project setup to all tests.")
