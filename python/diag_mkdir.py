import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
data_sessions_path = os.path.join(base_dir, "data", "sessions")

print(f"Base dir: {base_dir}")
print(f"Target path: {data_sessions_path}")

try:
    if not os.path.exists(os.path.dirname(data_sessions_path)):
        print(f"Parent dir {os.path.dirname(data_sessions_path)} does not exist!")
    
    os.makedirs(data_sessions_path, exist_ok=True)
    print("Successfully created data/sessions")
except Exception as e:
    print(f"Failed to create data/sessions: {type(e).__name__}: {e}")
