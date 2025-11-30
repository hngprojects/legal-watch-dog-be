"""Manually test the dispatch task."""

import sys

from app.api.modules.v1.scraping.service.tasks import dispatch_due_sources


def test_manual_dispatch():
    """Test dispatching task manually (blocking)."""
    print("=" * 60)
    print("TESTING MANUAL TASK DISPATCH")
    print("=" * 60)
    
    try:
        # Execute task synchronously
        result = dispatch_due_sources.apply()
        
        print("\n✅ Task completed!")
        print(f"Task ID: {result.id}")
        print(f"State: {result.state}")
        print(f"Result: {result.get(timeout=30)}")
        
    except Exception as e:
        print(f"\n❌ Task failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_manual_dispatch()

