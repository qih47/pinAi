import re
import difflib
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("CAKRA_ASSET_DIFF")

COLUMN_SEMANTIC_ALIASES: Dict[str, str] = {
    # Status group
    "status": "status",
    "kondisi": "status",
    "state": "status",
    "progress": "status",
    "hasil": "status",
    "keadaan": "status",
    # ID/No group
    "no": "id",
    "nomor": "id",
    "#": "id",
    "id": "id",
    "kode": "id",
    "task id": "id",
    "bug id": "id",
    "key": "id",
    # Description group
    "deskripsi": "deskripsi",
    "keterangan": "deskripsi",
    "uraian": "deskripsi",
    "rincian": "deskripsi",
    "bug / revisi": "deskripsi",
    "bug/revisi": "deskripsi",
    "revisi": "deskripsi",
    "tugas": "deskripsi",
    "nama tugas": "deskripsi",
    "description": "deskripsi",
    "fitur": "deskripsi",
    "judul": "deskripsi",
    # PIC group
    "pic": "pic",
    "penanggung jawab": "pic",
    "penanggungjawab": "pic",
    "nama": "pic",
    "personil": "pic",
    "assigned to": "pic",
    "assignee": "pic",
    "role": "pic",
    # Notes group
    "catatan": "catatan",
    "notes": "catatan",
    "keterangan tambahan": "catatan",
    "feedback": "catatan",
    "dokumentasi": "catatan",
    "testing": "catatan",
}


@dataclass
class AssetDelta:
    """
    Representasi terstruktur hasil komparasi antara dua snapshot aset (spreadsheet, dokumen, web, kode).
    """
    has_changes: bool
    added_items: List[str] = field(default_factory=list)
    modified_items: List[str] = field(default_factory=list)
    removed_items: List[str] = field(default_factory=list)
    summary_text: str = ""
    change_type: str = "none"  # "table", "text", "identical", "none"
    metrics: Dict[str, Any] = field(default_factory=dict)


