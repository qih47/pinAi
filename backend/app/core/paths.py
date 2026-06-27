import os
from pathlib import Path

# Mendapatkan root directory dari file ini (backend/app/core/paths.py)
# Naik 3 tingkat untuk sampai ke root project (pinAi/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

def get_abs_path(relative_path: str) -> str:
    """Mengubah path relatif menjadi absolut dari root project."""
    return str(BASE_DIR / relative_path)

# Definisi jalur-jalur krusial
DOCUMENTS_DIR = get_abs_path("db_doc")
UPLOAD_DIR = get_abs_path("uploads")
NOSQL_DATA_DIR = get_abs_path("data/nosql")
LOGS_DIR = get_abs_path("logs")

# Direktori Accounts
ACCOUNTS_DIR = get_abs_path("accounts")

def get_account_dir(npp: str, category: str) -> Path:
    """Mendapatkan path untuk penyimpanan berbasis akun (NPP) berdasarkan kategori (images, artifacts, documents, cache)"""
    safe_npp = "".join(c if c.isalnum() else "_" for c in str(npp)).strip("_")
    if not safe_npp:
        safe_npp = "guest"
        
    safe_category = "".join(c if c.isalnum() else "_" for c in str(category)).strip("_")
    account_path = Path(ACCOUNTS_DIR) / safe_npp / safe_category
    account_path.mkdir(parents=True, exist_ok=True)
    return account_path

def get_account_session_dir(npp: str, session_id: str, category: str) -> Path:
    """Mendapatkan path untuk penyimpanan berbasis sesi chat per akun"""
    safe_npp = "".join(c if c.isalnum() else "_" for c in str(npp)).strip("_")
    if not safe_npp:
        safe_npp = "guest"
        
    safe_session = "".join(c if c.isalnum() or c == "-" else "_" for c in str(session_id)).strip("_")
    safe_category = "".join(c if c.isalnum() else "_" for c in str(category)).strip("_")
    
    account_session_path = Path(ACCOUNTS_DIR) / safe_npp / safe_session / safe_category
    account_session_path.mkdir(parents=True, exist_ok=True)
    return account_session_path

# Pastikan folder exist
for directory in [DOCUMENTS_DIR, UPLOAD_DIR, NOSQL_DATA_DIR, LOGS_DIR, ACCOUNTS_DIR]:
    os.makedirs(directory, exist_ok=True)