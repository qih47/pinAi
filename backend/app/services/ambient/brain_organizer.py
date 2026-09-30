import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("CAKRA_BRAIN_ORGANIZER")


class BrainAssetOrganizer:
    """
    Session Brain Asset Organizer.
    Bertanggung jawab untuk:
    1. Memprofil aset (spreadsheet, web, dokumen, image) yang masuk ke session memory.
    2. Menyusun katalog aset ringkas (~40-80 token) untuk diinjeksikan ke Call 1 Router.
    3. Mengambil konten penuh (targeted retrieval) aset yang relevan ke Call 2 untuk mencegah OOM dan halusinasi.
    """

    @staticmethod
    def profile_asset(
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        asset_type: str = "auto"
    ) -> Dict[str, Any]:
        """
        Membuat profil struktural kaya dari konten aset.
        Mendeteksi tabel spreadsheet (markdown, CSV, TSV), dokumen, halaman web, dan gambar.
        """
        meta = dict(metadata or {})
        content = content or ""
        clean_content = content.strip()

        detected_type = asset_type
        title = meta.get("title") or meta.get("source") or "Aset Tanpa Judul"
        urls = meta.get("urls") or ([meta["url"]] if "url" in meta else [])
        primary_url = urls[0] if urls else ""

        # Deteksi tipe dari URL atau metadata
        if primary_url:
            p_lower = primary_url.lower()
            if "docs.google.com/spreadsheets" in p_lower or any(p_lower.endswith(ext) for ext in [".xlsx", ".xls", ".csv", ".tsv"]):
                detected_type = "spreadsheet"
            elif any(p_lower.endswith(ext) for ext in [".pdf", ".docx", ".doc", ".pptx"]):
                detected_type = "document"

        # Deteksi struktur spreadsheet / tabel di dalam konten
        is_table = False
        columns: List[str] = []
        row_count = 0
        status_samples: List[str] = []

        lines = [line.strip() for line in clean_content.split("\n") if line.strip()]
        
        # Periksa apakah format markdown table (| ... | ... |)
        table_lines = [l for l in lines if l.startswith("|") and l.endswith("|")]
        if len(table_lines) >= 2:
            is_table = True
            header_line = table_lines[0]
            raw_cols = [c.strip() for c in header_line.split("|")[1:-1]]
            columns = [c for c in raw_cols if c and not re.match(r"^:?-+:?$", c)]
            
            # Hitung data rows (abaikan divider `|---|---|`)
            data_rows = [l for l in table_lines[1:] if not re.match(r"^\|(?:\s*:?-+:?\s*\|)+$", l)]
            row_count = len(data_rows)

            # Cari sampel status jika ada kolom bernama status/kondisi
            status_col_idx = -1
            for idx, col in enumerate(columns):
                if any(k in col.lower() for k in ["status", "kondisi", "state", "progress", "hasil"]):
                    status_col_idx = idx
                    break
            if status_col_idx >= 0:
                statuses = set()
                for row in data_rows:
                    parts = [p.strip() for p in row.split("|")[1:-1]]
                    if len(parts) > status_col_idx:
                        val = parts[status_col_idx]
                        if val:
                            statuses.add(val)
                status_samples = list(statuses)[:5]

        # Periksa format CSV/TSV jika belum terdeteksi tabel
        elif not is_table and (detected_type == "spreadsheet" or (lines and ("," in lines[0] or "\t" in lines[0]))):
            delim = "\t" if "\t" in lines[0] else ","
            parts = [p.strip().strip('"') for p in lines[0].split(delim)]
            if len(parts) >= 2 and all(len(p) < 40 for p in parts):
                is_table = True
                columns = parts
                row_count = len(lines) - 1

        if is_table:
            detected_type = "spreadsheet"

        if detected_type == "auto":
            if meta.get("type"):
                detected_type = meta["type"]
            elif urls:
                detected_type = "web_page"
            else:
                detected_type = "document"

        # Susun Ringkasan Profil (Compact Scope Summary)
        if detected_type == "spreadsheet" and is_table:
            cols_str = ", ".join(columns[:6]) + ("..." if len(columns) > 6 else "")
            summary = f"Tabel spreadsheet berisikan {row_count} baris data. Kolom: [{cols_str}]."
            if status_samples:
                summary += f" Nilai status terdeteksi: [{', '.join(status_samples)}]."
        elif detected_type == "web_page":
            first_text = " ".join(clean_content.replace("==== ISI WEB:", "").split())[:180]
            summary = f"Konten web dari {primary_url or title}: {first_text}..."
        else:
            first_text = " ".join(clean_content.split())[:180]
            summary = f"Dokumen {title}: {first_text}..."

        profile = {
            "type": detected_type,
            "title": title,
            "urls": urls,
            "summary": summary,
            "columns": columns,
            "row_count": row_count,
            "is_tabular": is_table,
            "char_count": len(clean_content),
        }
        # Pertahankan metadata kustom yang sudah ada
        for k, v in meta.items():
            if k not in profile:
                profile[k] = v

        return profile

    @staticmethod
    def format_catalog_for_router(chunks_with_meta: List[Dict[str, Any]]) -> str:
        """
        Menghasilkan katalog ringkas untuk Call 1 Router.
        Menghabiskan token sangat sedikit (~30-60 token) tapi memberikan informasi lengkap:
        ID, Tipe, Judul, Kolom, Jumlah baris, dan URL.
        """
        if not chunks_with_meta:
            return ""

        catalog_lines = [
            "[SESSION BRAIN ASSETS (DATA / DOKUMEN / URL YANG PERNAH DIBUKA DI SESI INI)]:"
        ]
        for c in chunks_with_meta:
            chunk_id = c.get("id")
            meta = c.get("metadata", {})
            a_type = meta.get("type") or "file"
            title = meta.get("title") or meta.get("source") or f"Aset #{chunk_id}"
            urls = meta.get("urls") or ([meta["url"]] if "url" in meta else [])
            primary_url = urls[0] if urls else ""

            details = []
            if meta.get("is_tabular") or a_type == "spreadsheet":
                cols = meta.get("columns", [])
                if cols:
                    details.append(f"Kolom: [{', '.join(cols[:5])}{'...' if len(cols) > 5 else ''}]")
                rc = meta.get("row_count")
                if rc:
                    details.append(f"{rc} baris data")
            elif meta.get("summary"):
                details.append(meta["summary"][:120])

            if primary_url:
                details.append(f"URL: {primary_url}")

            detail_str = " | ".join(details)
            catalog_lines.append(f"• ID #{chunk_id} [{a_type.upper()}]: \"{title}\" — {detail_str}")

        return "\n".join(catalog_lines)

    @classmethod
    def resolve_targeted_assets(
        cls,
        chunks_with_meta: List[Dict[str, Any]],
        target_ids: Optional[List[int]] = None,
        user_message: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Memilih aset mana yang harus diambil isinya secara penuh.
        Prinsip Percabangan Aman (Non-Destructive Safe Branching):
        - Jika target_ids eksplisit diberikan oleh Router: Ambil ID tersebut.
        - Jika target_ids kosong, namun hanya ada 1 aset di sesi dan pesan pengguna menanyakan data/tabel/ceklis/isi:
          Fallback otomatis memilih aset tersebut agar Call 2 tidak berhalusinasi.
        """
        if not chunks_with_meta:
            return []

        # JALUR A1: Router secara spesifik menunjuk ID aset
        if target_ids:
            target_set = {int(tid) for tid in target_ids if str(tid).isdigit()}
            selected = [c for c in chunks_with_meta if c.get("id") in target_set]
            if selected:
                logger.info(f"[BRAIN_ORGANIZER] 🎯 Router targeted {len(selected)} asset(s): {target_set}")
                return selected

        # JALUR B1: Fallback Cerdas (Universal Smart Fallback)
        # Jika hanya ada 1 aset di sesi, dan user meminta data faktual, otomatis ambil aset tersebut.
        u_lower = (user_message or "").lower()
        factual_intent_markers = [
            "ceklis", "form", "revisi", "tabel", "spreadsheet", "sheet", "baris", 
            "kolom", "data", "status", "belum", "done", "selesai", "rekap", "daftar", 
            "isi", "link", "url", "dokumen", "file", "kemarin", "tadi", "kenapa cuma",
            "berapa", "siapa", "pic"
        ]
        has_factual_query = any(marker in u_lower for marker in factual_intent_markers)

        if len(chunks_with_meta) == 1 and has_factual_query:
            logger.info(f"[BRAIN_ORGANIZER] 🛡️ Smart Fallback: Single asset #{chunks_with_meta[0].get('id')} selected for factual query '{user_message[:50]}'")
            return [chunks_with_meta[0]]

        # Jika ada beberapa aset, periksa kecocokan kata kunci pada judul / kolom / URL
        matched = []
        for c in chunks_with_meta:
            meta = c.get("metadata", {})
            title = (meta.get("title") or "").lower()
            urls = [u.lower() for u in meta.get("urls", [])]
            cols = [col.lower() for col in meta.get("columns", [])]
            
            if (title and title in u_lower) or any(u in u_lower for u in urls if len(u) > 10) or any(col in u_lower for col in cols if len(col) > 3):
                matched.append(c)

        if matched:
            logger.info(f"[BRAIN_ORGANIZER] 🛡️ Keyword matched {len(matched)} asset(s) from user message")
            return matched

        return []

    @staticmethod
    def _strip_version_suffix(name: str) -> str:
        """
        Menghilangkan penanda versi/revisi/temporal dari nama file agar
        file revisi (misal: 'laporan_v2.xlsx') dapat dicocokkan dengan file versi sebelumnya ('laporan_v1.xlsx').
        """
        if not name:
            return ""
        clean = name.strip().lower()
        if "." in clean:
            stem, ext = clean.rsplit(".", 1)
            ext = f".{ext}"
        else:
            stem = clean
            ext = ""

        patterns = [
            r'[\s_(-]+(?:revisi|rev|v)?\s*\d+(?:\.\d+)?[\s_)-]*$',
            r'[\s_(-]+(?:revisi|rev|version)[\s_)-]*$',
            r'[\s_(-]+(?:lama|baru|old|new|draft|final)[\s_)-]*$',
        ]
        for pat in patterns:
            stem = re.sub(pat, '', stem, flags=re.IGNORECASE).strip()

        stem = stem.rstrip("_- .()")
        return stem + ext

    @classmethod
    def resolve_cross_comparison_assets(
        cls,
        chunks_with_meta: List[Dict[str, Any]],
        target_ids: Optional[List[int]] = None,
        user_message: str = ""
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Menentukan pasangan dua aset (Aset A dan Aset B) untuk komparasi lintas format / multi-aset.
        
        Skenario yang didukung:
        1. Router secara eksplisit memberikan 2 ID di target_ids ([id_a, id_b]).
        2. Pengguna meminta komparasi lintas modalitas (misal: spreadsheet vs foto/screenshot):
           Sistem secara otomatis mencari 1 aset tabular/spreadsheet dan 1 aset image/ocr.
        3. Pengguna meminta perbandingan dan ada tepat 2 aset di sesi:
           Sistem memasangkan kedua aset tersebut secara otomatis (Smart Pair Fallback).
        """
        if not chunks_with_meta or len(chunks_with_meta) < 2:
            return None

        # 1. Jalur Target IDs Eksplisit dari Router (2 ID atau lebih)
        if target_ids and len(target_ids) >= 2:
            id_a, id_b = int(target_ids[0]), int(target_ids[1])
            chunk_map = {c.get("id"): c for c in chunks_with_meta if c.get("id") is not None}
            if id_a in chunk_map and id_b in chunk_map:
                logger.info(f"[BRAIN_ORGANIZER] ⚖️ Explicit pair resolved: #{id_a} vs #{id_b}")
                return chunk_map[id_a], chunk_map[id_b]

        # 2. Periksa apakah pesan pengguna menunjukkan intensi komparasi
        u_lower = (user_message or "").lower()
        comparative_markers = [
            "bandingkan", "cocokkan", "sinkronkan", "crosscheck", "cross check",
            "cek silang", "apa bedanya", "perbedaan", "beda", "versus", "vs",
            "bandingin", "cocokin", "apakah sama", "selisih"
        ]
        is_comparative_intent = any(marker in u_lower for marker in comparative_markers)
        if not is_comparative_intent:
            return None

        # Skenario 2A: Foto/Gambar/OCR vs Spreadsheet/Tabel
        wants_image = any(k in u_lower for k in ["foto", "gambar", "screenshot", "scan", "ceklis", "kamera", "image"])
        wants_sheet = any(k in u_lower for k in ["spreadsheet", "sheet", "excel", "tabel", "url", "link", "google sheet"])

        if wants_image or wants_sheet:
            img_candidates = []
            sheet_candidates = []
            for c in chunks_with_meta:
                meta = c.get("metadata", {})
                a_type = (meta.get("type") or "").lower()
                source = (meta.get("source") or "").lower()
                if "image" in a_type or "ocr" in a_type or "image" in source or "attachment" in source:
                    img_candidates.append(c)
                elif a_type == "spreadsheet" or meta.get("is_tabular") or "sheet" in source or "url" in source:
                    sheet_candidates.append(c)

            if img_candidates and sheet_candidates:
                asset_img = img_candidates[-1]
                asset_sheet = sheet_candidates[-1]
                logger.info(f"[BRAIN_ORGANIZER] ⚖️ Cross-Modal resolved: Image #{asset_img.get('id')} vs Sheet #{asset_sheet.get('id')}")
                return asset_img, asset_sheet

        # Skenario 2B: Tepat 2 aset di sesi dan user ingin komparasi
        if len(chunks_with_meta) == 2:
            logger.info(f"[BRAIN_ORGANIZER] ⚖️ Exact 2-asset pair resolved: #{chunks_with_meta[0].get('id')} vs #{chunks_with_meta[1].get('id')}")
            return chunks_with_meta[0], chunks_with_meta[1]

        # Skenario 2C: Ambil dua aset paling baru di sesi
        if len(chunks_with_meta) >= 2:
            logger.info(f"[BRAIN_ORGANIZER] ⚖️ 2 latest assets resolved: #{chunks_with_meta[-2].get('id')} vs #{chunks_with_meta[-1].get('id')}")
            return chunks_with_meta[-2], chunks_with_meta[-1]

        return None

    @classmethod
    def find_matching_chunk_in_list(
        cls,
        chunks: List[Dict[str, Any]],
        urls: Optional[List[str]] = None,
        title: Optional[str] = None,
        file_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Mencari chunk paling baru dari daftar in-memory chunks yang cocok dengan URL, judul, atau file_id.
        Mendukung deteksi perubahan versi (diffing) bertahap tanpa query DB.
        """
        if not chunks:
            return None

        clean_urls = set()
        if urls:
            for u in urls:
                u_str = str(u).strip().rstrip("/")
                if u_str:
                    clean_urls.add(u_str)
                    clean_urls.add(re.sub(r"^https?://", "", u_str))

        rev_chunks = list(reversed(chunks))

        for c in rev_chunks:
            if file_id is not None and c.get("file_id") == file_id:
                return c

            meta = c.get("metadata", {})
            c_urls = list(meta.get("urls", []))
            if "url" in meta:
                c_urls.append(meta["url"])

            for cu in c_urls:
                cu_str = str(cu).strip().rstrip("/")
                if not cu_str:
                    continue
                cu_no_proto = re.sub(r"^https?://", "", cu_str)
                if cu_str in clean_urls or cu_no_proto in clean_urls:
                    return c

        if title:
            clean_title = title.strip().lower()
            norm_title = cls._strip_version_suffix(clean_title)

            # Pass 1: exact match
            for c in rev_chunks:
                meta = c.get("metadata", {})
                t = (meta.get("title") or "").strip().lower()
                if t and t == clean_title:
                    return c

            # Pass 2: version normalized match
            if norm_title:
                for c in rev_chunks:
                    meta = c.get("metadata", {})
                    t = (meta.get("title") or "").strip().lower()
                    if t and cls._strip_version_suffix(t) == norm_title:
                        return c

        return None

    @classmethod
    def format_asset_content_for_call2(
        cls,
        targeted_chunks: List[Dict[str, Any]],
        cross_delta_summary: Optional[str] = None
    ) -> str:
        """
        Menyusun teks konteks resmi untuk Call 2 dari aset yang dipilih.
        Menyertakan peringatan mutlak agar Call 2 merujuk hanya pada data nyata di tabel,
        diff changelog temporal jika ada, dan audit komparasi lintas aset jika lebih dari satu aset dibandingkan.
        """
        if not targeted_chunks:
            return ""

        sections = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "🧠 SESSION BRAIN: DATA RUJUKAN FAKTUAL RESMI DARI ASSET SESI",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "⚠️ PERINGATAN MUTLAK CALL 2 (STRICT FACTUAL INTEGRITY):",
            "1. Teks dan tabel di bawah ini adalah data RIIL dan SATU-SATUNYA SUMBER KEBENARAN FAKTA di sesi ini.",
            "2. Gunakan HANYA baris, angka, nama, ID, kolom, dan status yang benar-benar tercantum di bawah.",
            "3. DILARANG KERAS MENGARANG atau BERHALUSINASI membuat nomor ID, bug palsu, nama palsu, atau jumlah palsu!",
            "4. Jika pengguna menanyakan baris atau status tertentu (contoh: yang belum dikerjakan / pending), teliti seluruh baris tabel di bawah secara presisi sebelum menjawab.",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        ]

        if cross_delta_summary:
            sections.append(f"{cross_delta_summary}\n")

        for c in targeted_chunks:
            chunk_id = c.get("id")
            meta = c.get("metadata", {})
            title = meta.get("title") or meta.get("source") or f"Aset #{chunk_id}"
            a_type = (meta.get("type") or "file").upper()
            content = c.get("content", "")

            sections.append(f"--- [ASSET #{chunk_id}] {a_type}: {title} ---")
            diff_sum = meta.get("diff_summary")
            if diff_sum:
                sections.append(f"{diff_sum}\n")
            sections.append(content)
            sections.append("\n" + "-" * 50 + "\n")

        return "\n".join(sections)


brain_asset_organizer = BrainAssetOrganizer()

