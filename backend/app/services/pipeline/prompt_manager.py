import logging
from typing import Dict
from jinja2 import Environment, meta, Template, BaseLoader
from backend.app.core.database import get_db

logger = logging.getLogger("CAKRA_PROMPT_MANAGER")

class PromptManager:
    """
    Singleton for managing Dynamic System Prompts.
    Fetches templates from PostgreSQL and caches them in memory.
    Uses Jinja2 for safe and dynamic template rendering.
    """
    def __init__(self):
        self._cache: Dict[str, Template] = {}
        # Gunakan strict_undefined=False agar variabel yang hilang tidak membuat error crash
        self.env = Environment(loader=BaseLoader()) 
        self._default_prompts = {}
        
    def register_default(self, name: str, template_str: str, description: str):
        """Daftarkan fallback prompt hardcoded."""
        self._default_prompts[name] = {
            "template": template_str,
            "description": description
        }

    async def initialize(self):
        """Memuat prompts dari database, dan melakukan seed jika kosong."""
        logger.info("[PROMPT_MANAGER] Initializing dynamic prompts cache...")
        try:
            async with get_db() as conn:
                # Ambil semua dari DB
                rows = await conn.fetch("SELECT name, template FROM system_prompts")
                db_prompts = {row['name']: row['template'] for row in rows}
                
                # Cek apakah ada prompt default yang belum masuk DB
                for name, data in self._default_prompts.items():
                    if name not in db_prompts:
                        logger.info(f"[PROMPT_MANAGER] Seeding default prompt into DB: {name}")
                        await conn.execute(
                            "INSERT INTO system_prompts (name, template, description) VALUES ($1, $2, $3)",
                            name, data["template"], data["description"]
                        )
                        db_prompts[name] = data["template"]
                    else:
                        # 🔥 UPDATE: Selalu overwrite isi DB dengan versi terbaru dari file Python
                        # agar perubahan prompt di file .py selalu tersinkronisasi ke DB
                        logger.info(f"[PROMPT_MANAGER] Updating prompt in DB from Python default: {name}")
                        await conn.execute(
                            "UPDATE system_prompts SET template = $1, description = $2 WHERE name = $3",
                            data["template"], data["description"], name
                        )
                        db_prompts[name] = data["template"]
                
                # Rebuild Cache
                self._cache.clear()
                for name, temp_str in db_prompts.items():
                    try:
                        self._cache[name] = self.env.from_string(temp_str)
                    except Exception as e:
                        logger.error(f"[PROMPT_MANAGER] Jinja syntax error on prompt {name}: {e}")
                        # Fallback ke default jika error
                        if name in self._default_prompts:
                            self._cache[name] = self.env.from_string(self._default_prompts[name]["template"])

        except Exception as e:
            logger.error(f"[PROMPT_MANAGER] Failed to initialize from DB: {e}. Falling back to hardcoded defaults.")
            # Fallback total
            self._cache.clear()
            for name, data in self._default_prompts.items():
                self._cache[name] = self.env.from_string(data["template"])

    async def refresh(self):
        """Alias untuk hot-reload."""
        await self.initialize()

    def render(self, name: str, **kwargs) -> str:
        """Render prompt dengan variabel tertentu."""
        template = self._cache.get(name)
        if not template:
            # Fallback just in case
            logger.warning(f"[PROMPT_MANAGER] Prompt '{name}' not found in cache!")
            if name in self._default_prompts:
                template = self.env.from_string(self._default_prompts[name]["template"])
            else:
                return ""
        try:
            return template.render(**kwargs)
        except Exception as e:
            logger.error(f"[PROMPT_MANAGER] Error rendering prompt '{name}': {e}")
            return f"[PROMPT RENDERING ERROR] {e}"

    async def get_all_prompts(self) -> list:
        """Mengambil semua prompt dari database untuk Prompt Studio."""
        try:
            async with get_db() as conn:
                rows = await conn.fetch("SELECT name, template, description, version, updated_at FROM system_prompts ORDER BY name ASC")
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to fetch prompts: {e}")
            raise RuntimeError(f"Database error: {e}")

    async def update_prompt(self, name: str, template: str):
        """Update sebuah prompt di DB dan picu hot-reload di PromptManager."""
        try:
            async with get_db() as conn:
                await conn.execute(
                    "UPDATE system_prompts SET template = $1, version = version + 1, updated_at = now() WHERE name = $2",
                    template, name
                )
            # Trigger Hot-Reload
            await self.refresh()
        except Exception as e:
            logger.error(f"Failed to update prompt {name}: {e}")
            raise RuntimeError(f"Database error: {e}")

prompt_manager = PromptManager()
