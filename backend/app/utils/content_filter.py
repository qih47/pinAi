import re
import logging
from fastapi import HTTPException

logger = logging.getLogger("CAKRA_CONTENT_FILTER")

# Blacklist of prohibited words (can be extended)
# Mix of English and Indonesian explicit/toxic words
BANNED_WORDS = {
    "porn", "porno", "bokep", "ngentot", "memek", "kontol", "jembut",
    "sex", "seks", "nude", "bugil", "telanjang", "nsfw",
    "xxx", "x-rated", "milf", "blowjob", "handjob",
    "rape", "perkosa", "pedophile", "pedofil",
    "murder", "bunuh", "teroris", "terrorist", "bombing", "ngebom"
}

def contains_prohibited_content(text: str) -> bool:
    """
    Checks if the text contains heavily prohibited content.
    Returns True if violation is found.
    """
    if not text:
        return False
        
    text_lower = text.lower()
    
    # Check absolute word matches (boundaries)
    for word in BANNED_WORDS:
        # We use regex word boundaries to prevent matching 'Middlesex' for 'sex'
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, text_lower):
            logger.warning(f"[CONTENT_FILTER] Prohibited keyword detected: '{word}'")
            return True
            
    return False

def assert_safe_content(text: str) -> None:
    """
    Raises an HTTPException if content is prohibited.
    Useful for intercepting user prompts directly in endpoints.
    """
    if contains_prohibited_content(text):
        raise HTTPException(
            status_code=400,
            detail="Pesan Anda melanggar Kebijakan Penggunaan Cakra AI (Mengandung konten SARA/Pornografi/Kekerasan)."
        )
