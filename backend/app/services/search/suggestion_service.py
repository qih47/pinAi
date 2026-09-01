import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("CAKRA_SUGGESTIONS")

# Default curated suggestions for Web Search and Code
DEFAULT_WEB_SUGGESTIONS = [
    {"title": "Perkembangan industri alutsista PT Pindad dan DEFEND ID", "category": "Pertahanan", "source": "web"},
    {"title": "Spesifikasi dan varian kendaraan taktis MV3 Garuda Limousine", "category": "Alutsista", "source": "web"},
    {"title": "Berita terkini pengadaan dan modernisasi persenjataan TNI", "category": "Berita", "source": "web"},
    {"title": "Regulasi ekspor produk industri pertahanan nasional", "category": "Regulasi", "source": "web"},
    {"title": "Inovasi munisi kaliber kecil dan teknologi munisi pintar", "category": "Teknologi", "source": "web"},
]

DEFAULT_CODE_SUGGESTIONS = [
    {"title": "Buatkan form login dengan autentikasi JWT dan React Tailwind", "category": "Frontend", "source": "code"},
    {"title": "Script Python untuk automasi parsing dan rekapitulasi data Excel", "category": "Python", "source": "code"},
    {"title": "Struktur boilerplate REST API FastAPI dengan async PostgreSQL", "category": "Backend", "source": "code"},
    {"title": "Komponen Dashboard analitik chart interaktif dengan Recharts", "category": "UI/UX", "source": "code"},
    {"title": "Script pengolahan data CSV dan visualisasi laporan performa", "category": "Data", "source": "code"},
]

# ── PUBLIC / GUEST PRESETS (Bebas dari SOP/HR/Dokumen Internal Perusahaan) ───
GUEST_DIAGRAM_SUGGESTIONS = [
    {"title": "Diagram alur proses kerja mesin 4-tak pada kendaraan taktis", "category": "Teknik Mesin", "source": "diagram"},
    {"title": "Flowchart algoritma pencarian biner (Binary Search) dan Sorting", "category": "Algoritma", "source": "diagram"},
    {"title": "Diagram arsitektur web client-server REST API modern", "category": "Arsitektur Web", "source": "diagram"},
    {"title": "Diagram siklus hidup pengembangan perangkat lunak (SDLC)", "category": "Software Eng", "source": "diagram"},
    {"title": "Diagram sistem transmisi dan suspensi kendaraan 4x4", "category": "Otomotif", "source": "diagram"},
]

GUEST_CHART_SUGGESTIONS = [
    {"title": "Visualisasikan perbandingan spesifikasi Maung MV3 vs Kendaraan Taktis 4x4", "category": "Komparasi", "source": "chart"},
    {"title": "Grafik perbandingan kecepatan dan efisiensi bahasa pemrograman", "category": "Benchmark", "source": "chart"},
    {"title": "Tabel perbandingan data kaliber munisi standar NATO dan jarak efektif", "category": "Spesifikasi", "source": "chart"},
    {"title": "Grafik tren perkembangan teknologi industri pertahanan global", "category": "Statistik", "source": "chart"},
    {"title": "Visualisasi data spesifikasi varian kendaraan taktis Pindad (Bar Chart)", "category": "Alutsista", "source": "chart"},
]

# ── INTERNAL / EMPLOYEE PRESETS (Khusus Pegawai Login) ───
EMPLOYEE_DIAGRAM_SUGGESTIONS = [
    {"title": "Gambarkan diagram alur proses pengadaan barang & jasa sesuai SOP", "category": "Flowchart SOP", "source": "diagram"},
    {"title": "Buatkan flowchart proses persetujuan cuti dan izin kerja pegawai", "category": "Proses Bisnis HR", "source": "diagram"},
    {"title": "Diagram arsitektur microservice REST API Cakra AI dan backend FastAPI", "category": "Arsitektur", "source": "diagram"},
    {"title": "Diagram alur tahapan perakitan kendaraan taktis Maung MV3", "category": "Manufaktur", "source": "diagram"},
    {"title": "Sequence diagram alur autentikasi Single Sign-On (SSO) internal", "category": "IT & Keamanan", "source": "diagram"},
]

EMPLOYEE_CHART_SUGGESTIONS = [
    {"title": "Visualisasikan perbandingan spesifikasi Maung MV3 vs Kendaraan Taktis 4x4", "category": "Komparasi", "source": "chart"},
    {"title": "Buatkan grafik tren anggaran riset alutsista dalam format Bar Chart", "category": "Anggaran Riset", "source": "chart"},
    {"title": "Tabel perbandingan data kaliber munisi dan daya jangkau efektif", "category": "Produksi Munisi", "source": "chart"},
    {"title": "Grafik proporsi distribusi alokasi produk DEFEND ID (Pie Chart)", "category": "DEFEND ID", "source": "chart"},
    {"title": "Line chart simulasi peningkatan kapasitas produksi senjata 2024-2026", "category": "Perencanaan", "source": "chart"},
]

