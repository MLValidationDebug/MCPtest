"""Test if tools can be imported."""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from mcp_server.tools import calculator, notes_manager, get_current_time, list_timezones
    print("✅ All tools imported successfully!")
    print(f"   - calculator: {calculator}")
    print(f"   - notes_manager: {notes_manager}")
    print(f"   - get_current_time: {get_current_time}")
    print(f"   - list_timezones: {list_timezones}")
except Exception as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
