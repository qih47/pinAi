import os
from pathlib import Path

# Mendapatkan root directory dari file ini (backend/app/core/paths.py)
# Naik 3 tingkat untuk sampai ke root project (pinAi/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ROOT_DIR = BASE_DIR

def get_abs_path(relative_path: str) -> str:
    """Mengubah path relatif menjadi absolut dari root project."""
    return str(BASE_DIR / relative_path)

# Definisi jalur-jalur krusial
DOCUMENTS_DIR = get_abs_path("db_doc")
UPLOAD_DIR = get_abs_path("uploads")
NOSQL_DATA_DIR = get_abs_path("data/nosql")
LOGS_DIR = get_abs_path("logs")

# Direktori Accounts dan File Peraturan
ACCOUNTS_DIR = get_abs_path("accounts")
FILE_PERATURAN_DIR = get_abs_path("file_peraturan")

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
    """Mendapatkan path untuk penyimpanan berbasis sesi chat per akun di dalam folder brain/"""
    safe_npp = "".join(c if c.isalnum() else "_" for c in str(npp)).strip("_")
    if not safe_npp:
        safe_npp = "guest"
        
    safe_session = "".join(c if c.isalnum() or c == "-" else "_" for c in str(session_id)).strip("_")
    safe_category = "".join(c if c.isalnum() else "_" for c in str(category)).strip("_")
    
    account_session_path = Path(ACCOUNTS_DIR) / safe_npp / safe_session / "brain" / safe_category
    account_session_path.mkdir(parents=True, exist_ok=True)
    return account_session_path

def get_collab_room_brain_dir(master_npp: str, room_id: str, category: str = "") -> Path:
    """
    Mendapatkan path penyimpanan Collab Room Brain di bawah akun Room Master (SSOT).
    Struktur: accounts/{master_npp}/collab/{room_id}/brain/{category}
    """
    safe_npp = "".join(c if c.isalnum() else "_" for c in str(master_npp)).strip("_") or "guest"
    safe_room = "".join(c if c.isalnum() or c == "-" else "_" for c in str(room_id)).strip("_")
    
    room_brain_path = Path(ACCOUNTS_DIR) / safe_npp / "collab" / safe_room / "brain"
    if category:
        safe_cat = "".join(c if c.isalnum() else "_" for c in str(category)).strip("_")
        room_brain_path = room_brain_path / safe_cat
        
    room_brain_path.mkdir(parents=True, exist_ok=True)
    return room_brain_path

def get_collab_member_dir(member_npp: str, room_id: str) -> Path:
    """Mendapatkan path direktori kolaborasi anggota tim."""
    safe_npp = "".join(c if c.isalnum() else "_" for c in str(member_npp)).strip("_") or "guest"
    safe_room = "".join(c if c.isalnum() or c == "-" else "_" for c in str(room_id)).strip("_")
    member_path = Path(ACCOUNTS_DIR) / safe_npp / "collab" / safe_room
    member_path.mkdir(parents=True, exist_ok=True)
    return member_path

def ensure_collab_symlink(master_npp: str, member_npp: str, room_id: str) -> bool:
    """
    Membuat symlink dari accounts/{member_npp}/collab/{room_id}/brain
    menuju accounts/{master_npp}/collab/{room_id}/brain (SSOT).
    """
    if str(master_npp).strip() == str(member_npp).strip():
        return True
    try:
        master_brain = get_collab_room_brain_dir(master_npp, room_id)
        member_dir = get_collab_member_dir(member_npp, room_id)
        symlink_target = member_dir / "brain"

        if symlink_target.is_symlink():
            if symlink_target.resolve() == master_brain.resolve():
                return True
            symlink_target.unlink()
        elif symlink_target.exists():
            return False

        symlink_target.symlink_to(master_brain, target_is_directory=True)
        return True
    except Exception:
        return False

# Pastikan folder exist
for directory in [DOCUMENTS_DIR, UPLOAD_DIR, NOSQL_DATA_DIR, LOGS_DIR, ACCOUNTS_DIR, FILE_PERATURAN_DIR]:
    os.makedirs(directory, exist_ok=True)