DEFAULT_CREATE_FILE_SUGGESTIONS = [
    {"title": "Buatkan format rekap inventaris senjata dalam format Excel (.xlsx)", "category": "Excel", "source": "file"},
    {"title": "Generate draft laporan pertanggungjawaban kegiatan (.docx)", "category": "Word", "source": "file"},
    {"title": "Template dokumen berita acara serah terima barang (.docx)", "category": "Dokumen", "source": "file"},
    {"title": "Format tabel evaluasi kinerja vendor pengadaan (.xlsx)", "category": "Excel", "source": "file"},
    {"title": "Draft lembar persetujuan anggaran proyek riset alutsista (.docx)", "category": "Template", "source": "file"},
]

DEFAULT_SMART_MAIL_SUGGESTIONS = [
    {"title": "Buatkan draft Nota Dinas pengajuan pengadaan perangkat ke Divisi IT", "category": "Nota Dinas", "source": "mail"},
    {"title": "Susun surat undangan rapat koordinasi teknis DEFEND ID", "category": "Surat Resmi", "source": "mail"},
    {"title": "Draft memo internal sosialisasi ketentuan disiplin & tata tertib", "category": "Memo", "source": "mail"},
    {"title": "Surat balasan resmi konfirmasi penerimaan kunjungan industri", "category": "Surat Keluar", "source": "mail"},
    {"title": "Email pengantar laporan berkala perkembangan proyek litbang", "category": "Email", "source": "mail"},
]


