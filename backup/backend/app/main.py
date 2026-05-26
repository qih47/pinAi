import importlib.util
import logging
import os

from app.core.logging_setup import configure_logging
from app.core.paths import apply_huggingface_hotfix, setup_paths

configure_logging()
logger = logging.getLogger(__name__)

_app_dir, _backend_dir = setup_paths(__file__)
apply_huggingface_hotfix()

perf_status = "Default"
perf_path = os.path.join(_app_dir, "core", "hardware.py")
try:
    if os.path.exists(perf_path):
        spec = importlib.util.spec_from_file_location("performance_mod", perf_path)
        perf_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(perf_mod)
        perf_mod.optimize_torch()
        perf_status = "Optimized (Ampere A40)"
except Exception as e:
    logger.error("Failed to load performance module: %s", e)

from app.core.app_factory import create_app
from app.core.config import settings

app = create_app()

logger.info(
    "CAKRA AI ready | model=%s | hardware=%s",
    settings.primary_model,
    perf_status,
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=5000, reload=True, log_level="info"
    )
