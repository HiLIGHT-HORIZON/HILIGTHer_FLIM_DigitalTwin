import os

try:
    os.makedirs("sessions", exist_ok=True)
    print("Success create 'sessions' in current dir")
except Exception as e:
    print(f"Failed to create 'sessions': {type(e).__name__}: {e}")
