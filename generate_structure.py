import os

# Lokasi folder saat ini (tempat script berada)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

folders = [
    ".",           # pinAi (folder utama)
    "nlp",
    "memory",
    "rag",
    "llm",
    "tools",
    "chat",
    "database",
]

for folder in folders:
    folder_path = os.path.join(BASE_DIR, folder)
    init_path = os.path.join(folder_path, "__init__.py")

    # Pastikan folder ada
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Buat file __init__.py
    with open(init_path, "w") as f:
        f.write("# Marks this directory as a Python package.\n")

print("🔥 Semua __init__.py berhasil dibuat!")