class SuggestionService:
    """
    Layanan penyedia rekomendasi kata kunci (hints & suggestions)
    secara dinamis dari database regulasi/dokumen/berita Pindad dan generator preset.
    """

    async def get_suggestions(
        self,
        mode: str = "documents",
        query: str = "",
        limit: int = 6,
        is_guest: bool = False,
        doc_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        clean_q = query.strip()
        mode_lower = (mode or "documents").lower()

        if mode_lower in ["doc_questions", "document_questions", "questions"]:
            return await self.get_document_questions(doc_id=doc_id, doc_title=clean_q, limit=limit)

        if mode_lower == "websearch":
            return self._filter_static(DEFAULT_WEB_SUGGESTIONS, clean_q, "Cari di web", "web", limit)

        elif mode_lower == "code":
            return self._filter_static(DEFAULT_CODE_SUGGESTIONS, clean_q, "Buatkan kode", "code", limit)

        elif mode_lower in ["diagram", "flow", "flowchart"]:
            presets = GUEST_DIAGRAM_SUGGESTIONS if is_guest else EMPLOYEE_DIAGRAM_SUGGESTIONS
            return self._filter_static(presets, clean_q, "Gambarkan diagram", "diagram", limit)

        elif mode_lower in ["chart", "data", "visualization"]:
            presets = GUEST_CHART_SUGGESTIONS if is_guest else EMPLOYEE_CHART_SUGGESTIONS
            return self._filter_static(presets, clean_q, "Visualisasikan data", "chart", limit)

        elif mode_lower in ["create_file", "generate_file", "file"]:
            return self._filter_static(DEFAULT_CREATE_FILE_SUGGESTIONS, clean_q, "Generate file", "file", limit)

        elif mode_lower in ["smart_mail", "mail", "email", "surat"]:
            return self._filter_static(DEFAULT_SMART_MAIL_SUGGESTIONS, clean_q, "Buatkan surat", "mail", limit)

        # Mode Documents / Focus -> Jika guest, jangan beri dokumen internal (PKB/SOP/SKEP)
        if is_guest:
            return self._filter_static(DEFAULT_WEB_SUGGESTIONS, clean_q, "Cari informasi", "web", limit)

        return await self._fetch_document_suggestions(clean_q, limit)

    async def get_document_questions(
        self,
        doc_id: Optional[int] = None,
        doc_title: str = "",
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        questions = []
        clean_title = doc_title.replace(".pdf", "").replace(".docx", "").replace(".txt", "").strip()

        # 1. Coba ambil dari rag_document_questions (Synthetic QA yang tersimpan di PostgreSQL)
        if doc_id:
            try:
                from backend.app.core import database
                pool = database.db_pool
                if pool:
                    async with pool.acquire() as conn:
                        rows = await conn.fetch(
                            """
                            SELECT generated_question 
                            FROM rag_document_questions 
                            WHERE source_id = $1 
                            ORDER BY id ASC 
                            LIMIT $2
                            """,
                            doc_id, limit
                        )
                        for r in rows:
                            q_text = r["generated_question"].strip()
                            if q_text:
                                questions.append({
                                    "title": q_text,
                                    "category": "Pertanyaan Dokumen",
                                    "doc_id": doc_id,
                                    "source": "synthetic_qa"
                                })
            except Exception as e:
                logger.warning(f"[SUGGESTIONS] Error querying rag_document_questions: {e}")

        # 2. Fallback: Template pertanyaan sintetis bermutu tinggi berbasis judul dokumen
        if not questions:
            t_name = f"'{clean_title}'" if clean_title else "dokumen ini"
            template_list = [
                (f"Ringkas poin-poin penting dalam {t_name}", "Ringkasan"),
                (f"Apa saja hak, kewajiban, atau aturan utama dalam {t_name}?", "Klausul Utama"),
                (f"Bagaimana alur prosedur dan ketentuan implementasi {t_name}?", "Prosedur & Alur"),
                (f"Apa sanksi, batasan, atau risiko hukum dalam {t_name}?", "Kepatuhan & Risiko"),
                (f"Jelaskan pasal atau bagian krusial pada {t_name}", "Bedah Pasal"),
            ]
            for q_title, cat in template_list[:limit]:
                questions.append({
                    "title": q_title,
                    "category": cat,
                    "doc_id": doc_id,
                    "source": "template"
                })

        return questions[:limit]

    def _filter_static(self, presets: List[Dict[str, Any]], query: str, default_prefix: str, source: str, limit: int) -> List[Dict[str, Any]]:
        if not query:
            return presets[:limit]
        filtered = [
            s for s in presets 
            if query.lower() in s["title"].lower() or query.lower() in s["category"].lower()
        ]
        if not filtered:
            return [{"title": f"{default_prefix}: {query}", "category": "Custom", "source": source}]
        return filtered[:limit]

    async def _fetch_document_suggestions(self, query: str, limit: int = 6) -> List[Dict[str, Any]]:
        suggestions = []
        try:
            from backend.app.core import database
            pool = database.db_pool
            if pool:
                async with pool.acquire() as conn:
                    if query:
                        search_pattern = f"%{query}%"
                        # 1. Cari di tabel dokumen / regulasi (PostgreSQL schema: d.judul, d.filename, d.nomor, j.nama)
                        sql = """
                            SELECT DISTINCT COALESCE(d.judul, d.filename, 'Dokumen Tanpa Judul') as title,
                                   COALESCE(j.nama, 'Regulasi') as category,
                                   d.id as doc_id,
                                   'dokumen' as source
                            FROM dokumen d
                            LEFT JOIN jenis_dokumen j ON d.id_jenis = j.id
                            WHERE (d.judul ILIKE $1 OR d.nomor ILIKE $1 OR d.filename ILIKE $1 OR j.nama ILIKE $1)
                            ORDER BY title ASC
                            LIMIT $2
                        """
                        rows = await conn.fetch(sql, search_pattern, limit)
                        for r in rows:
                            suggestions.append({
                                "title": r["title"].strip(),
                                "category": r["category"],
                                "doc_id": r["doc_id"],
                                "source": r["source"]
                            })
                    else:
                        # Default dokumen terpopuler / penting
                        sql = """
                            SELECT DISTINCT COALESCE(d.judul, d.filename, 'Dokumen Tanpa Judul') as title,
                                   COALESCE(j.nama, 'Regulasi') as category,
                                   d.id as doc_id,
                                   'dokumen' as source
                            FROM dokumen d
                            LEFT JOIN jenis_dokumen j ON d.id_jenis = j.id
                            ORDER BY d.id DESC
                            LIMIT $1
                        """
                        rows = await conn.fetch(sql, limit)
                        for r in rows:
                            suggestions.append({
                                "title": r["title"].strip(),
                                "category": r["category"],
                                "doc_id": r["doc_id"],
                                "source": r["source"]
                            })
        except Exception as e:
            logger.warning(f"[SUGGESTIONS] Database query fallback error: {e}")

        # Fallback default jika database kosong / offline
        if not suggestions:
            fallback_docs = [
                {"title": "Perjanjian Kerja Bersama (PKB) Periode 2024 - 2026", "category": "PKB", "source": "dokumen"},
                {"title": "Surat Keputusan Direksi tentang Ketentuan Disiplin & Tata Tertib", "category": "SKEP", "source": "dokumen"},
                {"title": "Pedoman Keselamatan, Kesehatan Kerja & Lingkungan Hidup (K3LH)", "category": "SOP", "source": "dokumen"},
                {"title": "Prosedur Operasional Standar Pengadaan Barang & Jasa Vendor", "category": "Pengadaan", "source": "dokumen"},
                {"title": "Ketentuan Hak Cuti Tahunan, Cuti Sakit, dan Izin Khusus Pegawai", "category": "HR", "source": "dokumen"},
            ]
            if query:
                suggestions = [d for d in fallback_docs if query.lower() in d["title"].lower()]
                if not suggestions:
                    suggestions = [{"title": f"Cari di arsip dokumen: {query}", "category": "Pencarian Dokumen", "source": "dokumen"}]
            else:
                suggestions = fallback_docs[:limit]

        return suggestions[:limit]


suggestion_service = SuggestionService()
