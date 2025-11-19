# pinAi/tools/anti_halu.py

def is_corporate_answer_possible(rag_items, learning_items, memory_items):
    # Ada dokumen perusahaan valid
    if rag_items and rag_items[0].get("similarity", 0) >= 0.40:
        return True

    # Ada koreksi user sebelumnya
    if learning_items:
        return True

    # Ada long-term memory
    if memory_items:
        return True

    # Tidak ada dasar data → jangan jawab
    return False
