"""Test that Celery tasks are properly registered."""

from app.celery_app import celery_app


def test_task_registration():
    """Check if tasks are registered with Celery."""
    celery_app.finalize()
    registered_tasks = celery_app.tasks.keys()
    
    print("=" * 60)
    print("REGISTERED CELERY TASKS")
    print("=" * 60)
    
    for task_name in sorted(registered_tasks):
        if not task_name.startswith("celery."):
            print(f"✓ {task_name}")
    
    print("=" * 60)
    
    # Check for our specific tasks
    expected_tasks = [
        "app.api.modules.v1.scraping.service.tasks.dispatch_due_sources",
        "app.api.modules.v1.scraping.service.tasks.scrape_source",
    ]
    
    for task in expected_tasks:
        if task in registered_tasks:
            print(f"✅ Found: {task}")
        else:
            print(f"❌ Missing: {task}")

if __name__ == "__main__":
    test_task_registration()
