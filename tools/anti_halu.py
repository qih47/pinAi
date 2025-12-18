# pinAi/tools/anti_halu.py

def is_corporate_answer_possible(rag_items, learning_items, memory_items):
    """
    Validasi apakah AI diperbolehkan menjawab pertanyaan berbasis data.
    """

    # ==============================================
    # 1. PRIORITAS UTAMA: DOKUMEN PERUSAHAAN (RAG)
    # ==============================================
    if rag_items:

        # Cek similarity tertinggi
        top_sim = rag_items[0].get("similarity", 0)

        # Wajib sangat relevan untuk menjawab (>= 0.70)
        if top_sim >= 0.70:
            return True

    # ==============================================
    # 2. KOREKSI USER → selalu valid untuk menjawab
    # ==============================================
    if learning_items:
        return True

    # ==============================================
    # 3. MEMORY USER → hanya untuk percakapan biasa,
    #    TIDAK untuk dokumen perusahaan!
    # ==============================================
    # memory tidak dipakai sebagai validasi perusahaan
        # cek memori personal
    if memory_items:
        return True

    # ==============================================
    # TIDAK ADA DASAR → jangan jawab
    # ==============================================
    return False
