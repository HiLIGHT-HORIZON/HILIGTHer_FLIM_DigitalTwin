import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
test_path = os.path.join(base_dir, "test_dir")

print(f"Base dir: {base_dir}")
print(f"Target path: {test_path}")

try:
    os.makedirs(test_path, exist_ok=True)
    print("Successfully created test_dir")
except Exception as e:
    print(f"Failed to create test_dir: {type(e).__nmae__}: {e}")
