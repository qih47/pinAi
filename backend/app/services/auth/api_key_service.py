import secrets
import hashlib
import logging
from typing import List, Dict, Any, Optional

from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_API_KEY_SERVICE")

class APIKeyService:
    @staticmethod
    async def generate_api_key(app_name: str, owner_npp: str) -> Dict[str, Any]:
        """
        Generate a new API Key for an external application and save to DB.
        """
        raw_key = "cakra_live_" + secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:16] + "..."

        try:
            async with get_db() as conn:
                await conn.execute("""
                    INSERT INTO api_keys (key_hash, key_prefix, app_name, owner_npp)
                    VALUES ($1, $2, $3, $4)
                """, key_hash, key_prefix, app_name, owner_npp)
                logger.info(f"🔑 [API_KEY] New key generated for {app_name} by {owner_npp}")
        except Exception as e:
            logger.error(f"Failed to generate API Key: {e}")
            raise RuntimeError("Database error when generating API Key")

        return {
            "raw_key": raw_key,
            "app_name": app_name
        }

    @staticmethod
    async def list_api_keys() -> List[Dict[str, Any]]:
        """
        List all API keys generated. 
        """
        try:
            async with get_db() as conn:
                rows = await conn.fetch("""
                    SELECT id, key_prefix, app_name, owner_npp, is_active, total_requests, created_at, last_used_at
                    FROM api_keys
                    ORDER BY created_at DESC
                """)
                return rows
        except Exception as e:
            logger.error(f"Failed to list API Keys: {e}")
            raise RuntimeError("Database error when listing API Keys")

    @staticmethod
    async def revoke_api_key(key_id: str) -> bool:
        """
        Revoke (deactivate) an API key.
        """
        try:
            async with get_db() as conn:
                result = await conn.execute("UPDATE api_keys SET is_active = FALSE WHERE id = $1", key_id)
                # Ensure something was updated
                if result == "UPDATE 0":
                    return False
                return True
        except Exception as e:
            logger.error(f"Failed to revoke API Key: {e}")
            raise RuntimeError("Database error when revoking API Key")

api_key_service = APIKeyService()
