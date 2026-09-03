"""
CAKRA AI — Global Tools Package
================================
Kumpulan tool global yang bisa dipanggil dari semua mode pipeline.

Tools:
- unified_extractor: Ekstraksi dokumen multi-format (PDF/DOCX/XLSX/TXT/gambar)
- document_resolver: Resolver metadata dan path fisik regulasi
- artifact_generator: Generator & penyimpan file hasil AI
- visual_generator: Builder Mermaid diagram & Chart.js config
- web_reader: URL fetcher & content extractor
- persuratan: Generator naskah dinas PT Pindad
- geocoding: Geocoding & lokasi Pindad
"""

from backend.app.services.tools.artifact_generator import (
    write_artifact,
    sanitize_filename,
    get_mime_type,
    get_relative_artifact_path,
)
from backend.app.services.tools.visual_generator import (
    validate_mermaid,
    wrap_mermaid_block,
    build_chartjs_config,
)
from backend.app.services.tools.document_resolver import (
    find_valid_pdf_file,
    resolve_status_berlaku,
    resolve_mencabut_text,
    get_peraturan_abs_path,
)
from backend.app.services.tools.unified_extractor import (
    extract_document,
    ExtractedDocument,
    ExtractedPage,
)

__all__ = [
    "write_artifact",
    "sanitize_filename",
    "get_mime_type",
    "get_relative_artifact_path",
    "validate_mermaid",
    "wrap_mermaid_block",
    "build_chartjs_config",
    "find_valid_pdf_file",
    "resolve_status_berlaku",
    "resolve_mencabut_text",
    "get_peraturan_abs_path",
    "extract_document",
    "ExtractedDocument",
    "ExtractedPage",
]

