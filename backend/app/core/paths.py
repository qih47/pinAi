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
NOSQL_DATA_DIR = get_abs_path("data/nosql")
LOGS_DIR = get_abs_path("logs")

# Pastikan folder exist
for directory in [DOCUMENTS_DIR, NOSQL_DATA_DIR, LOGS_DIR]:
    os.makedirs(directory, exist_ok=True)