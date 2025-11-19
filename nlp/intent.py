# pinAi/nlp/intent.py
import re

def is_memory_instruction(text):
    text = text.lower()
    patterns = [
        r"panggil saya", r"mulai sekarang", r"tolong ingat",
        r"saya ingin kamu", r"mulai hari ini", r"anggap bahwa",
        r"jika saya bilang", r"kalau aku bilang", r"preferensi saya"
    ]
    return any(re.search(p, text) for p in patterns)

def is_correction(text):
    text = text.lower()
    return ("seharusnya" in text or "koreksi" in text or "yang benar" in text)
