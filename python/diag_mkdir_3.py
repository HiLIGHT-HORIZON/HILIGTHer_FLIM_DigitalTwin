from pathlib import Path
import os

p = Path("data/sessions")
print(f"Path: {p.absolute()}")
try:
    p.mkdir(parents=True, exist_ok=True)
    print("Successfully created via pathlib")
except Exception as e:
    print(f"Pathlib failed: {type(e).__name__}: {e}")
