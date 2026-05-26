"""Bootstrap Python path and optional dependency hotfixes."""
import logging
import os
import sys

logger = logging.getLogger(__name__)


def setup_paths(main_file: str) -> tuple[str, str]:
    app_dir = os.path.dirname(os.path.abspath(main_file))
    backend_dir = os.path.dirname(app_dir)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    return app_dir, backend_dir


def apply_huggingface_hotfix() -> None:
    try:
        import huggingface_hub
        import huggingface_hub.file_download as hf_file

        if not hasattr(huggingface_hub, "cached_download"):
            setattr(huggingface_hub, "cached_download", hf_file.hf_hub_download)
        if not hasattr(hf_file, "cached_download"):
            setattr(hf_file, "cached_download", hf_file.hf_hub_download)
    except Exception as e:
        logger.warning("HF Hotfix skipped: %s", e)
