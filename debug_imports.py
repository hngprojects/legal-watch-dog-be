import os
import sys

sys.path.append(os.getcwd())

try:
    print("Config imported successfully")
except Exception as e:
    print(f"Config import failed: {e}")

try:
    print("SourceService imported successfully")
except Exception as e:
    print(f"SourceService import failed: {e}")

try:
    print("SourceRoutes imported successfully")
except Exception as e:
    print(f"SourceRoutes import failed: {e}")
