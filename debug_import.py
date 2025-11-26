import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

print("Python Path:", sys.path)

try:
    from app.main import app
    print("Import successful")
except ModuleNotFoundError as e:
    print(f"ModuleNotFoundError: {e}")