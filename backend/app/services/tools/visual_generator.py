"""
CAKRA AI — Visual Generator
=============================
Builder untuk Mermaid diagram dan Chart.js configuration.
Memvalidasi syntax Mermaid dan membantu rendering chart secara terstruktur.
"""

import re
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("CAKRA_VISUAL_GENERATOR")

# Direktif Mermaid yang valid (subset yang sering dipakai)
_VALID_MERMAID_TYPES = {
    "flowchart", "graph", "sequenceDiagram", "classDiagram",
    "stateDiagram", "stateDiagram-v2", "gantt", "pie", "er",
    "erDiagram", "journey", "gitGraph", "mindmap", "timeline",
    "quadrantChart", "xychart-beta",
}

# Tipe chart Chart.js yang didukung
_VALID_CHART_TYPES = {
    "bar", "line", "pie", "doughnut", "radar",
    "polarArea", "bubble", "scatter",
}


# ─── Mermaid Helpers ──────────────────────────────────────────────────────────
def validate_mermaid(code: str) -> Dict[str, Any]:
    """
    Validasi dasar syntax Mermaid diagram.

    Returns:
        {"valid": bool, "type": str|None, "error": str|None}
    """
    if not code or not code.strip():
        return {"valid": False, "type": None, "error": "Kode Mermaid kosong"}

    lines = code.strip().splitlines()
    first_line = lines[0].strip().lower() if lines else ""

    detected_type = None
    for t in _VALID_MERMAID_TYPES:
        if first_line.startswith(t.lower()):
            detected_type = t
            break

    if not detected_type:
        return {
            "valid": False,
            "type": None,
            "error": f"Tipe diagram tidak dikenal: '{lines[0].strip() if lines else ''}'",
        }

    # Cek bracket balance dasar
    open_b = code.count("{")
    close_b = code.count("}")
    if abs(open_b - close_b) > 5:
        return {
            "valid": False,
            "type": detected_type,
            "error": f"Bracket tidak seimbang (open={open_b}, close={close_b})",
        }

    return {"valid": True, "type": detected_type, "error": None}


def wrap_mermaid_block(code: str, title: Optional[str] = None) -> str:
    """
    Wrap kode Mermaid dalam fenced code block markdown.
    Optionally tambahkan title sebagai komentar.
    """
    parts = []
    if title:
        parts.append(f"---\ntitle: {title}\n---")
    parts.append(code.strip())
    return "```mermaid\n" + "\n".join(parts) + "\n```"


# ─── Chart.js Helpers ─────────────────────────────────────────────────────────
def build_chartjs_config(
    chart_type: str,
    labels: List[str],
    datasets: List[Dict[str, Any]],
    title: Optional[str] = None,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build konfigurasi Chart.js yang valid dan lengkap.

    Args:
        chart_type: "bar" | "line" | "pie" | "doughnut" | dll
        labels: Label sumbu X atau segmen pie
        datasets: List dataset Chart.js (sudah include data, label, backgroundColor)
        title: Judul chart (opsional)
        x_label: Label sumbu X (opsional)
        y_label: Label sumbu Y (opsional)

    Returns:
        Dict konfigurasi Chart.js siap render
    """
    if chart_type not in _VALID_CHART_TYPES:
        logger.warning(f"[VISUAL_GEN] Tipe chart tidak dikenal: {chart_type}, fallback ke 'bar'")
        chart_type = "bar"

    config: Dict[str, Any] = {
        "type": chart_type,
        "data": {
            "labels": labels,
            "datasets": datasets,
        },
        "options": {
            "responsive": True,
            "plugins": {
                "legend": {"position": "top"},
            },
        },
    }

    if title:
        config["options"]["plugins"]["title"] = {
            "display": True,
            "text": title,
        }

    # Tambah skala hanya untuk chart non-radial
    if chart_type not in ("pie", "doughnut", "polarArea", "radar"):
        config["options"]["scales"] = {}
        if x_label:
            config["options"]["scales"]["x"] = {
                "title": {"display": True, "text": x_label}
            }
        if y_label:
            config["options"]["scales"]["y"] = {
                "title": {"display": True, "text": y_label}
            }

    return config


def build_simple_bar_chart(
    labels: List[str],
    values: List[float],
    title: str,
    color: str = "rgba(99, 102, 241, 0.8)",
) -> Dict[str, Any]:
    """
    Shortcut builder untuk bar chart sederhana satu dataset.
    """
    dataset = {
        "label": title,
        "data": values,
        "backgroundColor": color,
        "borderColor": color.replace("0.8", "1.0"),
        "borderWidth": 1,
    }
    return build_chartjs_config(
        chart_type="bar",
        labels=labels,
        datasets=[dataset],
        title=title,
    )
