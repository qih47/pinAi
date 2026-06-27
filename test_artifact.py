import sys
import os
from pathlib import Path

# Add backend directory to path
sys.path.append("/home/qisthi/pinAi/backend")

from app.core.paths import get_account_session_dir
from app.api.endpoints.chat.artifacts import read_artifact_file

async def run_test():
    current_user_npp = "06652"
    session_id = "117e9241-5c53-4ab0-84bf-c6a15d830b7c"
    filename = "accounts/06652/117e9241-5c53-4ab0-84bf-c6a15d830b7c/artifacts/Login.jsx"
    
    safe_name = Path(filename).name
    print(f"safe_name: {safe_name}")
    
    target_dir = get_account_session_dir(current_user_npp, session_id, "artifacts")
    print(f"target_dir: {target_dir}")
    print(f"target_dir.exists(): {target_dir.exists()}")
    
    target = target_dir / safe_name
    print(f"target: {target}")
    print(f"target.exists(): {target.exists()}")
    print(f"target.is_file(): {target.is_file()}")
    
    try:
        rel = target.resolve().relative_to(target_dir.resolve())
        print(f"resolve OK: {rel}")
    except Exception as e:
        print(f"resolve ERROR: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_test())