class UniversalAssetDiffEngine:
    """
    Universal Asset Diffing & Temporal State Awareness Engine.
    
    Agnostik format:
    1. Tabel / Spreadsheet (Markdown table |...|, CSV, TSV)
    2. Dokumen Teks / Regulasi / Markdown (Heading, Paragraf, Klausul)
    3. Kode & Teks Bebas
    4. Cross-Modal Diff (OCR Gambar vs Spreadsheet, Dokumen Revisi v1 vs v2)
    
    Menghasilkan rangkuman changelog presisi dan hemat token (~50-150 token)
    yang mengeliminasi Point-in-Time Blindness dan jebakan status 'Not Started'.
    """

    @classmethod
    def _normalize_header(cls, header: str) -> str:
        """
        Menormalkan nama kolom menjadi kluster semantik standar.
        Contoh: 'Penanggung Jawab' -> 'pic', 'Kondisi' -> 'status'.
        """
        clean = re.sub(r'[^a-zA-Z0-9\s/]', '', (header or "").strip().lower())
        for alias_key, canonical in COLUMN_SEMANTIC_ALIASES.items():
            if alias_key == clean or clean.startswith(alias_key):
                return canonical
        return clean

    @staticmethod
    def _fuzzy_match_key(candidate: str, targets: List[str], threshold: float = 0.82) -> Optional[str]:
        """
        Mencari kecocokan kunci baris meskipun ada typo minor dari OCR atau perbedaan formatting.
        Contoh: 'No 10: Bug Revisi' vs 'No 10: Bug Revislon', 'No. 20' vs 'No 20'.
        """
        if not candidate or not targets:
            return None
        if candidate in targets:
            return candidate

        c_raw = candidate.strip()
        c_low = c_raw.lower()
        c_alphanumeric = re.sub(r'[^a-zA-Z0-9]', '', c_low)

        # 1. Cek kecocokan nomor ID jika kedua key memiliki nomor ID utama (misal 'No 10')
        c_id_match = re.search(r'(?:no|#|id)?\s*(\d+)', c_low)
        c_id = c_id_match.group(1) if c_id_match else None

        best_match = None
        best_ratio = 0.0

        for t in targets:
            t_raw = t.strip()
            t_low = t_raw.lower()
            if t_low == c_low:
                return t

            t_alphanumeric = re.sub(r'[^a-zA-Z0-9]', '', t_low)
            if c_alphanumeric and t_alphanumeric and c_alphanumeric == t_alphanumeric:
                return t

            # Jika kedua key memuat nomor ID sama dan sisa teks sangat mirip
            if c_id:
                t_id_match = re.search(r'(?:no|#|id)?\s*(\d+)', t_low)
                t_id = t_id_match.group(1) if t_id_match else None
                if t_id and t_id == c_id:
                    # Nomor sama, cek similarity sisa teks
                    ratio = difflib.SequenceMatcher(None, c_low, t_low).ratio()
                    if ratio >= 0.70:
                        return t

            ratio = difflib.SequenceMatcher(None, c_low, t_low).ratio()
            if ratio > best_ratio and ratio >= threshold:
                best_ratio = ratio
                best_match = t

        return best_match

    @classmethod
    def compute_diff(
        cls,
        old_text: str,
        new_text: str,
        asset_type: str = "auto",
        asset_title: str = "Aset Dokumen"
    ) -> AssetDelta:
        """
        Membandingkan teks lama (old_text) dengan teks baru (new_text) secara algoritmik.
        """
        old_clean = (old_text or "").strip()
        new_clean = (new_text or "").strip()

        # Kasus 1: Teks 100% identik
        if old_clean == new_clean:
            return AssetDelta(
                has_changes=False,
                summary_text=(
                    f"[SISTEM: AUDIT PERUBAHAN ASET (TEMPORAL DIFF)]:\n"
                    f"Aset: \"{asset_title}\"\n"
                    f"Status: TIDAK ADA PERUBAHAN\n"
                    f"Catatan: Data aset ini 100% identik dengan kondisi saat dibaca sebelumnya di sesi ini. "
                    f"Belum ada penambahan baris, poin baru, atau revisi status apa pun."
                ),
                change_type="identical",
                metrics={"old_chars": len(old_clean), "new_chars": len(new_clean)}
            )

        # Kasus 2: Deteksi format tabel
        is_old_table, old_headers, old_rows = cls._extract_table_data(old_clean)
        is_new_table, new_headers, new_rows = cls._extract_table_data(new_clean)

        if (is_old_table or is_new_table) and (old_rows or new_rows):
            return cls._diff_tabular(
                old_headers=old_headers or new_headers,
                old_rows=old_rows,
                new_headers=new_headers or old_headers,
                new_rows=new_rows,
                asset_title=asset_title,
                old_len=len(old_clean),
                new_len=len(new_clean)
            )

        # Kasus 3: Dokumen teks / kode / regulasi
        return cls._diff_text_blocks(
            old_text=old_clean,
            new_text=new_clean,
            asset_title=asset_title
        )

    @classmethod
    def _extract_table_data(cls, text: str) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
        """
        Mengekstrak baris data tabel dari markdown table atau delimited text (CSV/TSV).
        """
        if not text:
            return False, [], []

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        # 1. Coba deteksi Markdown table (| ... |)
        table_lines = [l for l in lines if l.startswith("|") and l.endswith("|")]
        if len(table_lines) >= 2:
            raw_headers = [c.strip() for c in table_lines[0].split("|")[1:-1]]
            headers = [c for c in raw_headers if c and not re.match(r"^:?-+:?$", c)]
            
            data_rows = []
            for line in table_lines[1:]:
                # Abaikan separator line (|---|---|)
                if re.match(r"^\|(?:\s*:?-+:?\s*\|)+$", line):
                    continue
                parts = [c.strip() for c in line.split("|")[1:-1]]
                if not any(parts):
                    continue
                
                # Cari primary key untuk row ini
                row_key = cls._resolve_row_key(headers, parts)
                data_rows.append({
                    "key": row_key,
                    "cells": parts,
                    "raw": line
                })
            return True, headers, data_rows

        # 2. Coba deteksi CSV / TSV sederhana jika baris berulang dengan delimiter sama
        for delim in ["\t", ","]:
            sample = lines[:5]
            if len(sample) >= 2 and all(delim in l for l in sample):
                headers = [p.strip().strip('"') for p in lines[0].split(delim)]
                if len(headers) >= 2:
                    data_rows = []
                    for line in lines[1:]:
                        parts = [p.strip().strip('"') for p in line.split(delim)]
                        if not any(parts):
                            continue
                        row_key = cls._resolve_row_key(headers, parts)
                        data_rows.append({
                            "key": row_key,
                            "cells": parts,
                            "raw": line
                        })
                    return True, headers, data_rows

        return False, [], []

    @classmethod
    def _resolve_row_key(cls, headers: List[str], cells: List[str]) -> str:
        """
        Menentukan kunci unik (key) untuk baris data.
        Prioritas: Kolom bernama 'no', 'id', '#', 'nomor', 'kode', atau angka pada kolom pertama.
        """
        if not cells:
            return ""

        # Cek kolom No/ID berdasarkan header
        for idx, h in enumerate(headers[:4]):
            h_lower = h.lower()
            if any(k == h_lower or h_lower.startswith(k) for k in ["no", "id", "#", "nomor", "kode", "key"]):
                if idx < len(cells) and cells[idx]:
                    return f"No {cells[idx]}" if not cells[idx].lower().startswith("no") else cells[idx]

        # Cek apakah sel pertama adalah digit murni (1, 2, 20)
        first_clean = cells[0].strip()
        if first_clean.isdigit():
            return f"No {first_clean}"

        # Fallback ke gabungan 2 kolom pertama
        non_empty = [c for c in cells[:2] if c]
        return " - ".join(non_empty) if non_empty else cells[0]

    @classmethod
    def _diff_tabular(
        cls,
        old_headers: List[str],
        old_rows: List[Dict[str, Any]],
        new_headers: List[str],
        new_rows: List[Dict[str, Any]],
        asset_title: str,
        old_len: int,
        new_len: int
    ) -> AssetDelta:
        """
        Membandingkan dua tabel baris-demi-baris dengan identifikasi key dan fuzzy matching.
        """
        old_map: Dict[str, Dict[str, Any]] = {}
        for r in old_rows:
            k = r["key"]
            if k:
                old_map[k] = r

        new_map: Dict[str, Dict[str, Any]] = {}
        for r in new_rows:
            k = r["key"]
            if k:
                new_map[k] = r

        # 1. Exact matching
        unmatched_new = []
        common_pairs: List[Tuple[str, str]] = []  # (old_key, new_key)
        matched_old_keys = set()

        for k_new in new_map:
            if k_new in old_map:
                common_pairs.append((k_new, k_new))
                matched_old_keys.add(k_new)
            else:
                unmatched_new.append(k_new)

        # 2. Fuzzy matching untuk unmatched keys (toleransi OCR noise / formatting ~82%)
        remaining_old_keys = [k for k in old_map if k not in matched_old_keys]
        added_keys = []

        for k_new in unmatched_new:
            fuzzy_target = cls._fuzzy_match_key(k_new, remaining_old_keys, threshold=0.82)
            if fuzzy_target:
                common_pairs.append((fuzzy_target, k_new))
                matched_old_keys.add(fuzzy_target)
                if fuzzy_target in remaining_old_keys:
                    remaining_old_keys.remove(fuzzy_target)
            else:
                added_keys.append(k_new)

        removed_keys = [k for k in old_map if k not in matched_old_keys]

        added_items = []
        for k in added_keys:
            r = new_map[k]
            cell_desc = cls._format_row_cells(new_headers, r["cells"])
            added_items.append(f"Baris/Poin [{k}]: {cell_desc}")

        removed_items = []
        for k in removed_keys:
            r = old_map[k]
            cell_desc = cls._format_row_cells(old_headers, r["cells"])
            removed_items.append(f"Baris/Poin [{k}]: {cell_desc}")

        modified_items = []
        for old_k, new_k in common_pairs:
            old_r = old_map[old_k]
            new_r = new_map[new_k]
            diff_cols = cls._find_diff_columns_semantic(
                old_headers=old_headers,
                new_headers=new_headers,
                old_cells=old_r["cells"],
                new_cells=new_r["cells"]
            )
            if diff_cols:
                diff_str = "; ".join(diff_cols)
                display_k = new_k if new_k == old_k else f"{new_k} (eks '{old_k}')"
                modified_items.append(f"Baris/Poin [{display_k}]: {diff_str}")

        has_changes = bool(added_items or modified_items or removed_items)

        # Susun summary text
        summary_lines = [
            f"[SISTEM: AUDIT PERUBAHAN ASET (TEMPORAL DIFF)]:",
            f"Aset: \"{asset_title}\"",
        ]

        if not has_changes:
            summary_lines.append("Status: TIDAK ADA PERUBAHAN")
            summary_lines.append(f"Catatan: Isi tabel ({len(new_rows)} baris) 100% konsisten dengan data sebelumnya di sesi ini.")
        else:
            summary_lines.append("Status: TERDETEKSI PERUBAHAN BARU DARI PEMBACAAN SEBELUMNYA")
            summary_lines.append(f"Kondisi: Sebelumnya {len(old_rows)} baris data → Sekarang {len(new_rows)} baris data.\n")

            if added_items:
                summary_lines.append("• ➕ ITEM / BARIS BARU DITAMBAHKAN:")
                for item in added_items[:15]:
                    summary_lines.append(f"  - {item}")
                if len(added_items) > 15:
                    summary_lines.append(f"  - ... dan {len(added_items) - 15} baris baru lainnya.")
                summary_lines.append("")

            if modified_items:
                summary_lines.append("• 🔄 ITEM DENGAN PERUBAHAN NILAI / STATUS:")
                for item in modified_items[:15]:
                    summary_lines.append(f"  - {item}")
                if len(modified_items) > 15:
                    summary_lines.append(f"  - ... dan {len(modified_items) - 15} baris terevisi lainnya.")
                summary_lines.append("")

            if removed_items:
                summary_lines.append("• ➖ ITEM YANG DIHAPUS:")
                for item in removed_items[:10]:
                    summary_lines.append(f"  - {item}")
                if len(removed_items) > 10:
                    summary_lines.append(f"  - ... dan {len(removed_items) - 10} baris dihapus lainnya.")
                summary_lines.append("")

            summary_lines.extend([
                "⚠️ PANDUAN SEMANTIK UNTUK RESPON AI (MUTLAK):",
                "1. Pahami bahwa penambahan baris/poin/item baru (seperti yang tercantum di atas) ADALAH PERUBAHAN / UPDATE NYATA.",
                "2. DILARANG KERAS menyimpulkan 'belum ada update' hanya karena kolom status pada baris baru tersebut bertuliskan 'Not Started', 'Draft', atau 'Open'! Baris itu sendiri adalah hal baru yang baru dimasukkan ke spreadsheet/dokumen.",
                "3. Sampaikan secara proaktif, antusias, dan jelas kepada pengguna mengenai poin/baris baru atau revisi status yang terdeteksi di atas."
            ])

        return AssetDelta(
            has_changes=has_changes,
            added_items=added_items,
            modified_items=modified_items,
            removed_items=removed_items,
            summary_text="\n".join(summary_lines),
            change_type="table",
            metrics={
                "old_rows_count": len(old_rows),
                "new_rows_count": len(new_rows),
                "added_count": len(added_items),
                "modified_count": len(modified_items),
                "removed_count": len(removed_items)
            }
        )

    @classmethod
    def _format_row_cells(cls, headers: List[str], cells: List[str]) -> str:
        """
        Membuat deskripsi teks yang rapi untuk satu baris.
        """
        parts = []
        for idx, val in enumerate(cells):
            if not val:
                continue
            h_name = headers[idx] if idx < len(headers) else f"Kolom {idx+1}"
            # Abaikan jika header hanya 'no' atau '#' karena key sudah membawanya
            if h_name.lower() in ["no", "id", "#", "nomor"]:
                continue
            parts.append(f"{h_name}: '{val}'")
            if len(parts) >= 4:
                break
        return " | ".join(parts) if parts else " | ".join(cells[:3])

    @classmethod
    def _find_diff_columns_semantic(
        cls,
        old_headers: List[str],
        new_headers: List[str],
        old_cells: List[str],
        new_cells: List[str]
    ) -> List[str]:
        """
        Mendeteksi perubahan nilai sel dengan memetakan kolom secara semantik
        (misal 'Kondisi' ekuivalen dengan 'Status', 'Penanggung Jawab' dengan 'PIC').
        """
        diffs = []
        old_norm_map: Dict[str, Tuple[str, str]] = {}
        for idx, h in enumerate(old_headers):
            val = old_cells[idx] if idx < len(old_cells) else ""
            norm = cls._normalize_header(h)
            old_norm_map[norm] = (h, val)

        new_norm_map: Dict[str, Tuple[str, str]] = {}
        for idx, h in enumerate(new_headers):
            val = new_cells[idx] if idx < len(new_cells) else ""
            norm = cls._normalize_header(h)
            new_norm_map[norm] = (h, val)

        semantic_overlap = set(old_norm_map.keys()) & set(new_norm_map.keys()) - {"id"}
        if len(semantic_overlap) >= 1:
            for norm_key in semantic_overlap:
                old_h, old_val = old_norm_map[norm_key]
                new_h, new_val = new_norm_map[norm_key]
                if old_val != new_val:
                    col_label = new_h if new_h.lower() == old_h.lower() else f"{new_h} / {old_h}"
                    diffs.append(f"{col_label} berubah dari '{old_val}' → '{new_val}'")
            return diffs

        # Fallback ke pencocokan indeks posisi standar
        return cls._find_diff_columns(new_headers, old_cells, new_cells)

    @classmethod
    def _find_diff_columns(
        cls,
        headers: List[str],
        old_cells: List[str],
        new_cells: List[str]
    ) -> List[str]:
        """
        Mendeteksi kolom spesifik yang nilainya berbeda antara old dan new cells berdasarkan posisi indeks.
        """
        diffs = []
        max_len = max(len(old_cells), len(new_cells))
        for idx in range(max_len):
            old_val = old_cells[idx] if idx < len(old_cells) else ""
            new_val = new_cells[idx] if idx < len(new_cells) else ""
            if old_val != new_val:
                h_name = headers[idx] if idx < len(headers) else f"Kolom {idx+1}"
                diffs.append(f"{h_name} berubah dari '{old_val}' → '{new_val}'")
        return diffs

    @classmethod
    def _diff_text_blocks(
        cls,
        old_text: str,
        new_text: str,
        asset_title: str
    ) -> AssetDelta:
        """
        Diffing cerdas berbasis paragraf/baris untuk dokumen bebas, markdown, atau regulasi.
        """
        old_lines = [l.strip() for l in old_text.splitlines() if l.strip()]
        new_lines = [l.strip() for l in new_text.splitlines() if l.strip()]

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        added_items = []
        removed_items = []
        modified_items = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'insert':
                for l in new_lines[j1:j2]:
                    if len(l) > 3:
                        added_items.append(l[:160] + ("..." if len(l) > 160 else ""))
            elif tag == 'delete':
                for l in old_lines[i1:i2]:
                    if len(l) > 3:
                        removed_items.append(l[:160] + ("..." if len(l) > 160 else ""))
            elif tag == 'replace':
                old_chunk = " ".join(old_lines[i1:i2])[:100]
                new_chunk = " ".join(new_lines[j1:j2])[:100]
                modified_items.append(f"'{old_chunk}' → '{new_chunk}'")

        has_changes = bool(added_items or modified_items or removed_items)

        summary_lines = [
            f"[SISTEM: AUDIT PERUBAHAN ASET (TEMPORAL DIFF)]:",
            f"Aset: \"{asset_title}\"",
        ]

        if not has_changes:
            summary_lines.append("Status: TIDAK ADA PERUBAHAN")
            summary_lines.append("Catatan: Isi dokumen identik dengan kondisi saat dibaca sebelumnya.")
        else:
            summary_lines.append("Status: TERDETEKSI PERUBAHAN TEKS DARI PEMBACAAN SEBELUMNYA\n")
            if added_items:
                summary_lines.append("• ➕ BAGIAN / TEKS BARU YANG DISISIPKAN:")
                for it in added_items[:8]:
                    summary_lines.append(f"  - {it}")
                if len(added_items) > 8:
                    summary_lines.append(f"  - ... dan {len(added_items) - 8} baris tambahan lainnya.")
                summary_lines.append("")

            if modified_items:
                summary_lines.append("• 🔄 BAGIAN YANG DIREVISI / DIUBAH:")
                for it in modified_items[:8]:
                    summary_lines.append(f"  - {it}")
                summary_lines.append("")

            if removed_items:
                summary_lines.append("• ➖ BAGIAN YANG DIHAPUS:")
                for it in removed_items[:5]:
                    summary_lines.append(f"  - {it}")
                summary_lines.append("")

            summary_lines.extend([
                "⚠️ PANDUAN SEMANTIK UNTUK RESPON AI (MUTLAK):",
                "1. Terangkan penambahan atau revisi teks di atas secara faktual kepada pengguna.",
                "2. Jika ada bab/pasal/poin baru, jelaskan keberadaan poin baru tersebut."
            ])

        return AssetDelta(
            has_changes=has_changes,
            added_items=added_items,
            modified_items=modified_items,
            removed_items=removed_items,
            summary_text="\n".join(summary_lines),
            change_type="text",
            metrics={
                "old_chars": len(old_text),
                "new_chars": len(new_text),
                "added_blocks": len(added_items),
                "modified_blocks": len(modified_items),
                "removed_blocks": len(removed_items)
            }
        )

    @classmethod
    def compute_cross_asset_diff(
        cls,
        asset_a: Dict[str, Any],
        asset_b: Dict[str, Any]
    ) -> AssetDelta:
        """
        Menghitung perbandingan lintas aset (Cross-Modal / Multi-Asset Diff).
        Misal: Foto/OCR Formulir (Asset A) vs Google Sheets (Asset B), atau Dokumen V1 vs V2.
        """
        title_a = asset_a.get("title") or asset_a.get("source") or asset_a.get("metadata", {}).get("title") or "Aset A (Baseline)"
        title_b = asset_b.get("title") or asset_b.get("source") or asset_b.get("metadata", {}).get("title") or "Aset B (Pembanding)"
        
        type_a = asset_a.get("type") or asset_a.get("metadata", {}).get("type", "dokumen")
        type_b = asset_b.get("type") or asset_b.get("metadata", {}).get("type", "dokumen")

        text_a = asset_a.get("content") or asset_a.get("text") or ""
        text_b = asset_b.get("content") or asset_b.get("text") or ""

        delta = cls.compute_diff(
            old_text=text_a,
            new_text=text_b,
            asset_title=f"{title_a} vs {title_b}"
        )

        cross_summary_lines = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "⚖️ [SISTEM: AUDIT KOMPARASI LINTAS ASET (CROSS-MODAL / MULTI-ASSET DIFF)]",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"• Aset A (Baseline / Acuan): \"{title_a}\" [Tipe: {type_a.upper()}]",
            f"• Aset B (Pembanding / Baru): \"{title_b}\" [Tipe: {type_b.upper()}]",
        ]

        if not delta.has_changes:
            cross_summary_lines.append("• Status Komparasi: KEDUA ASET KONSISTEN (TIDAK ADA PERBEDAAN SIGNIFIKAN)")
            cross_summary_lines.append("  Seluruh baris/data yang terdaftar di Aset A tercocokkan dengan konsisten di Aset B.")
        else:
            cross_summary_lines.append("• Status Komparasi: DITEMUKAN SELISIH / PERBEDAAN ANTARA KEDUA ASET\n")
            if delta.added_items:
                cross_summary_lines.append(f"• ➕ ITEM YANG HANYA ADA DI ASET B (\"{title_b}\"):")
                for it in delta.added_items[:12]:
                    cross_summary_lines.append(f"  - {it}")
                if len(delta.added_items) > 12:
                    cross_summary_lines.append(f"  - ... dan {len(delta.added_items) - 12} item lainnya.")
                cross_summary_lines.append("")

            if delta.modified_items:
                cross_summary_lines.append("• 🔄 ITEM DENGAN NILAI / STATUS BERBEDA ANTARA ASET A & B:")
                for it in delta.modified_items[:12]:
                    cross_summary_lines.append(f"  - {it}")
                if len(delta.modified_items) > 12:
                    cross_summary_lines.append(f"  - ... dan {len(delta.modified_items) - 12} item terevisi lainnya.")
                cross_summary_lines.append("")

            if delta.removed_items:
                cross_summary_lines.append(f"• ➖ ITEM YANG HANYA ADA DI ASET A (Tidak Ditemukan di Aset B):")
                for it in delta.removed_items[:8]:
                    cross_summary_lines.append(f"  - {it}")
                if len(delta.removed_items) > 8:
                    cross_summary_lines.append(f"  - ... dan {len(delta.removed_items) - 8} item lainnya.")
                cross_summary_lines.append("")

            cross_summary_lines.extend([
                "⚠️ PANDUAN UNTUK RESPON AI (MUTLAK):",
                "1. Terangkan selisih antara kedua berkas di atas secara objektif dan sistematis.",
                "2. Jika pengguna menanyakan sinkronisasi atau kelengkapan, sebutkan secara tegas item mana yang sudah sesuai dan mana yang berselisih.",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ])

        delta.summary_text = "\n".join(cross_summary_lines)
        return delta


asset_diff_engine = UniversalAssetDiffEngine()
