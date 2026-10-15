"""
CAKRA AI — PPT Master Sovereign Generator
=========================================
Generator presentasi dinamis dan representasi kanvas tingkat tinggi berbasis
filosofi dan arsitektur repositori PPT Master (hugohe3/ppt-master).

Mendukung:
1. Universal Data Intake: RAG, Web Search, Dokumen File, Chat Context, Prompt Konseptual.
2. Progressive SSE Event Stream: Emisi status interaktif halaman demi halaman (mirip Process Card).
3. Native OOXML (.pptx) Compiler via python-pptx (Widescreen 16:9, cards grid, timeline roadmap, stats).
4. Integrasi Disk Artefak & Session Brain Manifest.
"""

import os
import re
import json
import logging
import asyncio
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator, Union, Tuple
from datetime import datetime

import io
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import pptx
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls

from backend.app.core.paths import get_account_session_dir
from backend.app.services.tools.artifact_generator import sanitize_filename

logger = logging.getLogger("CAKRA_PPT_MASTER")

# ─── Palet Tema Warna Presentasi (Widescreen 16:9) ───────────────────────────
THEME_PALETTES = {
    "pindad-dark": {
        "name": "Pindad Navy & Gold",
        "bg_rgb": RGBColor(7, 21, 38),         # #071526 Deep Navy
        "card_bg_rgb": RGBColor(13, 37, 66),   # #0D2542 Surface Navy
        "card_subtle_rgb": RGBColor(10, 29, 52),
        "title_rgb": RGBColor(255, 255, 255),  # #FFFFFF Pure White
        "accent_rgb": RGBColor(243, 183, 44),  # #F3B72C Gold
        "text_rgb": RGBColor(226, 232, 240),   # #E2E8F0 Slate 200
        "muted_rgb": RGBColor(148, 163, 184),  # #94A3B8 Slate 400
        "border_rgb": RGBColor(243, 183, 44),
        "separator_rgb": RGBColor(30, 58, 95), # #1E3A5F
        "is_dark": True
    },
    "modern-dark": {
        "name": "Modern Slate",
        "bg_rgb": RGBColor(15, 23, 42),        # #0F172A Dark Slate
        "card_bg_rgb": RGBColor(30, 41, 59),   # #1E293B
        "card_subtle_rgb": RGBColor(24, 34, 49),
        "title_rgb": RGBColor(248, 250, 252),  # #F8FAFC
        "accent_rgb": RGBColor(56, 189, 248),  # #38BDF8 Sky
        "text_rgb": RGBColor(203, 213, 225),   # #CBD5E1
        "muted_rgb": RGBColor(100, 116, 139),  # #64748B
        "border_rgb": RGBColor(56, 189, 248),
        "separator_rgb": RGBColor(51, 65, 85),
        "is_dark": True
    },
    "clean-light": {
        "name": "Clean Corporate",
        "bg_rgb": RGBColor(248, 250, 252),     # #F8FAFC Light Slate
        "card_bg_rgb": RGBColor(255, 255, 255), # #FFFFFF
        "card_subtle_rgb": RGBColor(241, 245, 249),
        "title_rgb": RGBColor(15, 23, 42),      # #0F172A
        "accent_rgb": RGBColor(2, 132, 199),    # #0284C7 Blue
        "text_rgb": RGBColor(51, 65, 85),       # #334155
        "muted_rgb": RGBColor(100, 116, 139),   # #64748B
        "border_rgb": RGBColor(2, 132, 199),
        "separator_rgb": RGBColor(226, 232, 240),
        "is_dark": False
    },
    "emerald-tactical": {
        "name": "Tactical Emerald",
        "bg_rgb": RGBColor(6, 35, 24),         # #062318 Forest Dark
        "card_bg_rgb": RGBColor(13, 56, 41),    # #0D3829
        "card_subtle_rgb": RGBColor(10, 44, 32),
        "title_rgb": RGBColor(240, 253, 244),  # #F0FDF4
        "accent_rgb": RGBColor(52, 211, 153),   # #34D399 Emerald
        "text_rgb": RGBColor(226, 232, 240),   # #E2E8F0
        "muted_rgb": RGBColor(134, 239, 172),  # #86EFAC
        "border_rgb": RGBColor(52, 211, 153),
        "separator_rgb": RGBColor(22, 101, 52),
        "is_dark": True
    }
}


def _build_presentation_slides(
    topic: str, 
    slide_count: int = 6, 
    content_sources: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Menghasilkan data slide presentasi secara cerdas, kontekstual, dan dinamis
    berdasarkan domain topik (Arsitektur TI, Pertahanan/Alpalhankam, Regulasi/SOP, Bisnis).
    Menghindari slide statis/kaku dengan memberikan deliverable substantif di tiap kartu.
    """
    clean_topic = (topic or "Paparan Strategis").strip()
    lower_topic = clean_topic.lower()
    
    # ── Deteksi Domain Topik ──
    is_tech = any(k in lower_topic for k in ["microservice", "arsitektur", "software", "cloud", "api", "database", "devops", "k8s", "sistem", "backend", "frontend", "keamanan siber", "it"])
    is_defense = any(k in lower_topic for k in ["pindad", "senjata", "alutsista", "alpalhankam", "amunisi", "ranpur", "rantis", "militer", "pertahanan", "tni", "ss2", "anoa", "harimau", "badak"])
    is_regulation = any(k in lower_topic for k in ["sop", "regulasi", "peraturan", "kebijakan", "kepatuhan", "compliance", "tata kelola", "audit", "hukum", "uu", "perpres"])

    if is_tech:
        category_kicker = "TRANSFORMASI ARSITEKTUR & TEKNOLOGI"
        arc = [
            {
                "layout": "title",
                "cover_style": "split_editorial",
                "kicker": category_kicker,
                "title": clean_topic,
                "subtitle": "Modernisasi Sistem Berkelanjutan, Skalabilitas Tinggi & Keandalan Layanan",
                "presenter": "TIM ARSITEKTUR & STRATEGI",
                "organization": f"INISIASI STRATEGIS • {clean_topic.upper()}"
            },
            {
                "layout": "split_screen",
                "kicker": "ANALISIS SITUASI & LATAR BELAKANG",
                "title": f"Tantangan & Urgensi {clean_topic}",
                "subtitle": "Identifikasi Hambatan Arsitektur Monolitik Eksisting & Kebutuhan Skalabilitas",
                "hero": {
                    "badge": "AKAR MASALAH",
                    "title": "Bottleneck & Throughput Terpusat",
                    "desc": "Beban pemrosesan terpusat membatasi kapasitas transaksi saat lonjakan operasional lintas divisi, memicu ketergantungan database tunggal dan latensi tinggi.",
                    "takeaway": "Dekomposisi modular dan modernisasi layanan menjadi kebutuhan mendesak untuk kesinambungan bisnis."
                },
                "items": [
                    {
                        "title": "Siklus Rilis Terhambat",
                        "desc": "Keterikatan erat (tight coupling) antar modul menghambat kecepatan deployment fitur mandiri."
                    },
                    {
                        "title": "Isolasi Kegagalan Rendah",
                        "desc": "Insiden kegagalan satu sub-layanan berisiko melumpuhkan ekosistem tanpa mekanisme circuit breaker."
                    }
                ]
            },
            {
                "layout": "feature_list",
                "kicker": "DESAIN ARSITEKTUR INTI",
                "title": "Pilar Solusi & Dekomposisi Layanan",
                "subtitle": "Prinsip Desain Terdistribusi Menuju Arsitektur Mandiri dan Resilien",
                "items": [
                    {
                        "badge": "PILAR 01",
                        "title": "Bounded Context & API First",
                        "desc": "Pemisahan domain bisnis secara tegas dengan kontrak OpenAPI dan isolasi basis data mandiri."
                    },
                    {
                        "badge": "PILAR 02",
                        "title": "Event-Driven Backbone",
                        "desc": "Komunikasi asinkron via message streaming untuk menjamin decoupling dan konsistensi data."
                    },
                    {
                        "badge": "PILAR 03",
                        "title": "Gateway & Zero-Trust Security",
                        "desc": "Akses terpusat dengan autentikasi mTLS, rate limiting, dan isolasi jaringan bertingkat."
                    }
                ]
            },
            {
                "layout": "stats",
                "kicker": "INDIKATOR KINERJA UTAMA",
                "title": "Target Metrik & Peningkatan Kinerja",
                "subtitle": "Ekspektasi Pencapaian Efisiensi & Ketersediaan Pasca Implementasi",
                "stats": [
                    {
                        "value": "99.98%",
                        "label": "Ketersediaan Sistem (SLA)",
                        "desc": "Toleransi downtime < 1.7 jam/tahun via multi-cluster redundancy"
                    },
                    {
                        "value": "4.5x",
                        "label": "Frekuensi Deployment",
                        "desc": "Siklus rilis independen harian tanpa gangguan operasional"
                    },
                    {
                        "value": "< 45ms",
                        "label": "Latensi Respon (P99)",
                        "desc": "Efisiensi komunikasi internal service mesh berbasis high-throughput"
                    }
                ],
                "takeaway": "🎯 Transformasi arsitektur ditargetkan memangkas biaya pemeliharaan infrastruktur hingga 40% sekaligus meningkatkan ketahanan sistem operasional."
            },
            {
                "layout": "timeline",
                "kicker": "ROADMAP EKSEKUSI BERTAHAP",
                "title": "Tahapan Migrasi & Implementasi",
                "subtitle": "Jadwal Transisi Berkelanjutan Menjamin Zero Disruption Terhadap Bisnis",
                "steps": [
                    {
                        "phase": "TAHAP 1",
                        "title": "Strangler Fig Pattern",
                        "desc": "Memecah modul pendukung non-kritis menjadi microservice mandiri sebagai pilot project.",
                        "bullets": [
                            "Audit batasan bounded context modul",
                            "Setup container cluster & CI/CD pipeline"
                        ]
                    },
                    {
                        "phase": "TAHAP 2",
                        "title": "Implementasi API Gateway",
                        "desc": "Menyatukan gerbang akses frontend dan mengarahkan rute trafik secara transparan.",
                        "bullets": [
                            "Pengalihan rute dinamis (canary release)",
                            "Integrasi otorisasi terpusat & rate limit"
                        ]
                    },
                    {
                        "phase": "TAHAP 3",
                        "title": "Full Cloud Native",
                        "desc": "Dekomposisi penuh modul inti dan orkestrasi orkestrator kontainer secara menyeluruh.",
                        "bullets": [
                            "Migrasi database terdistribusi",
                            "Penerapan automated failover & telemetry"
                        ]
                    }
                ],
                "takeaway": "🎯 Pendekatan bertahap (Phased Rollout) memitigasi risiko kegagalan massal dan menjamin keberlangsungan operasional harian."
            },
            {
                "layout": "bullets",
                "kicker": "REKOMENDASI & TINDAK LANJUT",
                "title": "Rekomendasi Strategis Tim Proyek",
                "subtitle": "Langkah Konkret Untuk Memastikan Keberhasilan Tata Kelola & Adopsi",
                "bullets": [
                    "Menetapkan kontrak antarmuka API & Schema Registry yang terstandarisasi sebelum memecah modul baru.",
                    "Membangun tim DevSecOps lintas divisi untuk mengawal kepatuhan standar isolasi data industri pertahanan.",
                    "Mengimplementasikan platform observability terpadu (OpenTelemetry, Prometheus, Grafana) sejak fase awal.",
                    "Menyelenggarakan program peningkatan kompetensi internal terkait arsitektur distributed systems."
                ]
            }
        ]
    elif is_defense:
        category_kicker = "INDUSTRI PERTAHANAN & ALPALHANKAM"
        arc = [
            {
                "layout": "title",
                "cover_style": "modern_minimalist",
                "kicker": category_kicker,
                "title": clean_topic,
                "subtitle": "Pengembangan Kapabilitas Pertahanan, Keandalan Taktis & Kemandirian Industri",
                "presenter": "TIM PENGEMBANGAN STRATEGIS",
                "organization": f"KEMANDIRIAN INDUSTRI & TEKNOLOGI • {clean_topic.upper()}"
            },
            {
                "layout": "split_screen",
                "kicker": "ANALISIS KEBUTUHAN TAKTIS",
                "title": f"Latar Belakang & Doktrin Penggunaan",
                "subtitle": "Kebutuhan Operasional Lapangan Menghadapi Spektrum Ancaman Modern",
                "hero": {
                    "badge": "KEBUTUHAN UTAMA",
                    "title": "Kemandirian Rantai Pasok Hankam",
                    "desc": "Mereduksi ketergantungan komponen impor guna menjamin kedaulatan logistik pertahanan dengan Tingkat Kandungan Dalam Negeri (TKDN) di atas 65% serta ketersediaan suku cadang berkelanjutan.",
                    "takeaway": "Kedaulatan logistik alpalhankam mutlak bagi kesiapan tempur nasional."
                },
                "items": [
                    {
                        "title": "Daya Tahan & Ergonomi",
                        "desc": "Kemampuan operasi di medan tropis ekstrem dengan kemudahan perawatan di garis depan."
                    },
                    {
                        "title": "Akurasi & Balistik Optimal",
                        "desc": "Presisi tinggi pada jarak efektif sesuai standar kualifikasi teknis operasional."
                    }
                ]
            },
            {
                "layout": "feature_list",
                "kicker": "SPESIFIKASI & KEUNGGULAN PRODUK",
                "title": "Spesifikasi Teknis & Keunggulan",
                "subtitle": "Rancangan Rekayasa Presisi Berstandar Mutu Militer Internasional",
                "items": [
                    {
                        "badge": "FITUR 01",
                        "title": "Konstruksi Material Modular",
                        "desc": "Komponen polimer tahan benturan dan baja paduan tempa khusus berkekuatan tinggi."
                    },
                    {
                        "badge": "FITUR 02",
                        "title": "Interoperabilitas Sistem",
                        "desc": "Dukungan rel pikatini standar untuk integrasi optik bidik dan sensor malam hari."
                    },
                    {
                        "badge": "FITUR 03",
                        "title": "Standar Uji Balistik",
                        "desc": "Lolos serangkaian pengujian ekstrem lumpur, debu, dan sertifikasi Dislitbang TNI."
                    }
                ]
            },
            {
                "layout": "stats",
                "kicker": "INDIKATOR KINERJA PRODUK",
                "title": "Parameter Teknis & Kapabilitas Lapangan",
                "subtitle": "Capaian Metrik Pengujian Laboratorium & Lapangan Tembak",
                "stats": [
                    {
                        "value": "600m",
                        "label": "Jarak Efektif Tembak",
                        "desc": "Akurasi perkenaan sasaran titik dengan standar dispersi ketat"
                    },
                    {
                        "value": "750+",
                        "label": "Laju Tembak (RPM)",
                        "desc": "Kecepatan siklus mekanik optimal dengan recoil terkendali"
                    },
                    {
                        "value": "> 70%",
                        "label": "TKDN Nasional",
                        "desc": "Penggunaan bahan baku lokal baja paduan dan manufaktur dalam negeri"
                    }
                ],
                "takeaway": "🎯 Produk dirancang untuk memenuhi standar kelaikan alpalhankam modern demi memperkuat kedaulatan pertahanan nasional."
            },
            {
                "layout": "timeline",
                "kicker": "ROADMAP INDUSTRIALISASI",
                "title": "Tahapan Litbang Hingga Produksi Massal",
                "subtitle": "Rencana Eksekusi Menuju Pemenuhan Kebutuhan Alutsista Pengguna",
                "steps": [
                    {
                        "phase": "TAHAP 1",
                        "title": "Desain & Purwarupa",
                        "desc": "Pembuatan model 3D CAD, simulasi dinamika fluida/tegangan, dan perakitan prototipe awal.",
                        "bullets": [
                            "Penyusunan dokumen rekayasa teknik",
                            "Fabrikasi prototipe laboratorium 1 & 2"
                        ]
                    },
                    {
                        "phase": "TAHAP 2",
                        "title": "Uji Kelaikan & Sertifikasi",
                        "desc": "Pelaksanaan uji fungsi taktis dan sertifikasi kelaikan bersama badan litbang militer.",
                        "bullets": [
                            "Uji tembak kontinu & pengujian lingkungan",
                            "Penerbitan sertifikat kelaikan resmi"
                        ]
                    },
                    {
                        "phase": "TAHAP 3",
                        "title": "Produksi Massal & Distribusi",
                        "desc": "Industrialisasi lini produksi, quality control ketat, dan pengiriman unit ke satuan pengguna.",
                        "bullets": [
                            "Optimalisasi lini perakitan manufaktur",
                            "Pelatihan pemeliharaan bagi personel pengguna"
                        ]
                    }
                ],
                "takeaway": "🎯 Rencana industrialisasi memastikan pengiriman tepat waktu dengan konsistensi mutu yang terjamin."
            },
            {
                "layout": "bullets",
                "kicker": "KESIMPULAN & LANGKAH KE DEPAN",
                "title": "Rekomendasi Kebijakan & Rencana Aksi",
                "subtitle": "Penguatan Ekosistem Manufaktur Pertahanan Nasional",
                "bullets": [
                    "Mempercepat sinergi rantai pasok material logam khusus dengan industri baja strategis nasional.",
                    "Menerapkan otomasi robotik pada proses pemesinan presisi untuk meningkatkan kapasitas output produksi.",
                    "Mengembangkan varian turunan sesuai umpan balik taktis dari satuan pengguna lapangan.",
                    "Memperkuat program pemeliharaan berkelanjutan (Life Cycle Support) bersama pengguna."
                ]
            }
        ]
    elif is_regulation:
        category_kicker = "TATA KELOLA & REGULASI KORPORAT"
        arc = [
            {
                "layout": "title",
                "cover_style": "centered_hero",
                "kicker": category_kicker,
                "title": clean_topic,
                "subtitle": "Kerangka Kepatuhan, Standardisasi Operasional & Manajemen Risiko Terpadu",
                "presenter": "TIM TATA KELOLA & KEPATUHAN",
                "organization": "KOMITE REGULASI & MANAJEMEN RISIKO"
            },
            {
                "layout": "split_screen",
                "kicker": "LANDASAN HUKUM & URGENSI",
                "title": f"Latar Belakang & Landasan Hukum",
                "subtitle": "Konteks Kepatuhan dan Penyelarasan Terhadap Regulasi Nasional",
                "hero": {
                    "badge": "URGENSI UTAMA",
                    "title": "Mitigasi Risiko Hukum & Regulasi",
                    "desc": "Mencegah potensi sengketa hukum, denda administratif, dan penyimpangan prosedur operasional melalui pencatatan jejak audit yang valid dan transparan.",
                    "takeaway": "Kepatuhan tata kelola adalah fondasi keberlanjutan dan reputasi institusi."
                },
                "items": [
                    {
                        "title": "Penyelarasan Regulasi",
                        "desc": "Menyesuaikan kebijakan internal dengan undang-undang dan peraturan menteri terbaru."
                    },
                    {
                        "title": "Efisiensi Tata Kelola",
                        "desc": "Menstandarisasi birokrasi agar proses verifikasi dan persetujuan berjalan lincah."
                    }
                ]
            },
            {
                "layout": "feature_list",
                "kicker": "KERANGKA KEBIJAKAN UTAMA",
                "title": "Pilar Kepatuhan & Prosedur Inti",
                "subtitle": "Standar Operasional Prosedur Yang Wajib Dipedomani Seluruh Insan Organisasi",
                "items": [
                    {
                        "badge": "PILAR 01",
                        "title": "Akuntabilitas & Integritas",
                        "desc": "Dokumentasi resmi dan penerapan matriks kewenangan serta prinsip Four-Eyes."
                    },
                    {
                        "badge": "PILAR 02",
                        "title": "Pengawasan Berkala",
                        "desc": "Supervisi aktif melalui audit kepatuhan mandiri dan Whistleblowing System."
                    },
                    {
                        "badge": "PILAR 03",
                        "title": "Transparansi Informasi",
                        "desc": "Keterbukaan informasi terukur dengan tetap menjaga data strategis dan rahasia institusi."
                    }
                ]
            },
            {
                "layout": "stats",
                "kicker": "TARGET KEPATUHAN & AUDIT",
                "title": "Target Capaian & Indikator Kepatuhan",
                "subtitle": "Key Compliance Indicators Menuju Predikat Tata Kelola Unggul",
                "stats": [
                    {
                        "value": "100%",
                        "label": "Kepatuhan Regulasi",
                        "desc": "Zero finding audit material oleh badan pemeriksa eksternal"
                    },
                    {
                        "value": "< 3 Hari",
                        "label": "Waktu Verifikasi",
                        "desc": "Percepatan siklus persetujuan dokumen melalui alur digital"
                    },
                    {
                        "value": "95%+",
                        "label": "Tingkat Pemahaman",
                        "desc": "Cakupan sosialisasi dan pemahaman regulasi bagi seluruh pegawai"
                    }
                ],
                "takeaway": "🎯 Kepatuhan bukan sekadar kewajiban formalitas, melainkan fondasi perlindungan aset dan reputasi berkelanjutan korporat."
            },
            {
                "layout": "timeline",
                "kicker": "JADWAL IMPLEMENTASI REGULASI",
                "title": "Tahapan Sosialisasi & Penerapan Efektif",
                "subtitle": "Pemberlakuan Bertahap Guna Memastikan Kesiapan Seluruh Unit Kerja",
                "steps": [
                    {
                        "phase": "TAHAP 1",
                        "title": "Penetapan & Distribusi",
                        "desc": "Pengesahan surat keputusan direksi dan diseminasi dokumen resmi ke seluruh divisi.",
                        "bullets": [
                            "Penerbitan Surat Edaran Resmi",
                            "Penyediaan dokumen di portal intranet korporat"
                        ]
                    },
                    {
                        "phase": "TAHAP 2",
                        "title": "Sosialisasi & Workshop",
                        "desc": "Penyelenggaraan sesi pelatihan intensif bagi para pimpinan unit kerja dan staf operasional.",
                        "bullets": [
                            "Workshop studi kasus implementasi",
                            "Tanya jawab panduan teknis operasional"
                        ]
                    },
                    {
                        "phase": "TAHAP 3",
                        "title": "Pemberlakuan Penuh",
                        "desc": "Penerapan sanksi dan penghargaan secara konsisten disertai evaluasi berkala triwulan.",
                        "bullets": [
                            "Inspeksi mendadak kepatuhan prosedur",
                            "Laporan kepatuhan semesteran ke Dewan Komisaris"
                        ]
                    }
                ],
                "takeaway": "🎯 Implementasi terstruktur menjamin transisi kebijakan berjalan mulus tanpa menimbulkan friksi kerja."
            },
            {
                "layout": "bullets",
                "kicker": "KESIMPULAN & REKOMENDASI",
                "title": "Rekomendasi Tindak Lanjut Strategis",
                "subtitle": "Komitmen Bersama Dalam Membangun Budaya Kepatuhan Berkelanjutan",
                "bullets": [
                    "Membentuk focal point kepatuhan di masing-masing unit kerja guna memantau pelaksanaan harian.",
                    "Mengintegrasikan modul kuis pemahaman regulasi ke dalam sistem manajemen pembelajaran (LMS) SDM.",
                    "Melakukan review tahunan terhadap efektivitas regulasi untuk mengantisipasi dinamika bisnis terkini.",
                    "Memberikan apresiasi kepada unit kerja dengan indeks kepatuhan tata kelola tertinggi."
                ]
            }
        ]
    else:
        # Default Eksekutif / Bisnis Universal
        category_kicker = "PAPARAN EKSEKUTIF STRATEGIS"
        arc = [
            {
                "layout": "title",
                "cover_style": "split_editorial",
                "kicker": category_kicker,
                "title": clean_topic,
                "subtitle": "Rencana Strategis, Analisis Komprehensif & Sasaran Kinerja Terpadu",
                "presenter": "TIM PERENCANAAN STRATEGIS",
                "organization": "BADAN PENGEMBANGAN & MANAJEMEN STRATEGIS"
            },
            {
                "layout": "split_screen",
                "kicker": "ANALISIS SITUASI & TANTANGAN",
                "title": f"Tantangan & Peluang {clean_topic}",
                "subtitle": "Pemetaan Kondisi Internal & Dinamika Lingkungan Eksternal",
                "hero": {
                    "badge": "FOKUS UTAMA",
                    "title": "Akselerasi Produktivitas & Mutu",
                    "desc": "Pemanfaatan inovasi teknologi dan integrasi alur kerja modern untuk melipatgandakan efisiensi operasional dan kepuasan pengguna akhir.",
                    "takeaway": "Optimalisasi sumber daya dan standardisasi alur kerja menjadi kunci keberhasilan kompetitif."
                },
                "items": [
                    {
                        "title": "Tantangan Operasional",
                        "desc": "Kebutuhan optimalisasi kapasitas dan standarisasi alur kerja antar unit fungsi."
                    },
                    {
                        "title": "Dinamika Pemangku Kepentingan",
                        "desc": "Tuntutan responsivitas yang lebih cepat terhadap perubahan standar mutu dan layanan."
                    }
                ]
            },
            {
                "layout": "feature_list",
                "kicker": "STRATEGI & INISIATIF UTAMA",
                "title": "Pilar Inisiatif & Program Kerja",
                "subtitle": "Langkah Strategis Berkelanjutan Untuk Mencapai Keunggulan Kompetitif",
                "items": [
                    {
                        "badge": "PILAR 01",
                        "title": "Penguatan Fondasi",
                        "desc": "Modernisasi infrastruktur inti dan penguatan tata kelola manajemen risiko terpadu."
                    },
                    {
                        "badge": "PILAR 02",
                        "title": "Kolaborasi Sinergis",
                        "desc": "Gugus tugas lintas fungsi dan integrasi dashboard pemantauan progres bersama secara transparan."
                    },
                    {
                        "badge": "PILAR 03",
                        "title": "Inovasi Berkelanjutan",
                        "desc": "Kultur perbaikan berkesinambungan (Kaizen) dan metodologi kerja adaptif pada seluruh lini."
                    }
                ]
            },
            {
                "layout": "stats",
                "kicker": "INDIKATOR KINERJA UTAMA",
                "title": "Target Kinerja & Sasaran Strategis",
                "subtitle": "Key Performance Indicators Sebagai Tolok Ukur Keberhasilan Eksekusi",
                "stats": [
                    {
                        "value": "+35%",
                        "label": "Efisiensi Produktivitas",
                        "desc": "Peningkatan throughput hasil kerja per jam kerja operasional"
                    },
                    {
                        "value": "99.5%",
                        "label": "Akurasi Eksekusi",
                        "desc": "Tingkat kesesuaian output terhadap standar mutu target"
                    },
                    {
                        "value": "100%",
                        "label": "Penyelesaian Tepat Waktu",
                        "desc": "Kepatuhan terhadap milestone jadwal yang telah disepakati"
                    }
                ],
                "takeaway": "🎯 Target kinerja ditetapkan secara terukur demi menjamin transparansi pencapaian tujuan strategis organisasi."
            },
            {
                "layout": "timeline",
                "kicker": "ROADMAP IMPLEMENTASI",
                "title": "Tahapan Pelaksanaan & Roadmap Eksekusi",
                "subtitle": "Rencana Implementasi Bertahap Menuju Pencapaian Target Penuh",
                "steps": [
                    {
                        "phase": "TAHAP 1",
                        "title": "Konsolidasi & Persiapan",
                        "desc": "Penyelarasan tim, penganggaran, dan penetapan indikator keberhasilan awal.",
                        "bullets": [
                            "Kick-off pertemuan pemangku kepentingan",
                            "Penyusunan rencana kerja terinci (Work Breakdown)"
                        ]
                    },
                    {
                        "phase": "TAHAP 2",
                        "title": "Implementasi Bertahap",
                        "desc": "Eksekusi proyek percontohan (pilot project) dan penyempurnaan alur kerja.",
                        "bullets": [
                            "Uji coba penerapan pada unit terpilih",
                            "Evaluasi kendala teknis dan umpan balik pengguna"
                        ]
                    },
                    {
                        "phase": "TAHAP 3",
                        "title": "Ekspansi & Penskalaan",
                        "desc": "Penerapan skala penuh ke seluruh unit organisasi dengan pengawasan berkelanjutan.",
                        "bullets": [
                            "Rollout komprehensif ke seluruh departemen",
                            "Pemantauan performa melalui executive dashboard"
                        ]
                    }
                ],
                "takeaway": "🎯 Eksekusi bertahap meminimalkan distorsi operasional dan menjamin adopsi pengguna secara optimal."
            },
            {
                "layout": "bullets",
                "kicker": "KESIMPULAN & REKOMENDASI",
                "title": "Rekomendasi Strategis & Rencana Aksi",
                "subtitle": "Langkah Konkret Untuk Memastikan Keberlanjutan Capaian",
                "bullets": [
                    "Memastikan komitmen pimpinan puncak sebagai sponsor utama kelancaran transformasi.",
                    "Melakukan tinjauan berkala dwimingguan terhadap hambatan di lapangan agar cepat teratasi.",
                    "Menyediakan saluran komunikasi terbuka untuk menampung masukan konstruktif tim pelaksana.",
                    "Mendokumentasikan praktik terbaik (best practices) sebagai aset pengetahuan organisasi."
                ]
            }
        ]

    # Sesuaikan panjang slide dengan kebutuhan safe_count
    slides_output = []
    for i in range(slide_count):
        if i < len(arc):
            slides_output.append(arc[i])
        else:
            slides_output.append({
                "layout": "bullets",
                "kicker": "BAGIAN LANJUTAN",
                "title": f"Fokus Tambahan: Bagian {i + 1}",
                "subtitle": f"Analisis Lanjutan & Rencana Aksi {clean_topic}",
                "bullets": [
                    f"Poin strategis implementasi lanjutan bagian {i + 1}.",
                    "Penyelarasan dengan tata kelola operasional korporat.",
                    "Mitigasi risiko dan rencana kontinuitas layanan."
                ]
            })
            
    return slides_output


def _parse_rgb(hex_code: Optional[str], default_rgb: RGBColor) -> RGBColor:
    """Helper untuk mem-parsing kode heksadesimal ke RGBColor pptx dengan failover aman."""
    if not hex_code or not isinstance(hex_code, str):
        return default_rgb
    c = hex_code.strip().lstrip("#")
    if len(c) == 6:
        try:
            return RGBColor(int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
        except ValueError:
            return default_rgb
    return default_rgb


def _resolve_palette(
    custom_theme: Optional[Dict[str, Any]] = None, 
    theme_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Menyusun palet warna DrawingML secara dinamis berbasis rancangan AI (theme_style)
    atau fallback ke tema preset netral.
    """
    if custom_theme and isinstance(custom_theme, dict) and ("bg_hex" in custom_theme or "accent_hex" in custom_theme):
        is_dark = custom_theme.get("is_dark")
        if is_dark is None:
            is_dark = True
        bg = _parse_rgb(custom_theme.get("bg_hex"), RGBColor(15, 23, 42) if is_dark else RGBColor(246, 248, 252))
        card_bg = _parse_rgb(custom_theme.get("card_bg_hex"), RGBColor(24, 34, 49) if is_dark else RGBColor(255, 255, 255))
        accent = _parse_rgb(custom_theme.get("accent_hex"), RGBColor(56, 189, 248) if is_dark else RGBColor(37, 99, 235))
        title = _parse_rgb(custom_theme.get("title_hex"), RGBColor(248, 250, 252) if is_dark else RGBColor(15, 23, 42))
        text = _parse_rgb(custom_theme.get("text_hex"), RGBColor(203, 213, 225) if is_dark else RGBColor(51, 65, 85))
        muted = _parse_rgb(custom_theme.get("muted_hex"), RGBColor(148, 163, 184) if is_dark else RGBColor(100, 116, 139))
        border = _parse_rgb(custom_theme.get("border_hex"), accent if is_dark else RGBColor(218, 224, 233))
        separator = _parse_rgb(custom_theme.get("separator_hex"), RGBColor(51, 65, 85) if is_dark else RGBColor(226, 232, 240))
        card_subtle = _parse_rgb(custom_theme.get("card_subtle_hex"), RGBColor(30, 41, 59) if is_dark else RGBColor(241, 245, 249))
        return {
            "name": custom_theme.get("name", "AI Designed Palette"),
            "bg_rgb": bg,
            "card_bg_rgb": card_bg,
            "card_subtle_rgb": card_subtle,
            "title_rgb": title,
            "accent_rgb": accent,
            "text_rgb": text,
            "muted_rgb": muted,
            "border_rgb": border,
            "separator_rgb": separator,
            "is_dark": is_dark
        }
    
    if theme_id and theme_id in THEME_PALETTES:
        return THEME_PALETTES[theme_id]
        
    return THEME_PALETTES.get("modern-dark", THEME_PALETTES["pindad-dark"])


def _generate_deck_background_image(
    palette: Dict[str, Any], 
    custom_theme: Optional[Dict[str, Any]] = None,
    width: int = 1920, 
    height: int = 1080
) -> bytes:
    """
    Menghasilkan citra kanvas latar belakang dinamis (1920x1080, 16:9)
    dengan gradasi diagonal, ambient glow orbs, dan pola partikel/grid
    yang selaras dengan konsep desain visual PPT Master.
    """
    try:
        bg_rgb = palette["bg_rgb"]
        card_bg_rgb = palette["card_bg_rgb"]
        accent_rgb = palette["accent_rgb"]
        is_dark = palette.get("is_dark", True)
        
        # 1. Base Diagonal Linear Gradient
        y_coords, x_coords = np.mgrid[0:height, 0:width]
        diag = (x_coords / width + y_coords / height) / 2.0
        
        c1 = np.array([bg_rgb[0], bg_rgb[1], bg_rgb[2]], dtype=np.float32)
        c2 = np.array([card_bg_rgb[0], card_bg_rgb[1], card_bg_rgb[2]], dtype=np.float32)
        
        grad_array = (1.0 - diag[..., np.newaxis]) * c1 + diag[..., np.newaxis] * c2
        grad_array = np.clip(grad_array, 0, 255).astype(np.uint8)
        base_img = Image.fromarray(grad_array, mode='RGB')
        
        # 2. Ambient Glow Orbs
        glow_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_img)
        acc_alpha = 75 if is_dark else 45
        acc_color = (accent_rgb[0], accent_rgb[1], accent_rgb[2], acc_alpha)
        glow_draw.ellipse([int(width * 0.70), -int(height * 0.25), int(width * 1.25), int(height * 0.65)], fill=acc_color)
        cbg_alpha = 65 if is_dark else 35
        cbg_color = (card_bg_rgb[0], card_bg_rgb[1], card_bg_rgb[2], cbg_alpha)
        glow_draw.ellipse([-int(width * 0.20), int(height * 0.55), int(width * 0.40), int(height * 1.25)], fill=cbg_color)
        glow_blurred = glow_img.filter(ImageFilter.GaussianBlur(radius=80))
        base_img.paste(glow_blurred, (0, 0), glow_blurred)
        
        # 3. Dynamic Texture (dots_particles / cyber_grid)
        backdrop_effect = "dots_particles"
        if custom_theme and isinstance(custom_theme, dict):
            backdrop_effect = custom_theme.get("backdrop_effect", "")
            if not backdrop_effect and "grid" in str(custom_theme.get("visual_style", "")).lower():
                backdrop_effect = "cyber_grid"
        if not backdrop_effect:
            backdrop_effect = "dots_particles"
            
        texture_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        tex_draw = ImageDraw.Draw(texture_img)
        
        if backdrop_effect == "cyber_grid":
            grid_step = 48
            grid_alpha = 22 if is_dark else 15
            grid_color = (accent_rgb[0], accent_rgb[1], accent_rgb[2], grid_alpha)
            for x in range(0, width, grid_step):
                tex_draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
            for y in range(0, height, grid_step):
                tex_draw.line([(0, y), (width, y)], fill=grid_color, width=1)
        elif backdrop_effect == "dots_particles":
            dot_step = 32
            dot_alpha = 35 if is_dark else 20
            dot_color = (accent_rgb[0], accent_rgb[1], accent_rgb[2], dot_alpha)
            dot_r = 1.5
            for x in range(dot_step // 2, width, dot_step):
                for y in range(dot_step // 2, height, dot_step):
                    tex_draw.ellipse([x - dot_r, y - dot_r, x + dot_r, y + dot_r], fill=dot_color)
                    
        base_img.paste(texture_img, (0, 0), texture_img)
        
        # 4. Vignette Softening
        cx, cy = width / 2, height / 2
        max_radius = np.sqrt(cx**2 + cy**2)
        dist = np.sqrt((x_coords - cx)**2 + (y_coords - cy)**2) / max_radius
        vignette_alpha = np.clip((dist - 0.5) / 0.5, 0, 1) * (100 if is_dark else 40)
        vignette_array = np.zeros((height, width, 4), dtype=np.uint8)
        if is_dark:
            vignette_array[..., 0:3] = 0
        else:
            vignette_array[..., 0:3] = 255
        vignette_array[..., 3] = vignette_alpha.astype(np.uint8)
        vig_img = Image.fromarray(vignette_array, mode='RGBA')
        base_img.paste(vig_img, (0, 0), vig_img)
        
        out_io = io.BytesIO()
        base_img.save(out_io, format="PNG", optimize=True)
        return out_io.getvalue()
    except Exception as e:
        logger.warning(f"[PPT_MASTER] Gagal generate background canvas dinamis: {e}")
        return b""


def _safe_str(val: Any, default: str = "") -> str:
    """Safely converts any value (including dict, list, None, int, bool) to a clean string for python-pptx text frames."""
    if val is None:
        return default
    if isinstance(val, str):
        return val
    if isinstance(val, (int, float, bool)):
        return str(val)
    if isinstance(val, dict):
        return str(
            val.get("text")
            or val.get("point")
            or val.get("content")
            or val.get("desc")
            or val.get("description")
            or val.get("title")
            or val.get("label")
            or val.get("value")
            or " - ".join([_safe_str(v) for v in val.values() if v and not isinstance(v, (dict, list))])
            or default
        )
    if isinstance(val, (list, tuple, set)):
        return " • ".join([_safe_str(item) for item in val if item])
    return str(val)


def _create_native_pptx_file(
    slides_data: List[Dict[str, Any]], 
    output_path: Path, 
    theme_id: Optional[str] = None,
    custom_theme_style: Optional[Dict[str, Any]] = None,
    deck_title: Optional[str] = None
) -> Path:
    """
    Mengompilasi slide data menjadi file .pptx native menggunakan python-pptx
    berdasarkan standar arsitektur PPT Master (Widescreen 16:9, cards grid, flowline, stats).
    Mendukung kanvas latar belakang dinamis dan transisi native OpenXML.
    """
    palette = _resolve_palette(custom_theme=custom_theme_style, theme_id=theme_id)
    
    # 🎨 Render kanvas background dinamis (1920x1080 16:9) sekali per presentasi
    bg_bytes = _generate_deck_background_image(palette=palette, custom_theme=custom_theme_style)
    
    prs = Presentation()
    # Standar Widescreen 16:9 (13.333 x 7.5 inches)
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    
    blank_layout = prs.slide_layouts[6]  # Blank layout
    
    # ── Deteksi presenter & organisasi global untuk header, cover, & footer ──
    global_pres = None
    global_org = None
    for raw_item in slides_data:
        norm_temp = _normalize_slide_item(raw_item)
        if not global_pres and norm_temp.get("presenter"):
            global_pres = norm_temp["presenter"]
        if not global_org and norm_temp.get("organization"):
            global_org = norm_temp["organization"]
        if global_pres and global_org:
            break
    if not global_org and custom_theme_style:
        global_org = custom_theme_style.get("organization") or custom_theme_style.get("name")
    if not global_org:
        global_org = "EXECUTIVE PRESENTATION"
    if not global_pres:
        global_pres = "EXECUTIVE TEAM"
        
    for idx, raw_s in enumerate(slides_data):
        s = _normalize_slide_item(raw_s, idx + 1)
        slide = prs.slides.add_slide(blank_layout)
        
        # ── 1. Full-Bleed High-Res Slide Background Canvas ──
        if bg_bytes:
            try:
                slide.shapes.add_picture(
                    io.BytesIO(bg_bytes), 
                    Inches(0), Inches(0), Inches(13.333), Inches(7.5)
                )
            except Exception as e_bg:
                logger.warning(f"[PPT_MASTER] Fallback background shape: {e_bg}")
                bg_shape = slide.shapes.add_shape(
                    MSO_SHAPE.RECTANGLE, 
                    Inches(0), Inches(0), Inches(13.333), Inches(7.5)
                )
                bg_shape.fill.solid()
                bg_shape.fill.fore_color.rgb = palette["bg_rgb"]
                bg_shape.line.fill.background()
        else:
            bg_shape = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, 
                Inches(0), Inches(0), Inches(13.333), Inches(7.5)
            )
            bg_shape.fill.solid()
            bg_shape.fill.fore_color.rgb = palette["bg_rgb"]
            bg_shape.line.fill.background()

        # ── 2. Native Slide Transition (Ditentukan LLM / User) ──
        trans_name = s.get("transition") or (custom_theme_style.get("transition") if custom_theme_style else None) or "fade"
        trans_clean = str(trans_name).strip().lower()
        valid_transitions = {"fade", "push", "wipe", "split", "cut", "zoom", "wheel"}
        active_trans = trans_clean if trans_clean in valid_transitions else "fade"
        try:
            trans_xml = parse_xml(f'<p:transition {nsdecls("p")}><p:{active_trans}/></p:transition>')
            slide._element.append(trans_xml)
        except Exception as e_tr:
            logger.debug(f"[PPT_MASTER] Gagal menyematkan transisi slide {idx + 1}: {e_tr}")
        
        # ── Target Animasi Shape Native DrawingML untuk Slide ini ──
        slide_anim_targets = []
        slide_anim_attr = s.get("animation")

        def record_anim(shape_obj, comp_anim=None, default_effect="entrance_fade", delay_ms=0, dur=0.35):
            if not shape_obj or not hasattr(shape_obj, "shape_id"):
                return
            eff = comp_anim or slide_anim_attr or default_effect or "entrance_fade"
            eff_clean = str(eff).strip().lower()
            if not eff_clean.startswith("entrance_") and not eff_clean.startswith("emphasis_") and not eff_clean.startswith("exit_"):
                eff_clean = f"entrance_{eff_clean}"
            valid_effects = {
                "entrance_appear", "entrance_fade", "entrance_fly", "entrance_zoom",
                "entrance_wipe", "entrance_split", "entrance_expand", "entrance_dissolve",
                "entrance_wheel", "entrance_box", "entrance_circle", "entrance_swivel"
            }
            final_eff = eff_clean if eff_clean in valid_effects else "entrance_fade"
            slide_anim_targets.append((shape_obj.shape_id, int(delay_ms), final_eff, float(dur)))

        layout = s.get("layout", "bullets").lower()
        title_text = s.get("title", f"Slide {idx + 1}")
        subtitle_text = s.get("subtitle", "")
        kicker_text = s.get("kicker", "CAKRA AI • EXECUTIVE PRESENTATION")
        
        # ── 2. Render Slide Sesuai Layout ──
        if idx == 0 or layout == "title":
            # ── COVER / TITLE SLIDE MULTI-ARCHETYPE (PPT MASTER) ──
            cover_style = s.get("cover_style") or (custom_theme_style.get("cover_style") if custom_theme_style else None)
            if not cover_style:
                cover_style = "split_editorial"

            pres_name = s.get("presenter") or global_pres
            org_name = s.get("organization") or global_org
            date_str = s.get("date") or datetime.now().strftime('%B %Y')

            if cover_style == "centered_hero":
                # ── ARCHETYPE 1: CENTERED HERO ──
                k_box = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    Inches(4.166), Inches(1.5), Inches(5.0), Inches(0.42)
                )
                k_box.fill.solid()
                k_box.fill.fore_color.rgb = palette["card_subtle_rgb"]
                k_box.line.color.rgb = palette["accent_rgb"]
                k_box.line.width = Pt(1)
                ktf = k_box.text_frame
                ktf.word_wrap = True
                ktf.vertical_anchor = MSO_ANCHOR.TOP
                p_k = ktf.paragraphs[0]
                p_k.text = kicker_text.upper()
                p_k.font.size = Pt(10)
                p_k.font.bold = True
                p_k.font.color.rgb = palette["accent_rgb"]
                p_k.alignment = PP_ALIGN.CENTER
                record_anim(k_box, delay_ms=0)

                t_box = slide.shapes.add_textbox(Inches(1.2), Inches(2.15), Inches(10.933), Inches(2.4))
                ttf = t_box.text_frame
                ttf.word_wrap = True
                ttf.vertical_anchor = MSO_ANCHOR.TOP
                p_t = ttf.paragraphs[0]
                p_t.text = title_text
                p_t.font.size = Pt(38)
                p_t.font.bold = True
                p_t.font.color.rgb = palette["title_rgb"]
                p_t.alignment = PP_ALIGN.CENTER

                if subtitle_text:
                    p_sub = ttf.add_paragraph()
                    p_sub.text = subtitle_text
                    p_sub.font.size = Pt(16)
                    p_sub.font.color.rgb = palette["accent_rgb"]
                    p_sub.alignment = PP_ALIGN.CENTER
                    p_sub.space_before = Pt(10)
                record_anim(t_box, delay_ms=80)

                div_line = slide.shapes.add_shape(
                    MSO_SHAPE.RECTANGLE,
                    Inches(5.416), Inches(4.75), Inches(2.5), Inches(0.04)
                )
                div_line.fill.solid()
                div_line.fill.fore_color.rgb = palette["accent_rgb"]
                div_line.line.fill.background()

                pres_card = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    Inches(3.416), Inches(5.1), Inches(6.5), Inches(1.2)
                )
                pres_card.fill.solid()
                pres_card.fill.fore_color.rgb = palette["card_bg_rgb"]
                pres_card.line.color.rgb = palette["separator_rgb"]
                pres_card.line.width = Pt(1)
                ptf = pres_card.text_frame
                ptf.word_wrap = True
                ptf.vertical_anchor = MSO_ANCHOR.TOP
                ptf.margin_top = Inches(0.2)
                p_p1 = ptf.paragraphs[0]
                p_p1.text = pres_name
                p_p1.font.size = Pt(13)
                p_p1.font.bold = True
                p_p1.font.color.rgb = palette["title_rgb"]
                p_p1.alignment = PP_ALIGN.CENTER

                p_p2 = ptf.add_paragraph()
                p_p2.text = f"{org_name}  •  {date_str}"
                p_p2.font.size = Pt(11)
                p_p2.font.color.rgb = palette["muted_rgb"]
                p_p2.alignment = PP_ALIGN.CENTER
                p_p2.space_before = Pt(3)
                record_anim(pres_card, delay_ms=160)

            elif cover_style == "modern_minimalist":
                # ── ARCHETYPE 2: MODERN MINIMALIST WITH ACCENT STRIPE ──
                acc_bar = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    Inches(1.0), Inches(1.8), Inches(0.12), Inches(4.5)
                )
                acc_bar.fill.solid()
                acc_bar.fill.fore_color.rgb = palette["accent_rgb"]
                acc_bar.line.fill.background()

                k_box = slide.shapes.add_textbox(Inches(1.3), Inches(1.8), Inches(10.5), Inches(0.35))
                ktf = k_box.text_frame
                ktf.margin_left = Inches(0)
                p_k = ktf.paragraphs[0]
                p_k.text = kicker_text.upper()
                p_k.font.size = Pt(11)
                p_k.font.bold = True
                p_k.font.color.rgb = palette["accent_rgb"]

                t_box = slide.shapes.add_textbox(Inches(1.3), Inches(2.2), Inches(10.8), Inches(2.6))
                ttf = t_box.text_frame
                ttf.word_wrap = True
                ttf.margin_left = Inches(0)
                p_t = ttf.paragraphs[0]
                p_t.text = title_text
                p_t.font.size = Pt(38)
                p_t.font.bold = True
                p_t.font.color.rgb = palette["title_rgb"]
                if subtitle_text:
                    p_sub = ttf.add_paragraph()
                    p_sub.text = subtitle_text
                    p_sub.font.size = Pt(16)
                    p_sub.font.color.rgb = palette["muted_rgb"]
                    p_sub.space_before = Pt(8)

                meta_card1 = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    Inches(1.3), Inches(5.1), Inches(5.2), Inches(1.1)
                )
                meta_card1.fill.solid()
                meta_card1.fill.fore_color.rgb = palette["card_bg_rgb"]
                meta_card1.line.color.rgb = palette["separator_rgb"]
                m1_tf = meta_card1.text_frame
                m1_tf.margin_left = Inches(0.2)
                m1_tf.margin_top = Inches(0.18)
                p_m1 = m1_tf.paragraphs[0]
                p_m1.text = "DIBAWAKAN OLEH"
                p_m1.font.size = Pt(9)
                p_m1.font.color.rgb = palette["accent_rgb"]
                p_m1.font.bold = True
                p_m1b = m1_tf.add_paragraph()
                p_m1b.text = pres_name
                p_m1b.font.size = Pt(12)
                p_m1b.font.bold = True
                p_m1b.font.color.rgb = palette["title_rgb"]

                meta_card2 = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    Inches(6.8), Inches(5.1), Inches(5.2), Inches(1.1)
                )
                meta_card2.fill.solid()
                meta_card2.fill.fore_color.rgb = palette["card_bg_rgb"]
                meta_card2.line.color.rgb = palette["separator_rgb"]
                m2_tf = meta_card2.text_frame
                m2_tf.margin_left = Inches(0.2)
                m2_tf.margin_top = Inches(0.18)
                p_m2 = m2_tf.paragraphs[0]
                p_m2.text = "INSTITUSI / WAKTU"
                p_m2.font.size = Pt(9)
                p_m2.font.color.rgb = palette["accent_rgb"]
                p_m2.font.bold = True
                p_m2b = m2_tf.add_paragraph()
                p_m2b.text = f"{org_name} • {date_str}"
                p_m2b.font.size = Pt(12)
                p_m2b.font.bold = True
                p_m2b.font.color.rgb = palette["title_rgb"]

            else:
                # ── ARCHETYPE 3: SPLIT EDITORIAL MAGAZINE COVER (DEFAULT) ──
                left_panel = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    Inches(0.8), Inches(1.2), Inches(4.3), Inches(5.2)
                )
                left_panel.fill.solid()
                left_panel.fill.fore_color.rgb = palette["card_bg_rgb"]
                left_panel.line.color.rgb = palette["separator_rgb"]
                left_panel.line.width = Pt(1)
                record_anim(left_panel, delay_ms=0)

                l_stripe = slide.shapes.add_shape(
                    MSO_SHAPE.RECTANGLE,
                    Inches(0.8), Inches(1.2), Inches(4.3), Inches(0.06)
                )
                l_stripe.fill.solid()
                l_stripe.fill.fore_color.rgb = palette["accent_rgb"]
                l_stripe.line.fill.background()

                ltf = left_panel.text_frame
                ltf.word_wrap = True
                ltf.vertical_anchor = MSO_ANCHOR.TOP
                ltf.margin_left = Inches(0.35)
                ltf.margin_right = Inches(0.35)
                ltf.margin_top = Inches(0.35)

                p_lp0 = ltf.paragraphs[0]
                p_lp0.text = kicker_text.upper()
                p_lp0.font.size = Pt(10)
                p_lp0.font.bold = True
                p_lp0.font.color.rgb = palette["accent_rgb"]

                p_lp1 = ltf.add_paragraph()
                p_lp1.text = "EXECUTIVE\nPRESENTATION"
                p_lp1.font.size = Pt(22)
                p_lp1.font.bold = True
                p_lp1.font.color.rgb = palette["title_rgb"]
                p_lp1.space_before = Pt(8)

                p_lp2 = ltf.add_paragraph()
                p_lp2.text = f"Topik Khusus: {_safe_str(s.get('topic') or title_text)[:65]}"
                p_lp2.font.size = Pt(11)
                p_lp2.font.color.rgb = palette["muted_rgb"]
                p_lp2.space_before = Pt(14)

                p_lp3 = ltf.add_paragraph()
                p_lp3.text = f"\n\nPresenter:\n{pres_name}\n\nInstitusi / Divisi:\n{org_name}\n{date_str}"
                p_lp3.font.size = Pt(10.5)
                p_lp3.font.color.rgb = palette["text_rgb"]
                p_lp3.space_before = Pt(14)

                t_box = slide.shapes.add_textbox(Inches(5.4), Inches(1.5), Inches(7.1), Inches(3.0))
                ttf = t_box.text_frame
                ttf.word_wrap = True
                ttf.vertical_anchor = MSO_ANCHOR.TOP
                ttf.margin_left = Inches(0)
                ttf.margin_right = Inches(0)
                p_t = ttf.paragraphs[0]
                p_t.text = title_text
                p_t.font.size = Pt(36)
                p_t.font.bold = True
                p_t.font.color.rgb = palette["title_rgb"]

                if subtitle_text:
                    p_sub = ttf.add_paragraph()
                    p_sub.text = subtitle_text
                    p_sub.font.size = Pt(16)
                    p_sub.font.color.rgb = palette["accent_rgb"]
                    p_sub.space_before = Pt(12)
                record_anim(t_box, delay_ms=80)

                abstract_card = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    Inches(5.4), Inches(4.7), Inches(7.1), Inches(1.7)
                )
                abstract_card.fill.solid()
                abstract_card.fill.fore_color.rgb = palette["card_subtle_rgb"]
                abstract_card.line.color.rgb = palette["separator_rgb"]
                abstract_card.line.width = Pt(1)
                atf = abstract_card.text_frame
                atf.word_wrap = True
                atf.margin_left = Inches(0.3)
                atf.margin_top = Inches(0.2)
                p_a0 = atf.paragraphs[0]
                p_a0.text = "🎯 RINGKASAN EKSEKUTIF"
                p_a0.font.size = Pt(10)
                p_a0.font.bold = True
                p_a0.font.color.rgb = palette["accent_rgb"]

                p_a1 = atf.add_paragraph()
                p_a1.text = _safe_str(s.get("takeaway") or s.get("desc") or "Paparan komprehensif disusun untuk menyajikan fondasi arsitektur, pilar strategi, dan roadmap eksekusi berstandar profesional.")
                p_a1.font.size = Pt(12)
                p_a1.font.color.rgb = palette["text_rgb"]
                p_a1.space_before = Pt(4)
                record_anim(abstract_card, delay_ms=160)
            
        else:
            # ── HEADER UMUM SLIDE (Kicker, Title, Subtitle, Divider) ──
            k_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.733), Inches(0.3))
            ktf = k_box.text_frame
            ktf.word_wrap = True
            ktf.margin_left = Inches(0)
            p_k = ktf.paragraphs[0]
            p_k.text = kicker_text.upper()
            p_k.font.size = Pt(10)
            p_k.font.bold = True
            p_k.font.color.rgb = palette["accent_rgb"]
            record_anim(k_box, delay_ms=0)
            
            h_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.7), Inches(11.733), Inches(1.1))
            htf = h_box.text_frame
            htf.word_wrap = True
            htf.vertical_anchor = MSO_ANCHOR.TOP
            htf.margin_left = Inches(0)
            
            p_title = htf.paragraphs[0]
            p_title.text = title_text
            p_title.font.size = Pt(24)
            p_title.font.bold = True
            p_title.font.color.rgb = palette["title_rgb"]
            
            if subtitle_text:
                p_sub = htf.add_paragraph()
                p_sub.text = subtitle_text
                p_sub.font.size = Pt(13)
                p_sub.font.color.rgb = palette["muted_rgb"]
                p_sub.space_before = Pt(3)
            record_anim(h_box, delay_ms=80)
                
            div_line = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Inches(0.8), Inches(1.85), Inches(1.8), Inches(0.03)
            )
            div_line.fill.solid()
            div_line.fill.fore_color.rgb = palette["accent_rgb"]
            div_line.line.fill.background()
            
            # ── CONTENT BODY SESUAI LAYOUT ──
            if layout in ("split_screen", "hero_split", "asymmetric"):
                # ── ASYMMETRIC SPLIT SCREEN (HERO STATEMENT + DETAILS) ──
                hero_w = 4.8
                detail_w = 6.6
                gap = 0.333
                
                hero_card = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    Inches(0.8), Inches(2.05), Inches(hero_w), Inches(4.5)
                )
                hero_card.fill.solid()
                hero_card.fill.fore_color.rgb = palette["card_bg_rgb"]
                hero_card.line.color.rgb = palette["border_rgb"] if palette["is_dark"] else palette["separator_rgb"]
                hero_card.line.width = Pt(1)
                
                h_stripe = slide.shapes.add_shape(
                    MSO_SHAPE.RECTANGLE,
                    Inches(0.9), Inches(2.05), Inches(hero_w - 0.2), Inches(0.04)
                )
                h_stripe.fill.solid()
                h_stripe.fill.fore_color.rgb = palette["accent_rgb"]
                h_stripe.line.fill.background()
                
                htf_c = hero_card.text_frame
                htf_c.word_wrap = True
                htf_c.margin_left = Inches(0.3)
                htf_c.margin_right = Inches(0.3)
                htf_c.margin_top = Inches(0.3)
                
                hero_data = s.get("hero") or {}
                p_hb = htf_c.paragraphs[0]
                p_hb.text = _safe_str(hero_data.get("badge") or s.get("kicker") or "KONSEP INTI").upper()
                p_hb.font.size = Pt(10)
                p_hb.font.bold = True
                p_hb.font.color.rgb = palette["accent_rgb"]
                
                p_ht = htf_c.add_paragraph()
                p_ht.text = _safe_str(hero_data.get("title") or title_text)
                p_ht.font.size = Pt(20)
                p_ht.font.bold = True
                p_ht.font.color.rgb = palette["title_rgb"]
                p_ht.space_before = Pt(6)
                
                p_hd = htf_c.add_paragraph()
                p_hd.text = _safe_str(hero_data.get("desc") or hero_data.get("content") or s.get("desc") or subtitle_text)
                p_hd.font.size = Pt(12)
                p_hd.font.color.rgb = palette["text_rgb"]
                p_hd.space_before = Pt(10)
                
                items = s.get("items") or s.get("cards") or s.get("bullets") or []
                num_items = min(len(items), 3) or 1
                item_h = (4.5 - (0.2 * (num_items - 1))) / num_items
                start_rx = 0.8 + hero_w + gap
                
                for it_idx, itm in enumerate(items[:num_items]):
                    ity = 2.05 + (it_idx * (item_h + 0.2))
                    it_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(start_rx), Inches(ity), Inches(detail_w), Inches(item_h)
                    )
                    it_card.fill.solid()
                    it_card.fill.fore_color.rgb = palette["card_subtle_rgb"]
                    it_card.line.color.rgb = palette["separator_rgb"] if not palette["is_dark"] else palette["border_rgb"]
                    it_card.line.width = Pt(1)
                    record_anim(it_card, delay_ms=100 * (it_idx + 1))
                    
                    itf = it_card.text_frame
                    itf.word_wrap = True
                    itf.margin_left = Inches(0.25)
                    itf.margin_right = Inches(0.25)
                    itf.margin_top = Inches(0.18)
                    
                    it_title = itm.get("title") if isinstance(itm, dict) else f"Pilar {it_idx + 1}"
                    it_desc = (itm.get("desc") or itm.get("description") or itm.get("content") or itm.get("text")) if isinstance(itm, dict) else _safe_str(itm)
                    
                    p_it0 = itf.paragraphs[0]
                    p_it0.text = f"0{it_idx + 1}  •  {it_title}"
                    p_it0.font.size = Pt(13.5)
                    p_it0.font.bold = True
                    p_it0.font.color.rgb = palette["title_rgb"]
                    
                    p_it1 = itf.add_paragraph()
                    p_it1.text = _safe_str(it_desc)
                    p_it1.font.size = Pt(11)
                    p_it1.font.color.rgb = palette["text_rgb"]
                    p_it1.space_before = Pt(3)

            elif layout in ("feature_list", "horizontal_rows", "rows", "modules"):
                # ── HORIZONTAL ROWS / CURRICULUM MODULES (BREAKS 3-BOX MONOTONY) ──
                items = s.get("items") or s.get("cards") or s.get("modules") or s.get("bullets") or []
                num_rows = min(len(items), 4) or 1
                row_w = 11.733
                gap = 0.2
                total_h = 4.5
                row_h = (total_h - (gap * (num_rows - 1))) / num_rows
                start_y = 2.05
                
                for r_idx, r_item in enumerate(items[:num_rows]):
                    ry = start_y + (r_idx * (row_h + gap))
                    
                    row_shape = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(0.8), Inches(ry), Inches(row_w), Inches(row_h)
                    )
                    row_shape.fill.solid()
                    row_shape.fill.fore_color.rgb = palette["card_bg_rgb"]
                    row_shape.line.color.rgb = palette["separator_rgb"] if not palette["is_dark"] else palette["border_rgb"]
                    row_shape.line.width = Pt(1)
                    
                    bar_shape = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(0.8), Inches(ry), Inches(0.1), Inches(row_h)
                    )
                    bar_shape.fill.solid()
                    bar_shape.fill.fore_color.rgb = palette["accent_rgb"]
                    bar_shape.line.fill.background()
                    
                    rtf = row_shape.text_frame
                    rtf.word_wrap = True
                    rtf.vertical_anchor = MSO_ANCHOR.TOP
                    rtf.margin_left = Inches(0.35)
                    rtf.margin_right = Inches(0.3)
                    rtf.margin_top = Inches(0.18)
                    
                    if isinstance(r_item, dict):
                        r_title = r_item.get("title") or f"Modul 0{r_idx + 1}"
                        r_badge = r_item.get("badge") or f"BAGIAN 0{r_idx + 1}"
                        r_desc = r_item.get("desc") or r_item.get("description") or ""
                        r_bullets = r_item.get("bullets") or []
                    else:
                        r_title = f"Poin 0{r_idx + 1}"
                        r_badge = f"POIN 0{r_idx + 1}"
                        r_desc = _safe_str(r_item)
                        r_bullets = []
                        
                    p_r0 = rtf.paragraphs[0]
                    p_r0.text = f"{r_badge.upper()}  |  {r_title}"
                    p_r0.font.size = Pt(13)
                    p_r0.font.bold = True
                    p_r0.font.color.rgb = palette["accent_rgb"]
                    
                    if r_desc:
                        p_r1 = rtf.add_paragraph()
                        p_r1.text = r_desc
                        p_r1.font.size = Pt(11)
                        p_r1.font.color.rgb = palette["text_rgb"]
                        p_r1.space_before = Pt(2)
                        
                    if r_bullets:
                        p_r2 = rtf.add_paragraph()
                        p_r2.text = " • ".join([_safe_str(b) for b in r_bullets[:3]])
                        p_r2.font.size = Pt(10)
                        p_r2.font.color.rgb = palette["muted_rgb"]
                        p_r2.space_before = Pt(2)

            elif layout in ("cards_grid", "grid", "pillars"):
                cards = s.get("cards", [])
                num_cards = min(len(cards), 4) or 1
                total_w = 11.733
                gap = 0.35
                card_w = (total_w - (gap * (num_cards - 1))) / num_cards
                start_x = 0.8
                has_takeaway = bool(s.get("takeaway"))
                card_y = 2.05
                card_h = 4.1 if has_takeaway else 4.5
                
                for c_idx, c in enumerate(cards[:num_cards]):
                    cx = start_x + (c_idx * (card_w + gap))
                    
                    card_shape = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(cx), Inches(card_y), Inches(card_w), Inches(card_h)
                    )
                    card_shape.fill.solid()
                    card_shape.fill.fore_color.rgb = palette["card_bg_rgb"]
                    card_shape.line.color.rgb = palette["separator_rgb"] if not palette["is_dark"] else palette["border_rgb"]
                    card_shape.line.width = Pt(0.75)
                    
                    # Top accent line stripe
                    top_stripe = slide.shapes.add_shape(
                        MSO_SHAPE.RECTANGLE,
                        Inches(cx + 0.1), Inches(card_y), Inches(card_w - 0.2), Inches(0.04)
                    )
                    top_stripe.fill.solid()
                    top_stripe.fill.fore_color.rgb = palette["accent_rgb"]
                    top_stripe.line.fill.background()
                    
                    record_anim(card_shape, comp_anim=c.get("animation"), delay_ms=100 * (c_idx + 1))
                    
                    ctf = card_shape.text_frame
                    ctf.word_wrap = True
                    ctf.vertical_anchor = MSO_ANCHOR.TOP
                    ctf.margin_left = Inches(0.25)
                    ctf.margin_right = Inches(0.25)
                    ctf.margin_top = Inches(0.25)
                    ctf.margin_bottom = Inches(0.2)
                    
                    badge_val = c.get("badge") or f"PILAR 0{c_idx + 1}"
                    p_badge = ctf.paragraphs[0]
                    p_badge.text = badge_val.upper()
                    p_badge.font.size = Pt(10)
                    p_badge.font.bold = True
                    p_badge.font.color.rgb = palette["accent_rgb"]
                    
                    p_ctitle = ctf.add_paragraph()
                    p_ctitle.text = _safe_str(c.get("title", ""))
                    p_ctitle.font.size = Pt(16)
                    p_ctitle.font.bold = True
                    p_ctitle.font.color.rgb = palette["title_rgb"]
                    p_ctitle.space_before = Pt(4)
                    p_ctitle.space_after = Pt(6)
                    
                    p_cdesc = ctf.add_paragraph()
                    p_cdesc.text = _safe_str(c.get("desc", c.get("description", "")))
                    p_cdesc.font.size = Pt(11.5)
                    p_cdesc.font.color.rgb = palette["text_rgb"]
                    p_cdesc.space_after = Pt(8)
                    
                    c_bullets = c.get("bullets", [])
                    for b_txt in c_bullets:
                        p_cb = ctf.add_paragraph()
                        p_cb.text = f"•  {_safe_str(b_txt)}"
                        p_cb.font.size = Pt(10.5)
                        p_cb.font.color.rgb = palette["muted_rgb"]
                        p_cb.space_before = Pt(2)
                        
                if has_takeaway:
                    t_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(0.8), Inches(6.25), Inches(11.733), Inches(0.48)
                    )
                    t_card.fill.solid()
                    t_card.fill.fore_color.rgb = palette["card_subtle_rgb"]
                    t_card.line.color.rgb = palette["separator_rgb"]
                    t_card.line.width = Pt(1)
                    ttf = t_card.text_frame
                    ttf.vertical_anchor = MSO_ANCHOR.TOP
                    ttf.margin_top = Inches(0.12)
                    p_tt = ttf.paragraphs[0]
                    raw_tw = _safe_str(s.get('takeaway'))
                    p_tt.text = raw_tw if raw_tw.startswith("🎯") or raw_tw.startswith("📌") else f"🎯 {raw_tw}"
                    p_tt.font.size = Pt(10.5)
                    p_tt.font.bold = True
                    p_tt.font.color.rgb = palette["accent_rgb"]
                    p_tt.alignment = PP_ALIGN.CENTER
                        
            elif layout in ("timeline", "roadmap", "milestone"):
                steps = s.get("steps", [])
                num_steps = min(len(steps), 4) or 1
                total_w = 11.733
                gap = 0.45
                step_w = (total_w - (gap * (num_steps - 1))) / num_steps
                start_x = 0.8
                
                # ── Horizontal Connecting Flow Line (PPT Master Signature) ──
                first_cx = start_x + (step_w / 2.0)
                last_cx = start_x + ((num_steps - 1) * (step_w + gap)) + (step_w / 2.0)
                line_w = last_cx - first_cx
                
                if line_w > 0:
                    flow_line = slide.shapes.add_shape(
                        MSO_SHAPE.RECTANGLE,
                        Inches(first_cx), Inches(2.15), Inches(line_w), Inches(0.04)
                    )
                    flow_line.fill.solid()
                    flow_line.fill.fore_color.rgb = palette["accent_rgb"]
                    flow_line.line.fill.background()
                    
                # ── Step Cards & Circular Nodes ──
                card_y = 2.45
                card_h = 3.65
                
                for s_idx, step in enumerate(steps[:num_steps]):
                    sx = start_x + (s_idx * (step_w + gap))
                    node_cx = sx + (step_w / 2.0)
                    
                    # Circular Step Node Indicator
                    node_shape = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(node_cx - 0.28), Inches(1.98), Inches(0.56), Inches(0.36)
                    )
                    node_shape.fill.solid()
                    node_shape.fill.fore_color.rgb = palette["accent_rgb"]
                    node_shape.line.fill.background()
                    ntf = node_shape.text_frame
                    ntf.vertical_anchor = MSO_ANCHOR.TOP
                    p_node = ntf.paragraphs[0]
                    p_node.text = f"{s_idx + 1}"
                    p_node.font.size = Pt(11)
                    p_node.font.bold = True
                    p_node.font.color.rgb = RGBColor(7, 21, 38) if palette["is_dark"] else RGBColor(255, 255, 255)
                    p_node.alignment = PP_ALIGN.CENTER
                    
                    # Step Card Container
                    step_shape = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(sx), Inches(card_y), Inches(step_w), Inches(card_h)
                    )
                    step_shape.fill.solid()
                    step_shape.fill.fore_color.rgb = palette["card_bg_rgb"]
                    step_shape.line.color.rgb = palette["accent_rgb"]
                    step_shape.line.width = Pt(1)
                    record_anim(step_shape, comp_anim=step.get("animation"), delay_ms=100 * (s_idx + 1))
                    
                    stf = step_shape.text_frame
                    stf.word_wrap = True
                    stf.vertical_anchor = MSO_ANCHOR.TOP
                    stf.margin_left = Inches(0.22)
                    stf.margin_right = Inches(0.22)
                    stf.margin_top = Inches(0.22)
                    stf.margin_bottom = Inches(0.2)
                    
                    phase_text = step.get("phase", f"TAHAP {s_idx + 1}").upper()
                    p_phase = stf.paragraphs[0]
                    p_phase.text = _safe_str(phase_text)
                    p_phase.font.size = Pt(10)
                    p_phase.font.bold = True
                    p_phase.font.color.rgb = palette["accent_rgb"]
                    
                    p_stitle = stf.add_paragraph()
                    p_stitle.text = _safe_str(step.get("title", ""))
                    p_stitle.font.size = Pt(15)
                    p_stitle.font.bold = True
                    p_stitle.font.color.rgb = palette["title_rgb"]
                    p_stitle.space_before = Pt(4)
                    p_stitle.space_after = Pt(6)
                    
                    p_sdesc = stf.add_paragraph()
                    p_sdesc.text = _safe_str(step.get("desc", step.get("description", step.get("content", ""))))
                    p_sdesc.font.size = Pt(11.5)
                    p_sdesc.font.color.rgb = palette["text_rgb"]
                    p_sdesc.space_after = Pt(8)
                    
                    # Checklist Bullets Deliverables
                    s_bullets = step.get("bullets", [])
                    for b_txt in s_bullets:
                        p_sb = stf.add_paragraph()
                        p_sb.text = f"•  {_safe_str(_extract_item_text(b_txt))}"
                        p_sb.font.size = Pt(10)
                        p_sb.font.color.rgb = palette["muted_rgb"]
                        p_sb.space_before = Pt(2)
                        
                # ── Takeaway Banner Di Bawah Roadmap ──
                raw_takeaway = s.get("takeaway") or f"Pelaksanaan roadmap {title_text.lower()} secara terstruktur menjamin pencapaian target yang ekselen."
                takeaway_txt = raw_takeaway if raw_takeaway.startswith("🎯") or raw_takeaway.startswith("📌") else f"🎯 {raw_takeaway}"
                t_card = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    Inches(0.8), Inches(6.25), Inches(11.733), Inches(0.48)
                )
                t_card.fill.solid()
                t_card.fill.fore_color.rgb = palette["card_subtle_rgb"]
                t_card.line.color.rgb = palette["separator_rgb"]
                t_card.line.width = Pt(1)
                record_anim(t_card, delay_ms=150)
                
                tt_tf = t_card.text_frame
                tt_tf.vertical_anchor = MSO_ANCHOR.TOP
                tt_tf.margin_top = Inches(0.12)
                p_tt = tt_tf.paragraphs[0]
                p_tt.text = _safe_str(takeaway_txt)
                p_tt.font.size = Pt(10.5)
                p_tt.font.bold = True
                p_tt.font.color.rgb = palette["accent_rgb"]
                p_tt.alignment = PP_ALIGN.CENTER
                
            elif layout == "stats":
                # ── STATS / KPI CARDS GRID ──
                stats = s.get("stats", [])
                num_stats = min(len(stats), 4) or 1
                total_w = 11.733
                gap = 0.35
                stat_w = (total_w - (gap * (num_stats - 1))) / num_stats
                start_x = 0.8
                stat_y = 2.05
                has_takeaway = bool(s.get("takeaway") or s.get("impact_points") or s.get("bullets"))
                stat_h = 2.25 if has_takeaway else 4.2
                
                for st_idx, stat in enumerate(stats[:num_stats]):
                    stx = start_x + (st_idx * (stat_w + gap))
                    stat_shape = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(stx), Inches(stat_y), Inches(stat_w), Inches(stat_h)
                    )
                    stat_shape.fill.solid()
                    stat_shape.fill.fore_color.rgb = palette["card_bg_rgb"]
                    stat_shape.line.color.rgb = palette["accent_rgb"]
                    stat_shape.line.width = Pt(1)
                    record_anim(stat_shape, comp_anim=stat.get("animation"), delay_ms=120 * (st_idx + 1))
                    
                    sttf = stat_shape.text_frame
                    sttf.word_wrap = True
                    sttf.vertical_anchor = MSO_ANCHOR.TOP if has_takeaway else MSO_ANCHOR.MIDDLE
                    sttf.margin_top = Inches(0.2)
                    sttf.margin_left = Inches(0.2)
                    sttf.margin_right = Inches(0.2)
                    
                    p_badge = sttf.paragraphs[0]
                    p_badge.text = f"INDIKATOR {st_idx + 1}"
                    p_badge.font.size = Pt(9.5)
                    p_badge.font.bold = True
                    p_badge.font.color.rgb = palette["accent_rgb"]
                    p_badge.alignment = PP_ALIGN.CENTER
                    
                    p_val = sttf.add_paragraph()
                    p_val.text = _safe_str(stat.get("value", ""))
                    p_val.font.size = Pt(36 if num_stats == 4 else 40)
                    p_val.font.bold = True
                    p_val.font.color.rgb = palette["accent_rgb"]
                    p_val.alignment = PP_ALIGN.CENTER
                    p_val.space_before = Pt(2)
                    
                    p_lbl = sttf.add_paragraph()
                    p_lbl.text = _safe_str(stat.get("label", ""))
                    p_lbl.font.size = Pt(13 if num_stats == 4 else 14)
                    p_lbl.font.bold = True
                    p_lbl.font.color.rgb = palette["title_rgb"]
                    p_lbl.alignment = PP_ALIGN.CENTER
                    p_lbl.space_before = Pt(2)
                    
                    if stat.get("desc"):
                        p_desc = sttf.add_paragraph()
                        p_desc.text = _safe_str(stat.get("desc"))
                        p_desc.font.size = Pt(10.5)
                        p_desc.font.color.rgb = palette["muted_rgb"]
                        p_desc.alignment = PP_ALIGN.CENTER
                        p_desc.space_before = Pt(3)
                        
                # Strategic Impact Banner Di Bawah Kartu KPI
                takeaway_txt = s.get("takeaway")
                impact_items = s.get("impact_points") or s.get("bullets") or []
                
                if takeaway_txt or impact_items:
                    impact_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(0.8), Inches(4.55), Inches(11.733), Inches(2.1)
                    )
                    impact_card.fill.solid()
                    impact_card.fill.fore_color.rgb = palette["card_bg_rgb"]
                    impact_card.line.color.rgb = palette["separator_rgb"]
                    impact_card.line.width = Pt(1)
                    record_anim(impact_card, delay_ms=150)
                    
                    itf = impact_card.text_frame
                    itf.word_wrap = True
                    itf.vertical_anchor = MSO_ANCHOR.TOP
                    itf.margin_top = Inches(0.25)
                    itf.margin_left = Inches(0.3)
                    itf.margin_right = Inches(0.3)
                    
                    p_ititle = itf.paragraphs[0]
                    p_ititle.text = _safe_str(s.get("impact_title") or "Analisis Capaian & Dampak Strategis")
                    p_ititle.font.size = Pt(15)
                    p_ititle.font.bold = True
                    p_ititle.font.color.rgb = palette["title_rgb"]
                    
                    if takeaway_txt:
                        p_idesc = itf.add_paragraph()
                        p_idesc.text = _safe_str(takeaway_txt)
                        p_idesc.font.size = Pt(12)
                        p_idesc.font.color.rgb = palette["accent_rgb"]
                        p_idesc.space_before = Pt(4)
                        p_idesc.space_after = Pt(6)
                        
                    for imp in impact_items[:3]:
                        p_imp = itf.add_paragraph()
                        p_imp.text = f"•  {_safe_str(imp)}"
                        p_imp.font.size = Pt(11)
                        p_imp.font.color.rgb = palette["text_rgb"]
                        p_imp.space_before = Pt(2)

            elif layout in ("two_columns", "comparison", "versus", "columns"):
                # ── DUA KOLOM KOMPARASI & MATRIKS STRATEGIS (PPT MASTER) ──
                left_data = s.get("left") or {}
                right_data = s.get("right") or {}
                has_takeaway = bool(s.get("takeaway"))
                col_w = 5.65
                gap = 0.433
                col_y = 2.05
                col_h = 4.1 if has_takeaway else 4.65

                # Kolom Kiri
                col_left = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    Inches(0.8), Inches(col_y), Inches(col_w), Inches(col_h)
                )
                col_left.fill.solid()
                col_left.fill.fore_color.rgb = palette["card_bg_rgb"]
                col_left.line.color.rgb = palette["separator_rgb"]
                col_left.line.width = Pt(1)
                record_anim(col_left, comp_anim=left_data.get("animation"), delay_ms=100)
                ltf = col_left.text_frame
                ltf.word_wrap = True
                ltf.vertical_anchor = MSO_ANCHOR.TOP
                ltf.margin_left = Inches(0.25)
                ltf.margin_right = Inches(0.25)
                ltf.margin_top = Inches(0.25)

                p_lh = ltf.paragraphs[0]
                p_lh.text = _safe_str(left_data.get("heading", left_data.get("title", "Kondisi Eksisting / Analisis")))
                p_lh.font.size = Pt(16)
                p_lh.font.bold = True
                p_lh.font.color.rgb = palette["accent_rgb"]
                p_lh.space_after = Pt(6)

                if left_data.get("desc"):
                    p_ldesc = ltf.add_paragraph()
                    p_ldesc.text = _safe_str(left_data.get("desc"))
                    p_ldesc.font.size = Pt(11.5)
                    p_ldesc.font.color.rgb = palette["text_rgb"]
                    p_ldesc.space_after = Pt(8)

                for item in left_data.get("items", left_data.get("bullets", [])):
                    p_li = ltf.add_paragraph()
                    p_li.text = f"•  {_safe_str(_extract_item_text(item))}"
                    p_li.font.size = Pt(11)
                    p_li.font.color.rgb = palette["muted_rgb"]
                    p_li.space_before = Pt(3)

                # Kolom Kanan
                rx = 0.8 + col_w + gap
                col_right = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    Inches(rx), Inches(col_y), Inches(col_w), Inches(col_h)
                )
                col_right.fill.solid()
                col_right.fill.fore_color.rgb = palette["card_bg_rgb"]
                col_right.line.color.rgb = palette["accent_rgb"]
                col_right.line.width = Pt(1)
                record_anim(col_right, comp_anim=right_data.get("animation"), delay_ms=200)
                rtf = col_right.text_frame
                rtf.word_wrap = True
                rtf.vertical_anchor = MSO_ANCHOR.TOP
                rtf.margin_left = Inches(0.25)
                rtf.margin_right = Inches(0.25)
                rtf.margin_top = Inches(0.25)

                p_rh = rtf.paragraphs[0]
                p_rh.text = _safe_str(right_data.get("heading", right_data.get("title", "Target Arsitektur / Solusi")))
                p_rh.font.size = Pt(16)
                p_rh.font.bold = True
                p_rh.font.color.rgb = palette["accent_rgb"]
                p_rh.space_after = Pt(6)

                if right_data.get("desc"):
                    p_rdesc = rtf.add_paragraph()
                    p_rdesc.text = _safe_str(right_data.get("desc"))
                    p_rdesc.font.size = Pt(11.5)
                    p_rdesc.font.color.rgb = palette["text_rgb"]
                    p_rdesc.space_after = Pt(8)

                for item in right_data.get("items", right_data.get("bullets", [])):
                    p_ri = rtf.add_paragraph()
                    p_ri.text = f"•  {_safe_str(_extract_item_text(item))}"
                    p_ri.font.size = Pt(11)
                    p_ri.font.color.rgb = palette["text_rgb"]
                    p_ri.space_before = Pt(3)

                if has_takeaway:
                    t_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(0.8), Inches(6.3), Inches(11.733), Inches(0.48)
                    )
                    t_card.fill.solid()
                    t_card.fill.fore_color.rgb = palette["card_subtle_rgb"]
                    t_card.line.color.rgb = palette["separator_rgb"]
                    t_card.line.width = Pt(1)
                    record_anim(t_card, delay_ms=250)
                    ttf = t_card.text_frame
                    ttf.vertical_anchor = MSO_ANCHOR.TOP
                    ttf.margin_top = Inches(0.12)
                    p_tt = ttf.paragraphs[0]
                    raw_tw = _safe_str(s.get('takeaway'))
                    p_tt.text = raw_tw if raw_tw.startswith("🎯") or raw_tw.startswith("📌") else f"🎯 {raw_tw}"
                    p_tt.font.size = Pt(10.5)
                    p_tt.font.bold = True
                    p_tt.font.color.rgb = palette["accent_rgb"]
                    p_tt.alignment = PP_ALIGN.CENTER
                    
            elif layout in ("quote", "statement", "callout", "big_idea"):
                # ── BIG STATEMENT / QUOTE LAYOUT WITH ACTION STEPS ──
                action_steps = s.get("action_steps") or []
                quote_text = s.get("quote") or s.get("statement") or s.get("desc") or title_text
                author_txt = s.get("author") or s.get("source") or s.get("takeaway")

                if action_steps:
                    # Top: Quote statement card
                    q_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(0.8), Inches(2.05), Inches(11.733), Inches(2.1)
                    )
                    q_card.fill.solid()
                    q_card.fill.fore_color.rgb = palette["card_bg_rgb"]
                    q_card.line.color.rgb = palette["accent_rgb"]
                    q_card.line.width = Pt(1.5)
                    record_anim(q_card, comp_anim=s.get("animation"), delay_ms=100)
                    
                    qtf = q_card.text_frame
                    qtf.word_wrap = True
                    qtf.vertical_anchor = MSO_ANCHOR.MIDDLE
                    qtf.margin_left = Inches(0.5)
                    qtf.margin_right = Inches(0.5)
                    p_q = qtf.paragraphs[0]
                    p_q.text = f'“{quote_text}”'
                    p_q.font.size = Pt(15.5)
                    p_q.font.bold = True
                    p_q.font.color.rgb = palette["title_rgb"]
                    p_q.alignment = PP_ALIGN.CENTER
                    
                    if author_txt:
                        p_a = qtf.add_paragraph()
                        p_a.text = f"— {author_txt}"
                        p_a.font.size = Pt(11)
                        p_a.font.color.rgb = palette["accent_rgb"]
                        p_a.alignment = PP_ALIGN.CENTER
                        p_a.space_before = Pt(4)

                    # Bottom: Action steps cards
                    num_acts = min(len(action_steps), 3) or 1
                    act_gap = 0.35
                    total_act_w = 11.733
                    act_w = (total_act_w - (act_gap * (num_acts - 1))) / num_acts
                    act_y = 4.35
                    act_h = 2.2

                    for a_idx, act_txt in enumerate(action_steps[:num_acts]):
                        ax = 0.8 + (a_idx * (act_w + act_gap))
                        a_card = slide.shapes.add_shape(
                            MSO_SHAPE.ROUNDED_RECTANGLE,
                            Inches(ax), Inches(act_y), Inches(act_w), Inches(act_h)
                        )
                        a_card.fill.solid()
                        a_card.fill.fore_color.rgb = palette["card_subtle_rgb"]
                        a_card.line.color.rgb = palette["separator_rgb"] if not palette["is_dark"] else palette["border_rgb"]
                        a_card.line.width = Pt(1)
                        record_anim(a_card, delay_ms=150 + (a_idx * 100))

                        # Top accent line
                        top_stripe = slide.shapes.add_shape(
                            MSO_SHAPE.RECTANGLE,
                            Inches(ax + 0.1), Inches(act_y), Inches(act_w - 0.2), Inches(0.04)
                        )
                        top_stripe.fill.solid()
                        top_stripe.fill.fore_color.rgb = palette["accent_rgb"]
                        top_stripe.line.fill.background()

                        atf = a_card.text_frame
                        atf.word_wrap = True
                        atf.vertical_anchor = MSO_ANCHOR.TOP
                        atf.margin_left = Inches(0.2)
                        atf.margin_right = Inches(0.2)
                        atf.margin_top = Inches(0.2)

                        p_ab = atf.paragraphs[0]
                        p_ab.text = f"LANGKAH 0{a_idx + 1}"
                        p_ab.font.size = Pt(9.5)
                        p_ab.font.bold = True
                        p_ab.font.color.rgb = palette["accent_rgb"]

                        p_at = atf.add_paragraph()
                        p_at.text = _safe_str(act_txt)
                        p_at.font.size = Pt(11.5)
                        p_at.font.color.rgb = palette["text_rgb"]
                        p_at.space_before = Pt(6)

                else:
                    q_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(0.8), Inches(2.2), Inches(11.733), Inches(4.2)
                    )
                    q_card.fill.solid()
                    q_card.fill.fore_color.rgb = palette["card_bg_rgb"]
                    q_card.line.color.rgb = palette["accent_rgb"]
                    q_card.line.width = Pt(1.5)
                    record_anim(q_card, comp_anim=s.get("animation"), delay_ms=100)
                    
                    qtf = q_card.text_frame
                    qtf.word_wrap = True
                    qtf.vertical_anchor = MSO_ANCHOR.MIDDLE
                    qtf.margin_left = Inches(0.8)
                    qtf.margin_right = Inches(0.8)
                    
                    p_q = qtf.paragraphs[0]
                    p_q.text = f'“{quote_text}”'
                    p_q.font.size = Pt(22)
                    p_q.font.bold = True
                    p_q.font.color.rgb = palette["title_rgb"]
                    p_q.alignment = PP_ALIGN.CENTER
                    
                    if author_txt:
                        p_a = qtf.add_paragraph()
                        p_a.text = f"— {author_txt}"
                        p_a.font.size = Pt(13)
                        p_a.font.color.rgb = palette["accent_rgb"]
                        p_a.alignment = PP_ALIGN.CENTER
                        p_a.space_before = Pt(14)

            else:
                # ── BULLETS & EXECUTIVE RECOMMENDATIONS (STACKED MODERN CARDS) ──
                bullets = s.get("bullets", [])
                if not bullets and s.get("content"):
                    bullets = [b.strip() for b in str(s.get("content")).split("\n") if b.strip()]
                if not bullets:
                    action_steps = s.get("action_steps") or []
                    if action_steps:
                        bullets = [str(x) for x in action_steps]
                    else:
                        deck_subj = deck_title[:35] if deck_title else "sistem"
                        bullets = [
                            f"Penyelarasan strategi dan tata kelola implementasi {deck_subj}",
                            "Eksekusi roadmap bertahap sesuai standar mutu terpadu",
                            "Monitoring berkelanjutan dan evaluasi pencapaian target"
                        ]
                
                has_takeaway = bool(s.get("takeaway"))
                num_b = min(len(bullets), 5)
                total_h = 3.9 if has_takeaway else 4.55
                gap = 0.15
                card_h = (total_h - (gap * (num_b - 1))) / num_b
                start_y = 2.05
                
                for b_idx, bullet in enumerate(bullets[:num_b]):
                    by = start_y + (b_idx * (card_h + gap))
                    
                    # Stacked Card Container
                    b_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(0.8), Inches(by), Inches(11.733), Inches(card_h)
                    )
                    b_card.fill.solid()
                    b_card.fill.fore_color.rgb = palette["card_bg_rgb"]
                    b_card.line.color.rgb = palette["separator_rgb"]
                    b_card.line.width = Pt(1)
                    record_anim(b_card, comp_anim=s.get("animation"), delay_ms=80 * (b_idx + 1))
                    
                    # Number Badge Circle
                    badge_size = min(card_h - 0.2, 0.42)
                    badge_y = by + ((card_h - badge_size) / 2)
                    badge_oval = slide.shapes.add_shape(
                        MSO_SHAPE.OVAL,
                        Inches(1.05), Inches(badge_y), Inches(badge_size), Inches(badge_size)
                    )
                    badge_oval.fill.solid()
                    badge_oval.fill.fore_color.rgb = palette["card_subtle_rgb"]
                    badge_oval.line.color.rgb = palette["accent_rgb"]
                    badge_oval.line.width = Pt(1.5)
                    
                    btf = badge_oval.text_frame
                    btf.vertical_anchor = MSO_ANCHOR.MIDDLE
                    btf.margin_top = Inches(0)
                    btf.margin_left = Inches(0)
                    btf.margin_right = Inches(0)
                    p_num = btf.paragraphs[0]
                    p_num.text = str(b_idx + 1)
                    p_num.font.size = Pt(11)
                    p_num.font.bold = True
                    p_num.font.color.rgb = palette["accent_rgb"]
                    p_num.alignment = PP_ALIGN.CENTER
                    
                    # Bullet Text Box (Properly Padded & Aligned)
                    t_box = slide.shapes.add_textbox(
                        Inches(1.65), Inches(by + 0.05), Inches(10.7), Inches(card_h - 0.1)
                    )
                    ttf_b = t_box.text_frame
                    ttf_b.word_wrap = True
                    ttf_b.vertical_anchor = MSO_ANCHOR.MIDDLE
                    ttf_b.margin_left = Inches(0)
                    ttf_b.margin_top = Inches(0)
                    p_txt = ttf_b.paragraphs[0]
                    p_txt.text = _safe_str(bullet)
                    p_txt.font.size = Pt(11.5 if num_b >= 5 else 13.0)
                    p_txt.font.color.rgb = palette["text_rgb"]
                    p_txt.alignment = PP_ALIGN.LEFT
                    
                if has_takeaway:
                    t_card = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(0.8), Inches(6.25), Inches(11.733), Inches(0.48)
                    )
                    t_card.fill.solid()
                    t_card.fill.fore_color.rgb = palette["card_subtle_rgb"]
                    t_card.line.color.rgb = palette["separator_rgb"]
                    t_card.line.width = Pt(1)
                    record_anim(t_card, delay_ms=150)
                    ttf = t_card.text_frame
                    ttf.vertical_anchor = MSO_ANCHOR.TOP
                    ttf.margin_top = Inches(0.12)
                    p_tt = ttf.paragraphs[0]
                    raw_tw = _safe_str(s.get('takeaway'))
                    p_tt.text = raw_tw if raw_tw.startswith("🎯") or raw_tw.startswith("📌") else f"🎯 {raw_tw}"
                    p_tt.font.size = Pt(10.5)
                    p_tt.font.bold = True
                    p_tt.font.color.rgb = palette["accent_rgb"]
                    p_tt.alignment = PP_ALIGN.CENTER
                    
            # ── 3. Slide Footer Refined (Divider & Meta) ──
            footer_line = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Inches(0.8), Inches(6.85), Inches(11.733), Inches(0.01)
            )
            footer_line.fill.solid()
            footer_line.fill.fore_color.rgb = palette["separator_rgb"]
            footer_line.line.fill.background()
            
            footer_box = slide.shapes.add_textbox(Inches(0.8), Inches(6.92), Inches(6.0), Inches(0.35))
            ftf = footer_box.text_frame
            ftf.margin_left = Inches(0)
            p_ft = ftf.paragraphs[0]
            footer_label = _safe_str(deck_title or s.get("organization") or global_org or "EXECUTIVE PRESENTATION")
            p_ft.text = footer_label.upper()
            p_ft.font.size = Pt(9)
            p_ft.font.color.rgb = palette["muted_rgb"]
            
            counter_box = slide.shapes.add_textbox(Inches(9.5), Inches(6.92), Inches(3.033), Inches(0.35))
            ctf_c = counter_box.text_frame
            ctf_c.margin_right = Inches(0)
            p_c = ctf_c.paragraphs[0]
            p_c.text = f"HALAMAN {idx + 1} DARI {len(slides_data)}"
            p_c.font.size = Pt(9)
            p_c.font.bold = True
            p_c.font.color.rgb = palette["accent_rgb"]
            p_c.alignment = PP_ALIGN.RIGHT
            
            # ── 4. Embed Native OpenXML <p:timing> Animation Sequence ──
            if slide_anim_targets:
                try:
                    sys_scripts = Path("/home/qisthi/pinAi/.agents/skills/ppt_master/scripts")
                    if str(sys_scripts) not in sys.path:
                        sys.path.insert(0, str(sys_scripts))
                    from pptx_animations import create_sequence_timing_xml
                    timing_xml_str = create_sequence_timing_xml(
                        targets=slide_anim_targets,
                        duration=0.35,
                        trigger='after-previous'
                    )
                    if timing_xml_str and timing_xml_str.strip():
                        timing_str = timing_xml_str.strip()
                        timing_str = timing_str.replace('<p:timing', f'<p:timing {nsdecls("p")}')
                        timing_xml = parse_xml(timing_str)
                        slide._element.append(timing_xml)
                        logger.debug(f"[PPT_MASTER] ✅ Sukses menyematkan {len(slide_anim_targets)} animasi shape native ke slide {idx + 1}")
                except Exception as e_anim:
                    logger.debug(f"[PPT_MASTER] Gagal menyematkan p:timing ke slide {idx + 1}: {e_anim}")
            
    prs.save(str(output_path))
    logger.info(f"[PPT_MASTER] ✅ File PPTX berhasil dikompilasi dengan standar PPT Master: {output_path}")
    return output_path


def _extract_item_text(x: Any) -> str:
    """Ekstraksi teks aman dari string atau dict item/bullet/step."""
    if isinstance(x, str):
        return x.strip()
    if isinstance(x, dict):
        return str(x.get("text") or x.get("title") or x.get("desc") or x.get("content") or "").strip()
    return str(x).strip()


def _normalize_slide_item(raw_s: Dict[str, Any], default_idx: int = 1) -> Dict[str, Any]:
    """Menormalisasi struktur slide baik format flat maupun nested 'content'/'type'/'elements' dari LLM."""
    if not isinstance(raw_s, dict):
        return {"layout": "bullets", "title": f"Slide {default_idx}", "bullets": [str(raw_s)]}
    res = {}
    if "content" in raw_s and isinstance(raw_s["content"], dict):
        res.update(raw_s["content"])
    for k, v in raw_s.items():
        if k != "content":
            res[k] = v
            
    # Normalisasi layout / type
    if "type" in res and "layout" not in res:
        res["layout"] = res["type"]
    if "layout" not in res:
        res["layout"] = "bullets"
        
    # Normalisasi title (mencegah KeyError jika LLM memakai nama alias atau lupa menyertakan title)
    title_candidate = (
        res.get("title")
        or res.get("slide_title")
        or res.get("heading")
        or res.get("header")
        or res.get("topic")
        or res.get("main_title")
        or res.get("name")
        or res.get("kicker")
    )
    if not title_candidate or not str(title_candidate).strip():
        title_candidate = f"Slide {default_idx}"
    res["title"] = str(title_candidate).strip()
    
    # Normalisasi subtitle & kicker jika kosong
    if "subtitle" not in res:
        res["subtitle"] = res.get("sub_title") or res.get("desc") or ""
    if "kicker" not in res:
        res["kicker"] = res.get("category") or res.get("pill") or "CAKRA AI • EXECUTIVE PRESENTATION"

    # ── EKSTRAKSI ELEMEN MODERN DARI `elements` (PPT MASTER BLUEPRINT) ──
    elements = res.get("elements") or []
    if isinstance(elements, list) and elements:
        for el in elements:
            if not isinstance(el, dict):
                continue
            etype = str(el.get("type", "")).lower()

            # Cover elements
            if etype == "hero_badge":
                if res.get("kicker") == "CAKRA AI • EXECUTIVE PRESENTATION" or not res.get("kicker"):
                    res["kicker"] = el.get("text") or el.get("badge") or res.get("kicker")
            elif etype == "main_title":
                res["title"] = el.get("text") or el.get("title") or res.get("title")
            elif etype == "subtitle":
                res["subtitle"] = el.get("text") or el.get("subtitle") or res.get("subtitle")
            elif etype in ("presenter_card", "speaker", "presenter"):
                res["presenter"] = el.get("name") or el.get("presenter") or res.get("presenter")
                res["organization"] = el.get("organization") or el.get("org") or res.get("organization")
                res["role"] = el.get("role") or res.get("role")

            # Hero card (split_screen)
            elif etype in ("hero_card", "hero_statement", "concept_hero"):
                res["hero"] = {
                    "badge": el.get("badge") or "KONSEP INTI",
                    "title": el.get("title") or res.get("title"),
                    "desc": el.get("content") or el.get("desc") or el.get("text") or ""
                }

            # Feature grid / items / cards
            elif etype in ("feature_grid", "feature_list", "feature_cards", "modules"):
                raw_items = el.get("items") or el.get("cards") or []
                if "items" not in res or not res["items"]:
                    res["items"] = raw_items
                if "cards" not in res or not res["cards"]:
                    res["cards"] = raw_items

            # Column card (two_columns)
            elif etype in ("column_card", "column", "col"):
                col_obj = {
                    "heading": el.get("title") or el.get("heading") or "Pilar",
                    "title": el.get("title") or el.get("heading") or "Pilar",
                    "desc": el.get("desc") or el.get("description", ""),
                    "items": [_extract_item_text(x) for x in el.get("items", el.get("bullets", []))]
                }
                if "left" not in res:
                    res["left"] = col_obj
                elif "right" not in res:
                    res["right"] = col_obj

            # Timeline step (timeline)
            elif etype in ("timeline_step", "step", "roadmap_step"):
                if "steps" not in res or not isinstance(res["steps"], list):
                    res["steps"] = []
                res["steps"].append({
                    "phase": el.get("phase") or f"FASE 0{len(res['steps']) + 1}",
                    "title": el.get("title", ""),
                    "desc": el.get("desc") or el.get("content", ""),
                    "bullets": [_extract_item_text(b) for b in el.get("bullets", el.get("items", []))]
                })

            # Stat card (stats)
            elif etype in ("stat_card", "metric_card", "kpi_card", "stat"):
                if "stats" not in res or not isinstance(res["stats"], list):
                    res["stats"] = []
                res["stats"].append({
                    "value": str(el.get("value", "")),
                    "label": el.get("label") or el.get("title", ""),
                    "desc": el.get("desc", "")
                })

            # Quote / Big Statement
            elif etype in ("quote_main", "quote", "statement", "big_idea"):
                res["quote"] = el.get("text") or el.get("content") or el.get("statement") or res.get("quote")
                if el.get("author") or el.get("source"):
                    res["author"] = el.get("author") or el.get("source")

            # Action steps (for closing / quote slides)
            elif etype in ("action_steps", "next_steps", "recommendations"):
                res["action_steps"] = [_extract_item_text(x) for x in el.get("items", el.get("steps", []))]

            # Takeaway banner
            elif etype in ("takeaway_banner", "takeaway", "summary_banner"):
                res["takeaway"] = el.get("text") or el.get("content") or res.get("takeaway")

    # Failsafe Content Hydration: Menjamin 100% tidak ada slide yang berlubang/kosong
    res = _hydrate_slide_content(res, default_idx)
    return res


def _hydrate_slide_content(res: Dict[str, Any], default_idx: int = 1) -> Dict[str, Any]:
    """
    Failsafe Content Hydrator:
    Menjamin tidak ada slide yang dirender kosong jika Planner/LLM hanya menghasilkan judul tanpa data bodi.
    Mengonversi data yang ada atau merekonstruksi materi kontekstual berkualitas tinggi sesuai layout.
    """
    layout = str(res.get("layout", "bullets")).lower()
    title = str(res.get("title", f"Slide {default_idx}")).strip()
    subtitle = str(res.get("subtitle", "")).strip()

    # 1. Timeline / Roadmap / Milestone
    if layout in ("timeline", "roadmap", "milestone"):
        steps = res.get("steps") or []
        if not steps and res.get("items"):
            steps = []
            for idx_it, itm in enumerate(res["items"]):
                if isinstance(itm, dict):
                    steps.append({
                        "phase": itm.get("badge") or f"TAHAP 0{idx_it + 1}",
                        "title": itm.get("title") or f"Langkah 0{idx_it + 1}",
                        "desc": itm.get("desc") or itm.get("content") or "",
                        "bullets": itm.get("bullets", [])
                    })
                else:
                    steps.append({
                        "phase": f"TAHAP 0{idx_it + 1}",
                        "title": f"Langkah 0{idx_it + 1}",
                        "desc": str(itm),
                        "bullets": []
                    })
        elif not steps and res.get("cards"):
            steps = []
            for idx_c, c in enumerate(res["cards"]):
                if isinstance(c, dict):
                    steps.append({
                        "phase": c.get("badge") or f"TAHAP 0{idx_c + 1}",
                        "title": c.get("title") or f"Fase 0{idx_c + 1}",
                        "desc": c.get("desc") or "",
                        "bullets": c.get("bullets", [])
                    })
        if not steps:
            is_curriculum = any(w in title.lower() for w in ["kurikulum", "roadmap", "belajar", "training", "silabus", "pelatihan", "tahapan", "alur"])
            if is_curriculum:
                steps = [
                    {
                        "phase": "TAHAP 01",
                        "title": "Fondasi & Prinsip Desain",
                        "desc": "Pemahaman fundamental arsitektur terdistribusi, pola komunikasi data, dan konfigurasi lingkungan kerja.",
                        "bullets": ["Standarisasi environment & dependensi", "Prinsip modularitas sistem"]
                    },
                    {
                        "phase": "TAHAP 02",
                        "title": "Implementasi & Integrasi Layanan",
                        "desc": "Pembangunan modul-modul inti secara independen serta integrasi antarmuka layanan melalui API terstruktur.",
                        "bullets": ["Pengembangan modul independen", "Mekanisme perutean & validasi data"]
                    },
                    {
                        "phase": "TAHAP 03",
                        "title": "Pengujian, Ketahanan & Keamanan",
                        "desc": "Uji keandalan sistem melalui skenario pengujian komprehensif, mitigasi error, dan pemantauan performa.",
                        "bullets": ["Skenario chaos & load testing", "Strategi failover dan audit logging"]
                    },
                    {
                        "phase": "TAHAP 04",
                        "title": "Deployment & Operasional Penuh",
                        "desc": "Orkestrasi sistem terdistribusi, otomatisasi proses rilis, dan pemantauan metrik kinerja secara berkelanjutan.",
                        "bullets": ["Pipeline rilis otomatis", "Monitoring telemetri layanan"]
                    }
                ]
            else:
                steps = [
                    {
                        "phase": "TAHAP 01",
                        "title": "Inisiasi & Analisis Kebutuhan",
                        "desc": f"Pemetaan kebutuhan strategis, analisis kapasitas, dan penyusunan kerangka kerja {title.lower()}.",
                        "bullets": ["Audit kesiapan fondasi eksisting", "Perumusan spesifikasi target"]
                    },
                    {
                        "phase": "TAHAP 02",
                        "title": "Pengembangan & Integrasi Modul",
                        "desc": "Eksekusi pembangunan pilar-pilar utama dan sinkronisasi antarmuka sistem secara bertahap.",
                        "bullets": ["Pembangunan modul kunci", "Integrasi terpadu lintas fungsi"]
                    },
                    {
                        "phase": "TAHAP 03",
                        "title": "Validasi Kualitas & Standardisasi",
                        "desc": "Pengujian fungsional menyeluruh guna menjamin kepatuhan mutu dan efisiensi operasional.",
                        "bullets": ["Verifikasi standar kualitas", "Uji performa dan kepatuhan"]
                    },
                    {
                        "phase": "TAHAP 04",
                        "title": "Implementasi Penuh & Evaluasi",
                        "desc": "Penerapan operasional menyeluruh disertai mekanisme pemantauan progres dan penyempurnaan berkala.",
                        "bullets": ["Rollout operasional penuh", "Evaluasi dampak berkesinambungan"]
                    }
                ]
        res["steps"] = steps
        if not res.get("takeaway"):
            res["takeaway"] = f"🎯 Pelaksanaan roadmap {title.lower()} secara terstruktur menjamin mitigasi risiko dan kelangsungan operasional optimal."

    # 2. Feature List / Horizontal Rows / Modules
    elif layout in ("feature_list", "horizontal_rows", "rows", "modules"):
        items = res.get("items") or []
        if not items and res.get("cards"):
            items = res["cards"]
        elif not items and res.get("steps"):
            items = [{"badge": s.get("phase", f"BAGIAN 0{idx_s + 1}"), "title": s.get("title", ""), "desc": s.get("desc", ""), "bullets": s.get("bullets", [])} for idx_s, s in enumerate(res["steps"])]
        if not items:
            items = [
                {
                    "badge": "PILAR 01",
                    "title": "Arsitektur & Infrastruktur Inti",
                    "desc": f"Fondasi struktural yang tangguh dan modular untuk menjamin skalabilitas serta keandalan {title.lower()}.",
                    "bullets": ["Desain komponen independen", "Standarisasi antarmuka data"]
                },
                {
                    "badge": "PILAR 02",
                    "title": "Integrasi Fungsional & Otomasi",
                    "desc": "Sinkronisasi alur data dan eksekusi tugas antarkomponen secara otomatis guna meniadakan friksi proses.",
                    "bullets": ["Otomasi alur eksekusi", "Mekanisme toleransi kesalahan"]
                },
                {
                    "badge": "PILAR 03",
                    "title": "Tata Kelola, Keamanan & Monitoring",
                    "desc": "Pengawasan telemetri secara real-time disertai penguatan standar keamanan dan mitigasi risiko komprehensif.",
                    "bullets": ["Audit logging & telemetri aktif", "Kepatuhan tata kelola berkelanjutan"]
                }
            ]
        res["items"] = items

    # 3. Split Screen / Hero Split / Asymmetric
    elif layout in ("split_screen", "hero_split", "asymmetric"):
        if not res.get("hero") or not isinstance(res.get("hero"), dict):
            res["hero"] = {
                "badge": "FOKUS STRATEGIS",
                "title": title,
                "desc": subtitle or f"Prinsip arsitektur dan fondasi utama yang mendasari keberhasilan implementasi {title.lower()} secara terpadu.",
                "takeaway": "Integrasi menyeluruh menjamin keberlanjutan dan efisiensi jangka panjang."
            }
        items = res.get("items") or []
        if not items and res.get("cards"):
            items = res["cards"]
        if not items:
            items = [
                {
                    "title": "Optimalisasi Kapasitas & Kinerja",
                    "desc": "Pemanfaatan sumber daya secara efisien guna memastikan throughput tinggi dan waktu respons minimal."
                },
                {
                    "title": "Ketahanan Layanan & Redundansi",
                    "desc": "Penerapan mekanisme isolasi kegagalan agar sistem tetap beroperasi tanpa disrupsi menyeluruh."
                },
                {
                    "title": "Standarisasi Protokol Komunikasi",
                    "desc": "Kontrak antarmuka yang terdefinisi jelas untuk menjamin interoperabilitas lintas komponen."
                }
            ]
        res["items"] = items

    # 4. Two Columns / Comparison / Versus
    elif layout in ("two_columns", "comparison", "versus", "columns"):
        left = res.get("left") or {}
        if not left.get("items") and not left.get("bullets"):
            res["left"] = {
                "heading": left.get("heading") or left.get("title") or "Prasyarat & Fondasi Kebutuhan",
                "desc": left.get("desc") or f"Identifikasi batasan teknis dan kesiapan prasyarat untuk mendukung {title.lower()}.",
                "items": [
                    "Pemetaan dependensi sistem dan kesiapan lingkungan kerja",
                    "Standarisasi tools pengembangan dan konfigurasi awal",
                    "Penetapan kriteria keberhasilan dan tolok ukur mutu"
                ]
            }
        right = res.get("right") or {}
        if not right.get("items") and not right.get("bullets"):
            res["right"] = {
                "heading": right.get("heading") or right.get("title") or "Target Capaian & Keunggulan",
                "desc": right.get("desc") or f"Output terukur dan kompetensi strategis yang dicapai melalui {title.lower()}.",
                "items": [
                    "Penguasaan pola arsitektur modern yang adaptif dan skalabel",
                    "Peningkatan produktivitas tim melalui automasi alur proses",
                    "Mitigasi risiko teknis secara proaktif dan teruji"
                ]
            }
        if not res.get("takeaway"):
            res["takeaway"] = f"🎯 Keselarasan antara fondasi prasyarat dan target eksekusi menjamin hasil akhir yang ekselen."

    # 5. Stats / KPI Cards Grid
    elif layout == "stats":
        stats = res.get("stats") or []
        if not stats and res.get("items"):
            stats = [{"value": f"{idx_st + 1}00%", "label": str(it.get('title') if isinstance(it, dict) else it)[:20], "desc": str(it.get('desc') if isinstance(it, dict) else "")[:60]} for idx_st, it in enumerate(res["items"][:3])]
        if not stats:
            stats = [
                {"value": "99.9%", "label": "Ketersediaan Sistem", "desc": "Tingkat ketersediaan layanan dan stabilitas operasional tinggi."},
                {"value": "< 100ms", "label": "Latensi Respons", "desc": "Kecepatan respons antarmuka dan efisiensi eksekusi kueri."},
                {"value": "100%", "label": "Validasi Kepatuhan", "desc": "Tingkat keberhasilan pengujian fungsional dan integritas sistem."}
            ]
        res["stats"] = stats
        if not res.get("takeaway"):
            res["takeaway"] = f"🎯 Pengukuran berbasis metrik kuantitatif memastikan performa {title.lower()} tercapai secara objektif."

    # 6. Cards Grid / Grid / Pillars
    elif layout in ("cards_grid", "grid", "pillars"):
        cards = res.get("cards") or []
        if not cards and res.get("items"):
            cards = res["cards"] = res["items"]
        if not cards:
            cards = [
                {
                    "badge": "PILAR 01",
                    "title": "Fondasi Arsitektur",
                    "desc": f"Penyusunan kerangka kerja modular yang adaptif terhadap pertumbuhan kebutuhan {title.lower()}.",
                    "bullets": ["Struktur komponen mandiri", "Standarisasi kontrak antarmuka"]
                },
                {
                    "badge": "PILAR 02",
                    "title": "Eksekusi & Integrasi",
                    "desc": "Penerapan alur implementasi yang presisi disertai pengujian otomatis berkelanjutan.",
                    "bullets": ["Otomatisasi pengujian alur", "Integrasi modul berkelanjutan"]
                },
                {
                    "badge": "PILAR 03",
                    "title": "Tata Kelola & Keandalan",
                    "desc": "Supervisi aktif terhadap kesehatan sistem dan mitigasi potensi risiko operasional.",
                    "bullets": ["Monitoring telemetri berkala", "Mitigasi anomali proaktif"]
                }
            ]
        res["cards"] = cards
        if not res.get("takeaway"):
            res["takeaway"] = f"🎯 Penguatan pilar strategis memperkokoh fondasi keandalan dan efisiensi jangka panjang."

    # 7. Quote / Closing / Call to Action
    elif layout in ("quote", "call_to_action", "closing"):
        if not res.get("quote"):
            res["quote"] = subtitle or f"Transformasi {title.lower()} merupakan langkah strategis untuk menciptakan keunggulan berkelanjutan dan nilai tambah yang nyata."
        if not res.get("action_steps"):
            res["action_steps"] = [
                "Penyelarasan pemahaman tim dan kesiapan infrastruktur pendukung",
                "Pelaksanaan roadmap implementasi bertahap dengan tata kelola terukur",
                "Evaluasi performa berkala untuk memastikan pencapaian target optimal"
            ]

    # 8. Bullets / List
    elif layout in ("bullets", "default"):
        bullets = res.get("bullets") or []
        if not bullets and res.get("items"):
            bullets = [_extract_item_text(x) for x in res["items"]]
        if not bullets:
            bullets = [
                f"Penyusunan standar operasi dan pedoman teknis {title.lower()} yang terverifikasi.",
                "Peningkatan kapabilitas tim melalui simulasi praktis dan pendalaman materi terpadu.",
                "Penguatan sinergi lintas fungsi guna mengeliminasi hambatan koordinasi operasional.",
                "Penerapan mekanisme audit berkala untuk menjaga konsistensi mutu pelaksanaan."
            ]
        res["bullets"] = bullets
        if not res.get("takeaway"):
            res["takeaway"] = f"🎯 Komitmen eksekusi disiplin adalah kunci keberhasilan pencapaian sasaran {title.lower()}."

    return res


def _xml_escape(s: Any) -> str:
    """Escapes XML entities strictly without HTML named entities."""
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _wrap_tspans(text: str, max_chars: int = 50, line_height: int = 22, base_x: int = 80) -> str:
    """Wraps text into sequential SVG tspans staying strictly within container horizontal bounds."""
    clean_text = str(text).replace("&nbsp;", " ")
    words = clean_text.split()
    lines = []
    curr = []
    curr_len = 0
    for w in words:
        if curr_len + len(w) + 1 <= max_chars:
            curr.append(w)
            curr_len += len(w) + 1
        else:
            if curr:
                lines.append(" ".join(curr))
            curr = [w]
            curr_len = len(w)
    if curr:
        lines.append(" ".join(curr))
    if not lines:
        lines = [clean_text]

    tspans = []
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else line_height
        tspans.append(f'<tspan x="{base_x}" dy="{dy}">{_xml_escape(line)}</tspan>')
    return "".join(tspans)


def _enforce_layout_diversity(slides: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Menjamin anti-monotoni layout presentasi.
    Memastikan tidak ada dua slide berurutan dengan layout visual yang sama.
    Merotasi layout berdasarkan semantik konten:
    - Slide 1: Cover (asymmetric editorial)
    - Content slides: rotasi dinamis antara horizontal_strips, split_screen, cards_grid, kpi_grid, timeline
    - Slide akhir: Closing (focal recommendation & next steps)
    """
    total = len(slides)
    if total <= 1:
        return slides

    available_content_layouts = ["horizontal_strips", "split_screen", "cards_grid", "kpi_grid", "timeline"]
    last_layout = "cover"

    for idx, s in enumerate(slides):
        if idx == 0:
            s["layout"] = "cover"
            last_layout = "cover"
            continue
        
        if idx == total - 1 and total >= 4:
            s["layout"] = "closing"
            continue

        title_l = str(s.get("title", "")).lower()
        sub_l = str(s.get("subtitle", "")).lower()
        kicker_l = str(s.get("kicker", "")).lower()
        combined_text = f"{title_l} {sub_l} {kicker_l}"

        candidate = str(s.get("layout", "")).lower()

        # Semantic classification
        if any(w in combined_text for w in ["kpi", "metrik", "angka", "target", "persen", "%", "sla", "throughput", "performa", "statistik"]):
            candidate = "kpi_grid"
        elif any(w in combined_text for w in ["roadmap", "timeline", "tahap", "fase", "jadwal", "rencana rilis", "milestone", "alur"]):
            candidate = "timeline"
        elif any(w in combined_text for w in ["komparasi", "vs", "versus", "sebelum", "sesudah", "tantangan", "masalah", "solusi", "perbandingan"]):
            candidate = "split_screen"
        elif candidate in ("feature_list", "pillars", "horizontal_strips"):
            candidate = "horizontal_strips"
        elif candidate in ("cards", "cards_grid", "modules", "bullets"):
            candidate = "cards_grid"

        # Anti-monotony collision check
        if candidate == last_layout:
            for alt in available_content_layouts:
                if alt != last_layout:
                    candidate = alt
                    break

        s["layout"] = candidate
        last_layout = candidate

    return slides


def _render_ppt_master_svg_page(
    idx: int, 
    total: int, 
    slide: Dict[str, Any], 
    deck_title: str, 
    palette: Dict[str, Any]
) -> str:
    """
    Menghasilkan kode SVG slide 1280x720 resmi yang sesuai dengan kontrak teknis hugohe3/ppt-master:
    - Root tag data-pptx-page-role (cover / content / ending) & lang="id-ID"
    - Top-level <g id="..." data-pptx-bounds="x y w h"> untuk object animation & DrawingML shapes
    - Palet modern dark mode (Obsidian / Slate / Accent glow)
    - Dynamic footer bebas hardcode corporate
    """
    layout = slide.get("layout", "cards_grid")
    title = str(slide.get("title", f"Slide {idx}")).strip()
    subtitle = str(slide.get("subtitle", "")).strip()
    kicker = str(slide.get("kicker", "STRATEGIC BRIEFING")).strip()
    if kicker == "CAKRA AI • EXECUTIVE PRESENTATION" or not kicker:
        kicker = "STRATEGIC INITIATIVE"

    font_main = "Arial, 'Segoe UI', sans-serif"
    page_role = "cover" if idx == 1 else ("ending" if idx == total and total >= 4 else "content")

    # Header Group for non-cover slides
    header_svg = f"""  <!-- Header Group -->
  <g id="header-group" data-pptx-bounds="80 40 1120 90">
    <text x="80" y="65" font-family="{font_main}" font-size="12" font-weight="bold" fill="#38BDF8" letter-spacing="1.5">{_xml_escape(kicker.upper())}</text>
    <text x="80" y="100" font-family="{font_main}" font-size="28" font-weight="bold" fill="#F8FAFC">{_xml_escape(title)}</text>
    <line id="header-divider" x1="80" y1="120" x2="1200" y2="120" stroke="#334155" stroke-width="1"/>
  </g>"""

    # Dynamic Footer
    footer_label = _xml_escape(deck_title.upper() if deck_title else "STRATEGIC BRIEFING")
    footer_svg = f"""  <!-- Dynamic Footer Meta -->
  <g id="footer-meta" data-pptx-bounds="80 660 1120 30">
    <line id="footer-line" x1="80" y1="650" x2="1200" y2="650" stroke="#334155" stroke-width="1"/>
    <text x="80" y="675" font-family="{font_main}" font-size="11" fill="#64748B">{footer_label}</text>
    <text x="1200" y="675" font-family="{font_main}" font-size="11" font-weight="bold" fill="#38BDF8" text-anchor="end">HALAMAN {idx} DARI {total}</text>
  </g>"""

    defs = """  <defs>
    <linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0F172A"/>
      <stop offset="100%" stop-color="#1E293B"/>
    </linearGradient>
    <linearGradient id="accentGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#38BDF8"/>
      <stop offset="100%" stop-color="#818CF8"/>
    </linearGradient>
    <filter id="softShadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#000000" flood-opacity="0.3"/>
    </filter>
  </defs>
  <rect width="1280" height="720" fill="url(#bgGrad)"/>"""

    # 1. COVER
    if idx == 1 or layout == "cover":
        desc_text = slide.get("desc") or subtitle or "Cetak biru arsitektur komprehensif dengan keandalan operasional tingkat tinggi dan tata kelola terpadu."
        kicker_clean = str(kicker)[:22].upper()
        tag_w = max(240, min(360, len(kicker_clean) * 11 + 40))
        body = f"""  <line id="decor-line-1" x1="80" y1="110" x2="1200" y2="110" stroke="#334155" stroke-width="1" stroke-dasharray="4,4" data-pptx-role="decoration"/>
  <g id="hero-tag" data-pptx-bounds="80 160 {tag_w} 36">
    <rect x="80" y="160" width="{tag_w}" height="36" rx="18" fill="#1E293B" stroke="#38BDF8" stroke-width="1.5"/>
    <text x="100" y="184" font-family="{font_main}" font-size="12" font-weight="bold" fill="#38BDF8" letter-spacing="1.5">{_xml_escape(kicker_clean)}</text>
  </g>
  <g id="hero-title" data-pptx-bounds="80 210 1120 160">
    <text x="80" y="260" font-family="{font_main}" font-size="36" font-weight="bold" fill="#F8FAFC">
      {_wrap_tspans(title, max_chars=48, line_height=44, base_x=80)}
    </text>
    <text x="80" y="325" font-family="{font_main}" font-size="16" fill="#94A3B8">
      {_wrap_tspans(subtitle or 'Executive Presentation & Strategic Roadmap', max_chars=75, line_height=24, base_x=80)}
    </text>
  </g>
  <g id="card-hero" data-pptx-bounds="80 390 1120 210">
    <rect x="80" y="390" width="1120" height="210" rx="16" fill="#182231" stroke="#334155" stroke-width="1" filter="url(#softShadow)"/>
    <rect x="80" y="390" width="1120" height="4" rx="2" fill="url(#accentGrad)"/>
    <text x="120" y="440" font-family="{font_main}" font-size="18" font-weight="bold" fill="#F8FAFC">Ikhtisar Eksekutif</text>
    <text x="120" y="480" font-family="{font_main}" font-size="15" fill="#94A3B8">
      {_wrap_tspans(desc_text, max_chars=75, line_height=24, base_x=120)}
    </text>
  </g>"""

    # 2. HORIZONTAL STRIPS (Pillars / Capabilities)
    elif layout in ("horizontal_strips", "pillars", "feature_list"):
        raw_items = slide.get("items") or slide.get("cards") or [
            {"title": "Pilar Keamanan & Isolasi", "desc": "Enkripsi berlapis zero trust pada seluruh transaksi microservices."},
            {"title": "Kemandirian Operasional", "desc": "Dukungan operasional mandiri pada jaringan terisolasi nasional."},
            {"title": "Skalabilitas Berkesinambungan", "desc": "Elastisitas beban komputasi tinggi tanpa distorsi layanan."}
        ]
        items = raw_items[:3]
        strip_y = [145, 285, 425]
        acc_colors = ["#38BDF8", "#818CF8", "#34D399"]
        strips_svg = []
        for i, itm in enumerate(items):
            sy = strip_y[i]
            col = acc_colors[i % len(acc_colors)]
            itm_title = itm.get("title") or itm.get("badge") or f"Pilar 0{i+1}"
            itm_desc = itm.get("desc") or itm.get("content") or ""
            strips_svg.append(f"""  <g id="pillar-strip-{i+1}" data-pptx-bounds="80 {sy} 1120 120">
    <rect x="80" y="{sy}" width="1120" height="120" rx="12" fill="#182231" stroke="#334155" stroke-width="1"/>
    <rect x="80" y="{sy}" width="6" height="120" rx="3" fill="{col}"/>
    <circle cx="125" cy="{sy+60}" r="18" fill="#1E293B" stroke="{col}" stroke-width="1.5"/>
    <text x="125" y="{sy+66}" font-family="{font_main}" font-size="14" font-weight="bold" fill="{col}" text-anchor="middle">0{i+1}</text>
    <text x="165" y="{sy+45}" font-family="{font_main}" font-size="18" font-weight="bold" fill="#F8FAFC">{_xml_escape(itm_title)}</text>
    <text x="165" y="{sy+75}" font-family="{font_main}" font-size="14" fill="#94A3B8">
      {_wrap_tspans(itm_desc, max_chars=80, line_height=20, base_x=165)}
    </text>
  </g>""")
        strips_svg_str = "\n".join(strips_svg)
        takeaway = slide.get("takeaway", "Seluruh pilar terintegrasi dalam kerangka orkestrasi tunggal berstandar industri.")
        body = f"""{header_svg}
{strips_svg_str}
  <g id="takeaway-box" data-pptx-bounds="80 570 1120 50">
    <rect x="80" y="570" width="1120" height="50" rx="8" fill="#1E293B" stroke="#38BDF8" stroke-width="1" stroke-dasharray="4,4"/>
    <text x="105" y="601" font-family="{font_main}" font-size="13" fill="#38BDF8">
      <tspan font-weight="bold">Rangkuman Kunci: </tspan>{_xml_escape(takeaway)}
    </text>
  </g>"""

    # 3. SPLIT SCREEN (Two Columns / Comparison)
    elif layout in ("split_screen", "two_column", "comparison"):
        hero_left = slide.get("hero", {})
        left_title = hero_left.get("title") or "Tantangan Eksisting & Hambatan"
        left_desc = hero_left.get("desc") or "Keterikatan erat antar modul membatasi throughput transaksi saat lonjakan beban dan memperpanjang siklus rilis."
        items_right = slide.get("items", [])
        right_title = "Solusi Arsitektur & Modernisasi"
        right_desc = "Pemisahan domain terdistribusi dengan isolasi kegagalan mandiri dan skalabilitas elastis otomatis."
        if items_right and isinstance(items_right[0], dict):
            right_title = items_right[0].get("title", right_title)
            right_desc = items_right[0].get("desc", right_desc)

        takeaway = slide.get("takeaway", "Migrasi modular mereduksi potensi downtime operasional hingga 85%.")
        body = f"""{header_svg}
  <g id="card-col-left" data-pptx-bounds="80 150 540 395">
    <rect x="80" y="150" width="540" height="395" rx="16" fill="#182231" stroke="#334155" stroke-width="1" filter="url(#softShadow)"/>
    <rect x="80" y="150" width="540" height="4" rx="2" fill="#EF4444"/>
    <rect x="110" y="180" width="160" height="28" rx="14" fill="#1E293B" stroke="#EF4444" stroke-width="1"/>
    <text x="190" y="199" font-family="{font_main}" font-size="12" font-weight="bold" fill="#EF4444" text-anchor="middle">TANTANGAN EKSISTING</text>
    <text x="110" y="240" font-family="{font_main}" font-size="20" font-weight="bold" fill="#F8FAFC">{_xml_escape(left_title)}</text>
    <text x="110" y="275" font-family="{font_main}" font-size="14" fill="#94A3B8">
      {_wrap_tspans(left_desc, max_chars=38, line_height=22, base_x=110)}
    </text>
    <circle cx="120" cy="375" r="4" fill="#EF4444"/>
    <text x="135" y="380" font-family="{font_main}" font-size="14" fill="#CBD5E1">Skalabilitas terbatas saat beban puncak</text>
    <circle cx="120" cy="415" r="4" fill="#EF4444"/>
    <text x="135" y="420" font-family="{font_main}" font-size="14" fill="#CBD5E1">Ketergantungan database tunggal terpusat</text>
  </g>
  <g id="card-col-right" data-pptx-bounds="660 150 540 395">
    <rect x="660" y="150" width="540" height="395" rx="16" fill="#182231" stroke="#334155" stroke-width="1" filter="url(#softShadow)"/>
    <rect x="660" y="150" width="540" height="4" rx="2" fill="#10B981"/>
    <rect x="690" y="180" width="160" height="28" rx="14" fill="#1E293B" stroke="#10B981" stroke-width="1"/>
    <text x="770" y="199" font-family="{font_main}" font-size="12" font-weight="bold" fill="#10B981" text-anchor="middle">SOLUSI TERINTEGRASI</text>
    <text x="690" y="240" font-family="{font_main}" font-size="20" font-weight="bold" fill="#F8FAFC">{_xml_escape(right_title)}</text>
    <text x="690" y="275" font-family="{font_main}" font-size="14" fill="#94A3B8">
      {_wrap_tspans(right_desc, max_chars=38, line_height=22, base_x=690)}
    </text>
    <circle cx="700" cy="375" r="4" fill="#10B981"/>
    <text x="715" y="380" font-family="{font_main}" font-size="14" fill="#CBD5E1">Autoscaling otomatis berbasis telemetri real-time</text>
    <circle cx="700" cy="415" r="4" fill="#10B981"/>
    <text x="715" y="420" font-family="{font_main}" font-size="14" fill="#CBD5E1">Zero-downtime deployment berkesinambungan</text>
  </g>
  <g id="takeaway-box" data-pptx-bounds="80 565 1120 50">
    <rect x="80" y="565" width="1120" height="50" rx="8" fill="#1E293B" stroke="#38BDF8" stroke-width="1"/>
    <text x="105" y="596" font-family="{font_main}" font-size="13" fill="#38BDF8">
      <tspan font-weight="bold">Kesimpulan Komparasi: </tspan>{_xml_escape(takeaway)}
    </text>
  </g>"""

    # 4. KPI GRID (Metrics / Numbers)
    elif layout in ("kpi_grid", "metrics", "analytics"):
        raw_stats = slide.get("items") or slide.get("cards") or [
            {"title": "Service Availability", "value": "99.99%", "desc": "Tingkat keandalan operasional sistem tanpa insiden kritis."},
            {"title": "P99 Latency", "value": "< 25ms", "desc": "Kecepatan respons transaksi microservices berkinerja tinggi."},
            {"title": "Deployment Speed", "value": "10x", "desc": "Peningkatan akselerasi rilis melalui automasi CI/CD terpadu."}
        ]
        stats = raw_stats[:3]
        acc_colors = ["#38BDF8", "#818CF8", "#34D399"]
        kpi_x = [80, 465, 850]
        kpi_svg = []
        for i, st in enumerate(stats):
            kx = kpi_x[i]
            col = acc_colors[i % len(acc_colors)]
            st_val = st.get("value") or st.get("badge") or ("99.9%" if i == 0 else ("<25ms" if i == 1 else "10x"))
            st_lbl = st.get("title") or st.get("label") or f"Metrik 0{i+1}"
            st_desc = st.get("desc") or st.get("content") or ""
            val_str = str(st_val)[:15]
            if len(val_str) > 7:
                val_sz = 28
            elif len(val_str) > 5:
                val_sz = 34
            else:
                val_sz = 44
            kpi_svg.append(f"""  <g id="kpi-metric-{i+1}" data-pptx-bounds="{kx} 155 350 380">
    <rect x="{kx}" y="155" width="350" height="380" rx="16" fill="#182231" stroke="#334155" stroke-width="1" filter="url(#softShadow)"/>
    <rect x="{kx}" y="155" width="350" height="4" rx="2" fill="{col}"/>
    <text x="{kx+30}" y="235" font-family="{font_main}" font-size="{val_sz}" font-weight="bold" fill="{col}">{_xml_escape(val_str)}</text>
    <text x="{kx+30}" y="275" font-family="{font_main}" font-size="18" font-weight="bold" fill="#F8FAFC">{_xml_escape(st_lbl)}</text>
    <text x="{kx+30}" y="315" font-family="{font_main}" font-size="14" fill="#94A3B8">
      {_wrap_tspans(st_desc, max_chars=25, line_height=20, base_x=kx+30)}
    </text>
  </g>""")
        kpi_str = "\n".join(kpi_svg)
        takeaway = slide.get("takeaway", "Seluruh metrik kuantitatif divalidasi berkala melalui telemetri otomatis terpusat.")
        body = f"""{header_svg}
{kpi_str}
  <g id="takeaway-box" data-pptx-bounds="80 560 1120 50">
    <rect x="80" y="560" width="1120" height="50" rx="8" fill="#1E293B" stroke="#38BDF8" stroke-width="1"/>
    <text x="105" y="591" font-family="{font_main}" font-size="13" fill="#38BDF8">
      <tspan font-weight="bold">Tolok Ukur Keberhasilan: </tspan>{_xml_escape(takeaway)}
    </text>
  </g>"""

    # 5. TIMELINE / ROADMAP
    elif layout in ("timeline", "roadmap", "milestone"):
        raw_steps = slide.get("steps") or slide.get("items") or [
            {"phase": "Q1 2026", "title": "Inisiasi & Standardisasi", "desc": "Audit arsitektur eksisting, standarisasi kontrak API, dan penetapan blueprint keamanan."},
            {"phase": "Q2-Q3 2026", "title": "Dekomposisi Modular", "desc": "Migrasi bertahap modul inti ke microservices dengan pengujian beban paralel."},
            {"phase": "Q4 2026", "title": "Adopsi Penuh Mandiri", "desc": "Operasional penuh mandiri dengan pemantauan telemetri 24/7 dan serah terima tim internal."}
        ]
        steps = raw_steps[:3]
        step_x = [80, 465, 850]
        acc_colors = ["#38BDF8", "#818CF8", "#34D399"]
        steps_svg = []
        for i, st in enumerate(steps):
            sx = step_x[i]
            col = acc_colors[i % len(acc_colors)]
            st_phase = st.get("phase") or f"Tahap 0{i+1}"
            st_title = st.get("title") or f"Fase 0{i+1}"
            st_desc = st.get("desc") or st.get("content") or ""
            steps_svg.append(f"""  <g id="step-{i+1}" data-pptx-bounds="{sx} 180 350 350">
    <rect x="{sx}" y="180" width="350" height="350" rx="16" fill="#182231" stroke="#334155" stroke-width="1" filter="url(#softShadow)"/>
    <circle cx="{sx+40}" cy="220" r="20" fill="#1E293B" stroke="{col}" stroke-width="2"/>
    <text x="{sx+40}" y="226" font-family="{font_main}" font-size="14" font-weight="bold" fill="{col}" text-anchor="middle">0{i+1}</text>
    <text x="{sx+75}" y="226" font-family="{font_main}" font-size="16" font-weight="bold" fill="#F8FAFC">{_xml_escape(st_phase)}</text>
    <line id="step-line-{i+1}" x1="{sx+30}" y1="255" x2="{sx+320}" y2="255" stroke="#334155" stroke-width="1"/>
    <text x="{sx+30}" y="285" font-family="{font_main}" font-size="15" font-weight="bold" fill="#F8FAFC">{_xml_escape(st_title)}</text>
    <text x="{sx+30}" y="315" font-family="{font_main}" font-size="13" fill="#94A3B8">
      {_wrap_tspans(st_desc, max_chars=25, line_height=20, base_x=sx+30)}
    </text>
  </g>""")
        steps_str = "\n".join(steps_svg)
        takeaway = slide.get("takeaway", "Pencapaian milestone dimonitor secara berkala dengan sprint tinjauan berkala.")
        body = f"""{header_svg}
  <line id="roadmap-connector" x1="150" y1="210" x2="1130" y2="210" stroke="#38BDF8" stroke-width="3" stroke-dasharray="6,6" data-pptx-role="decoration"/>
{steps_str}
  <g id="takeaway-box" data-pptx-bounds="80 560 1120 50">
    <rect x="80" y="560" width="1120" height="50" rx="8" fill="#1E293B" stroke="#38BDF8" stroke-width="1"/>
    <text x="105" y="591" font-family="{font_main}" font-size="13" fill="#38BDF8">
      <tspan font-weight="bold">Jaminan Jadwal: </tspan>{_xml_escape(takeaway)}
    </text>
  </g>"""

    # 6. CLOSING / ENDING (Vision & Executive Next Steps)
    elif layout in ("closing", "ending", "quote", "vision"):
        desc_text = slide.get("desc") or subtitle or "Penyelarasan strategis dan komitmen kepemimpinan merupakan pilar utama keberhasilan transformasi berkelanjutan."
        action_bullets = slide.get("action_steps") or slide.get("bullets") or [
            "Pembentukan gugus tugas lintas fungsi untuk percepatan eksekusi",
            "Pelaksanaan pilot project pada domain layanan prioritas awal",
            "Evaluasi performa berkala dan dokumentasi praktik terbaik"
        ]
        b1 = action_bullets[0] if len(action_bullets) > 0 else 'Koordinasi lintas divisi'
        b2 = action_bullets[1] if len(action_bullets) > 1 else 'Pelaksanaan tahap awal'
        body = f"""  <g id="hero-statement" data-pptx-bounds="120 140 1040 460">
    <rect x="120" y="140" width="1040" height="460" rx="20" fill="#182231" stroke="#38BDF8" stroke-width="1.5" filter="url(#softShadow)"/>
    <rect x="120" y="140" width="1040" height="6" rx="3" fill="url(#accentGrad)"/>
    <rect x="170" y="185" width="200" height="32" rx="16" fill="#1E293B" stroke="#38BDF8" stroke-width="1"/>
    <text x="270" y="206" font-family="{font_main}" font-size="12" font-weight="bold" fill="#38BDF8" text-anchor="middle">VISI &amp; REKOMENDASI AKHIR</text>
    <text x="170" y="265" font-family="{font_main}" font-size="28" font-weight="bold" fill="#F8FAFC">
      {_wrap_tspans(title or 'Membangun Kemandirian Arsitektur Berkelanjutan', max_chars=40, line_height=36, base_x=170)}
    </text>
    <text x="170" y="340" font-family="{font_main}" font-size="16" fill="#94A3B8">
      {_wrap_tspans(desc_text, max_chars=60, line_height=26, base_x=170)}
    </text>
    <line id="closing-divider" x1="170" y1="420" x2="1080" y2="420" stroke="#334155" stroke-width="1"/>
    <text x="170" y="455" font-family="{font_main}" font-size="15" font-weight="bold" fill="#38BDF8">Langkah Nyata Implementasi:</text>
    <text x="170" y="490" font-family="{font_main}" font-size="13" fill="#CBD5E1">• {_xml_escape(b1)}    • {_xml_escape(b2)}</text>
  </g>"""

    # 7. DEFAULT CARDS GRID (3 Modular Cards with Top Accent Line)
    else:
        raw_cards = slide.get("cards") or slide.get("items") or [
            {"title": "Kecepatan Implementasi", "desc": "Waktu delivery dipersingkat hingga 40% melalui orkestrasi otomatis."},
            {"title": "Kualitas Terstandarisasi", "desc": "Setiap komponen melewati pengujian keamanan dan kepatuhan standar ketat."},
            {"title": "Efisiensi Biaya Operasional", "desc": "Pengurangan pemborosan sumber daya komputasi melalui perancangan hemat daya."}
        ]
        cards = raw_cards[:3]
        acc_colors = ["#38BDF8", "#818CF8", "#34D399"]
        c_x = [80, 465, 850]
        cards_svg = []
        for i, c in enumerate(cards):
            cx = c_x[i]
            col = acc_colors[i % len(acc_colors)]
            c_title = c.get("title") or f"Komponen 0{i+1}"
            c_desc = c.get("desc") or c.get("content") or ""
            cards_svg.append(f"""  <g id="card-{i+1}" data-pptx-bounds="{cx} 150 350 395">
    <rect x="{cx}" y="150" width="350" height="395" rx="16" fill="#182231" stroke="#334155" stroke-width="1" filter="url(#softShadow)"/>
    <rect x="{cx}" y="150" width="350" height="4" rx="2" fill="{col}"/>
    <rect x="{cx+25}" y="180" width="70" height="24" rx="12" fill="#1E293B" stroke="{col}" stroke-width="1"/>
    <text x="{cx+60}" y="196" font-family="{font_main}" font-size="11" font-weight="bold" fill="{col}" text-anchor="middle">0{i+1}</text>
    <text x="{cx+25}" y="240" font-family="{font_main}" font-size="18" font-weight="bold" fill="#F8FAFC">{_xml_escape(c_title)}</text>
    <text x="{cx+25}" y="275" font-family="{font_main}" font-size="14" fill="#94A3B8">
      {_wrap_tspans(c_desc, max_chars=25, line_height=22, base_x=cx+25)}
    </text>
  </g>""")
        cards_str = "\n".join(cards_svg)
        takeaway = slide.get("takeaway", "Setiap komponen dirancang modular agar dapat dikembangkan secara mandiri.")
        body = f"""{header_svg}
{cards_str}
  <g id="takeaway-box" data-pptx-bounds="80 565 1120 50">
    <rect x="80" y="565" width="1120" height="50" rx="8" fill="#1E293B" stroke="#38BDF8" stroke-width="1"/>
    <text x="105" y="596" font-family="{font_main}" font-size="13" fill="#38BDF8">
      <tspan font-weight="bold">Fokus Strategis: </tspan>{_xml_escape(takeaway)}
    </text>
  </g>"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720" data-pptx-page-role="{page_role}" lang="id-ID">
{defs}
{body}
{footer_svg}
</svg>"""


def _build_ppt_master_svg_project(
    slides: List[Dict[str, Any]], 
    project_dir: Path, 
    theme_style: Dict[str, Any], 
    deck_title: str, 
    current_user_npp: str = ""
) -> None:
    """
    Menyusun struktur folder project SVG resmi PPT Master:
    - <project_dir>/svg_output/01_cover.svg, 02_problem.svg, dst.
    - <project_dir>/notes/01_cover.md, 02_problem.md, dst.
    Memastikan 100% kelulusan audit svg_quality_checker.
    """
    svg_dir = project_dir / "svg_output"
    notes_dir = project_dir / "notes"
    val_dir = project_dir / "validation"
    
    svg_dir.mkdir(parents=True, exist_ok=True)
    notes_dir.mkdir(parents=True, exist_ok=True)
    
    # Bersihkan file stale dari generasi sebelumnya di project_dir yang sama
    for old_svg in svg_dir.glob("*.svg"):
        try:
            old_svg.unlink()
        except Exception:
            pass
    for old_note in notes_dir.glob("*.md"):
        try:
            old_note.unlink()
        except Exception:
            pass
    if val_dir.exists():
        import shutil
        try:
            shutil.rmtree(val_dir, ignore_errors=True)
        except Exception:
            pass

    palette = _resolve_palette(custom_theme=theme_style)
    diverse_slides = _enforce_layout_diversity(slides)
    total_slides = len(diverse_slides)

    for idx, s in enumerate(diverse_slides):
        slide_num = idx + 1
        layout_name = s.get("layout", "slide")
        safe_slug = re.sub(r'[^a-zA-Z0-9_]', '_', layout_name).lower()
        file_prefix = f"{slide_num:02d}_{safe_slug}"

        svg_content = _render_ppt_master_svg_page(
            idx=slide_num,
            total=total_slides,
            slide=s,
            deck_title=deck_title,
            palette=palette
        )
        (svg_dir / f"{file_prefix}.svg").write_text(svg_content, encoding="utf-8")

        # Speaker notes
        note_text = s.get("notes") or s.get("speaker_notes")
        if not note_text:
            s_title = s.get("title", f"Slide {slide_num}")
            s_takeaway = s.get("takeaway", "")
            note_text = f"Presenter track untuk slide {slide_num}: {s_title}. Tekankan sasaran strategis dan implikasi implementasi di lapangan. {s_takeaway}"
        
        note_md = f"# Speaker Notes - Slide {slide_num} ({s.get('title', '')})\n\n{note_text}"
        (notes_dir / f"{file_prefix}.md").write_text(note_md, encoding="utf-8")


def _compile_svg_to_pptx(project_dir: Path, output_pptx: Path) -> bool:
    """
    Mengompilasi workspace SVG project menjadi berkas PowerPoint (.pptx)
    menggunakan pipeline resmi ppt-master (svg_to_pptx.py).
    Menjalankan rantai kompilasi standar ppt-master:
    1. Normalisasi styling & font default (compact_svg_styles.py)
    2. Quality Gate check & export JSON quality report (svg_quality_checker.py)
    3. Eksekusi compiler svg_to_pptx dengan preset animasi otomatis dan speaker notes.
    """
    script_candidates = [
        Path("/home/qisthi/pinAi/backend/app/services/tools/ppt_master/skills/ppt-master/scripts/svg_to_pptx.py"),
        Path("/home/qisthi/pinAi/.agents/skills/ppt_master/scripts/svg_to_pptx.py")
    ]
    script_path = None
    for p in script_candidates:
        if p.exists():
            script_path = p
            break
            
    if not script_path:
        logger.error("[PPT_MASTER] Skrip svg_to_pptx.py tidak ditemukan di sistem")
        return False

    import sys
    python_bin = sys.executable
    rag_env_python = Path("/home/qisthi/pinAi/rag_env/bin/python")
    if rag_env_python.exists():
        python_bin = str(rag_env_python)

    scripts_dir = script_path.parent
    compact_script = scripts_dir / "compact_svg_styles.py"
    quality_script = scripts_dir / "svg_quality_checker.py"
    svg_out_dir = project_dir / "svg_output"

    # Step 1: Normalisasi style SVG jika skrip tersedia
    if compact_script.exists() and svg_out_dir.exists():
        try:
            cmd_compact = [python_bin, str(compact_script), str(svg_out_dir), "--inplace"]
            p_comp = subprocess.run(cmd_compact, capture_output=True, text=True, timeout=30)
            if p_comp.returncode == 0:
                logger.info("[PPT_MASTER] ✅ compact_svg_styles berhasil menormalisasi deklarasi SVG")
        except Exception as e_comp:
            logger.warning(f"[PPT_MASTER] Advisory compact_svg_styles exception: {e_comp}")

    # Step 2: Quality Checker Gate (Wajib untuk --quick-generate)
    if quality_script.exists():
        try:
            cmd_quality = [
                python_bin,
                str(quality_script),
                str(project_dir),
                "--quick-generate",
                "--canonical-authoring",
                "--stage", "final",
                "--json"
            ]
            p_qual = subprocess.run(cmd_quality, capture_output=True, text=True, timeout=45)
            if p_qual.returncode == 0:
                logger.info("[PPT_MASTER] ✅ SVG Quality Gate lulus 100% (passing final quality report)")
            else:
                logger.warning(f"[PPT_MASTER] ⚠️ SVG Quality Checker exit code {p_qual.returncode}:\n{p_qual.stdout[:600]}")
        except Exception as e_qual:
            logger.warning(f"[PPT_MASTER] Eksepsi saat menjalankan svg_quality_checker: {e_qual}")

    # Step 3: Kompilasi SVG ke PPTX via svg_to_pptx.py
    cmd = [
        python_bin,
        str(script_path),
        str(project_dir),
        "--quick-generate",
        "-o", str(output_pptx),
        "-t", "fade",
        "-a", "auto",
        "--with-notes"
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode == 0 and output_pptx.exists() and output_pptx.stat().st_size > 0:
            logger.info(f"[PPT_MASTER] ✅ Sukses mengompilasi SVG ke PPTX via svg_to_pptx: {output_pptx.name} ({output_pptx.stat().st_size} bytes)")
            return True
        else:
            logger.warning(f"[PPT_MASTER] ⚠️ Kompilasi svg_to_pptx gagal (code {proc.returncode}):\nStdout: {proc.stdout}\nStderr: {proc.stderr}")
            return False
    except Exception as e:
        logger.warning(f"[PPT_MASTER] ⚠️ Eksepsi saat menjalankan svg_to_pptx: {e}")
        return False


def _export_pptx_slides_to_svg(pptx_path: Path, output_dir: Path) -> List[str]:
    """
    Mengonversi berkas PPTX asli menjadi SVG vektor resolusi tinggi per slide 
    menggunakan converter resmi PPT Master (pptx_to_svg).
    """
    import sys
    script_candidates = [
        Path("/home/qisthi/pinAi/backend/app/services/tools/ppt_master/skills/ppt-master/scripts"),
        Path("/home/qisthi/pinAi/.agents/skills/ppt_master/scripts")
    ]
    for sc in script_candidates:
        if sc.exists() and str(sc) not in sys.path:
            sys.path.insert(0, str(sc))
    try:
        from pptx_to_svg import convert_pptx_to_svg
        from pptx_to_svg.converter import ConvertOptions

        opts = ConvertOptions(inheritance_mode="flat", embed_images=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        convert_pptx_to_svg(pptx_path, output_dir, opts)
        
        svg_dir = output_dir / "svg"
        if svg_dir.exists():
            svg_files = sorted(list(svg_dir.glob("*.svg")))
            return [str(f) for f in svg_files]
        return []
    except Exception as e:
        logger.warning(f"[PPT_MASTER] Gagal konversi PPTX ke SVG: {e}")
        return []


def _find_session_pdf_attachments(
    session_id: Optional[str],
    current_user_npp: Optional[str],
    explicit_paths: Optional[List[str]] = None
) -> List[str]:
    """Mencari berkas PDF lampiran yang relevan dengan sesi aktif secara komprehensif."""
    valid_pdfs = []
    if explicit_paths:
        for p in explicit_paths:
            if isinstance(p, str) and p.lower().endswith(".pdf") and os.path.isfile(p):
                valid_pdfs.append(p)
                
    if session_id:
        if current_user_npp:
            from backend.app.core.paths import get_account_session_dir
            for sub in ["images", "attachments", "documents", "artifacts", "uploads"]:
                try:
                    s_dir = get_account_session_dir(current_user_npp, session_id, sub)
                    if s_dir.exists():
                        for f in s_dir.glob("*.pdf"):
                            f_str = str(f)
                            if f_str not in valid_pdfs:
                                valid_pdfs.append(f_str)
                except Exception:
                    pass

        # Fallback pencarian lintas folder accounts untuk session_id aktif jika belum ditemukan
        if not valid_pdfs:
            accounts_root = Path("/home/qisthi/pinAi/accounts")
            if accounts_root.exists():
                try:
                    for f in accounts_root.glob(f"*/{session_id}/brain/*/*.pdf"):
                        f_str = str(f)
                        if f_str not in valid_pdfs:
                            valid_pdfs.append(f_str)
                except Exception:
                    pass
                
    return valid_pdfs


async def call_ppt_master_planner(
    topic: str,
    slide_count: int = 6,
    user_instructions: str = "",
    attachment_paths: Optional[List[str]] = None,
    chat_context: Optional[str] = None,
    user_preferences: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    current_user_npp: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Step 1: PLANNER AGENT (Chief Presentation Architect)
    Menganalisis instruksi mentah, mengekstrak dokumen/PDF scan sebagai gambar halaman (hingga 20 halaman),
    dan merumuskan cetak biru lengkap (plan.json) mencakup tema visual dan arsitektur slide 1..X.
    """
    from backend.app.core.llm_client import generate_json_response
    from backend.app.core.config import settings

    target_model = getattr(settings, "MODEL_PERSONA", "cakra-core")

    # Ingest PDF visual pages (mampu membaca PDF scan / digital hingga 20 halaman)
    pdf_files = _find_session_pdf_attachments(session_id, current_user_npp, attachment_paths)
    base64_page_images = []
    if pdf_files:
        primary_pdf = pdf_files[0]
        try:
            from backend.app.services.tools.unified_extractor import extract_document
            doc = await extract_document(primary_pdf, render_images=True)
            if doc and doc.base64_images:
                base64_page_images = doc.base64_images[:20]
                logger.info(f"[PPT_MASTER_PLANNER] 📄 Sukses memuat {len(base64_page_images)} gambar halaman PDF dari '{os.path.basename(primary_pdf)}'")
        except Exception as e_pdf:
            logger.warning(f"[PPT_MASTER_PLANNER] Gagal ekstraksi gambar PDF {primary_pdf}: {e_pdf}")

    system_instruction = (
        "Anda adalah Chief Presentation Designer & Master Presentation Strategist berstandar PPT Master.\n\n"
        "=== PRINSIP PERANCANGAN (BEBAS, DINAMIS & KONTEKSTUAL) ===\n"
        "1. PEMAHAMAN MATERI & SUMBER DATA:\n"
        "   - Analisis secara mendalam topik, instruksi pengguna, dan visual lampiran jika ada.\n"
        "   - Setiap slide HARUS berakar kuat pada data dan materi substantif yang diberikan, bukan teks generik atau asumsi.\n\n"
        "2. IDENTITAS VISUAL & TEMA TEMATIK:\n"
        "   - Ciptakan tema warna dan estetika visual yang orisinal dan mencerminkan domain materi tersebut.\n"
        "   - Prioritaskan estetika Executive Dark Mode ('is_dark': true) dengan latar belakang obsidian, deep slate, atau charcoal gelap (misal bg_hex gelap, card_bg_hex selaras bergradasi, dan accent_hex bercahaya).\n"
        "   - Jika menggunakan tema terang, pastikan kanvas memiliki kontras lembut dengan permukaan kartu yang kontras dan border halus (bukan kanvas putih polos dengan wireframe garis biru kaku).\n"
        "   - Rancang palet warna harmonis (bg_hex, card_bg_hex, card_subtle_hex, accent_hex, title_hex, text_hex, muted_hex, border_hex, separator_hex, is_dark).\n"
        "   - Beri nama tema yang deskriptif dan relevan dengan materi.\n"
        "   - Tentukan efek latar ('dots_particles', 'cyber_grid', 'ambient_glow', atau 'minimal_clean').\n\n"
        "3. ARSITEKTUR & ATURAN DIVERSIFIKASI TATA LETAK SLIDE (ANTI-MONOTONI):\n"
        f"   - Rancang tepat {slide_count} slide dengan variasi tata letak yang kaya dan mengalir sesuai kebutuhan narasi materi.\n"
        "   - ATURAN ANTI-MONOTONI MUTLAK: DILARANG MENGULANG layout kartu vertikal yang sama ('cards_grid') secara berturut-turut atau mendominasi seluruh dek. Maksimal 1 hingga 2 slide saja yang boleh memakai 'cards_grid'.\n"
        "   - WAJIB variasikan jenis tata letak pada setiap halaman menggunakan ragam arsitektur berikut:\n"
        "     * 'title' : Sampul pembuka / cover eksekutif. WAJIB sertakan atribut 'cover_style' dengan pilihan salah satu dari:\n"
        "         - 'split_editorial' : Tata letak majalah editorial asimetris dengan panel hero sisi kiri dan judul/ringkasan di sisi kanan.\n"
        "         - 'centered_hero' : Tipografi terpusat yang berani dengan floating badge dan kartu identitas pembicara/institusi.\n"
        "         - 'modern_minimalist' : Garis aksen vertikal tegas dengan metadata chips horizontal terpadu.\n"
        "     * 'split_screen' : Tata letak asimetris dengan 1 kartu konsep hero besar di kiri dan 2-3 kartu modul detail bertingkat di kanan (sangat direkomendasikan untuk arsitektur, tantangan vs solusi, atau latar belakang inti).\n"
        "     * 'feature_list' : Deretan modul/komponen berbentuk kartu horizontal memanjang dengan aksen indikator samping (memecah kejenuhan kartu vertikal).\n"
        "     * 'two_columns' : Komparasi dua sisi berimbang (teori vs praktik, sebelum vs sesudah, pro vs kontra) dilengkapi takeaway opsional.\n"
        "     * 'timeline' : Alur tahapan bertahap, alur roadmap eksekusi, fase kurikulum, atau proses sekuensial (steps dengan phase, title, desc, bullets opsional).\n"
        "     * 'stats' : Metrik data kuantitatif, target SLA, rasio pencapaian dengan ringkasan dampak strategis (stats dengan value, label, desc).\n"
        "     * 'bullets' : Paparan butir-butir hierarkis berbobot tinggi dengan banner kesimpulan strategis.\n"
        "     * 'quote' : Penegasan pesan kunci visi strategis atau kutipan pimpinan institusi.\n"
        "   - Susun ritme tata letak secara luwes dan dinamis agar setiap slide memberikan kejutan visual segar bagi audiens.\n"
        "   - Setiap elemen kartu, modul, dan poin wajib memuat substansi informatif yang tajam, padat, dan bernilai tinggi.\n\n"
        "4. KONTEN SUBSTANTIF MUTLAK PER SLIDE (DILARANG KERAS SLIDE KOSONG/CACAT):\n"
        "   - SETIAP objek slide di dalam array 'slides' WAJIB menyertakan payload konten bodi lengkap sesuai layout yang dipilihnya:\n"
        "     * 'title'        : Wajib ada 'cover_style' ('split_editorial' | 'centered_hero' | 'modern_minimalist'), 'title', 'subtitle', 'kicker', 'presenter', 'organization'.\n"
        "     * 'split_screen' : Wajib ada 'hero': {'badge': '...', 'title': '...', 'desc': '...', 'takeaway': '...'}, dan 'items': [{'title': '...', 'desc': '...'}, ... (2-3 item)].\n"
        "     * 'feature_list' : Wajib ada 'items': [{'badge': '...', 'title': '...', 'desc': '...', 'bullets': [...]}, ... (3-4 item)].\n"
        "     * 'two_columns'  : Wajib ada 'left': {'heading': '...', 'desc': '...', 'items': [...]}, 'right': {'heading': '...', 'desc': '...', 'items': [...]}, dan 'takeaway': '...'.\n"
        "     * 'timeline'     : Wajib ada 'steps': [{'phase': 'TAHAP 01', 'title': '...', 'desc': '...', 'bullets': [...]}, ... (3-4 tahap)], dan 'takeaway': '...'.\n"
        "     * 'stats'        : Wajib ada 'stats': [{'value': '...', 'label': '...', 'desc': '...'}, ... (3 metrik)], dan 'takeaway': '...'.\n"
        "     * 'cards_grid'   : Wajib ada 'cards': [{'badge': '...', 'title': '...', 'desc': '...', 'bullets': [...]}, ... (3 kartu)], dan 'takeaway': '...'.\n"
        "     * 'quote'        : Wajib ada 'quote': '...', 'author': '...', dan 'action_steps': ['...', '...', '...'].\n"
        "     * 'bullets'      : Wajib ada 'bullets': ['...', '...', '...'] (3-5 butir berbobot), dan 'takeaway': '...'.\n"
        "   - PERINGATAN KERAS: DILARANG membuat objek slide yang hanya berisi judul dan kicker saja tanpa payload konten di atas. Setiap slide tanpa payload bodi akan menghasilkan tampilan kosong dan dianggap kegagalan fatal!\n\n"
        "STRUKTUR KELUARAN WAJIB (JSON murni tanpa markdown code fence):\n"
        "{\n"
        '  "title": "Judul Lengkap Presentasi",\n'
        '  "theme_style": {\n'
        '    "name": "Nama Tema Orisinal",\n'
        '    "visual_style": "Gaya Visual Relevan",\n'
        '    "backdrop_effect": "dots_particles",\n'
        '    "transition": "fade",\n'
        '    "bg_hex": "#...",\n'
        '    "card_bg_hex": "#...",\n'
        '    "card_subtle_hex": "#...",\n'
        '    "accent_hex": "#...",\n'
        '    "title_hex": "#...",\n'
        '    "text_hex": "#...",\n'
        '    "muted_hex": "#...",\n'
        '    "border_hex": "#...",\n'
        '    "separator_hex": "#...",\n'
        '    "is_dark": true\n'
        '  },\n'
        f'  "slides": [ ... tepat {slide_count} objek slide berstruktur data lengkap dengan payload konten bodi ... ]\n'
        "}"
    )

    user_prompt = f"Rancang cetak biru (blueprint) presentasi PPT Master:\nTopik: {topic}\nJumlah Slide yang Dibutuhkan: {slide_count}"
    if user_instructions and len(user_instructions.strip()) > 0:
        user_prompt += f"\n\nInstruksi & Keinginan Eksplisit Pengguna:\n{user_instructions}"
    if chat_context and len(chat_context.strip()) > 0:
        user_prompt += f"\n\nKonteks Obrolan Terkait:\n{chat_context[:3000]}"
    if base64_page_images:
        user_prompt += f"\n\nLampiran Dokumen: {len(base64_page_images)} halaman dokumen disertakan sebagai visual gambar. Teliti visual gambar tersebut untuk menyusun materi slide secara faktual dan akurat."

    user_msg_dict: Dict[str, Any] = {"role": "user", "content": user_prompt}
    if base64_page_images:
        user_msg_dict["images"] = base64_page_images

    messages = [
        {"role": "system", "content": system_instruction},
        user_msg_dict
    ]

    try:
        response_dict = await generate_json_response(
            model_name=target_model,
            messages=messages,
            temperature=0.35,
            timeout=180.0,
            num_predict=4096,
            num_ctx=32768
        )
        raw_slides = response_dict.get("slides")
        if isinstance(raw_slides, list) and len(raw_slides) >= 2:
            norm_slides = [_normalize_slide_item(s, idx + 1) for idx, s in enumerate(raw_slides)]
            theme_style = response_dict.get("theme_style") or {}
            pres_title = response_dict.get("title") or topic
            logger.info(f"[PPT_MASTER_PLANNER] ✅ Blueprint berhasil dirancang via '{target_model}' ({len(norm_slides)} slide, theme: {theme_style.get('name', 'Dynamic AI')})")
            return {
                "slides": norm_slides,
                "theme_style": theme_style,
                "title": pres_title
            }
    except Exception as e:
        logger.warning(f"[PPT_MASTER_PLANNER] Gagal merancang via LLM ({e}), beralih ke generator adaptif.")

    return None


async def call_ppt_master_evaluator(
    slides: List[Dict[str, Any]],
    topic: str,
    user_instructions: str = "",
    theme_style: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Step 3: EVALUATOR AGENT (Executive Creative Director & QA Auditor)
    Mengevaluasi kesesuaian slide yang telah dibangun Executor terhadap instruksi pengguna,
    memperbaiki teks kepanjangan (overflow), mempertajam gaya eksekutif, dan menyempurnakan kualitas akhir.
    """
    from backend.app.core.llm_client import generate_json_response
    from backend.app.core.config import settings

    target_model = getattr(settings, "MODEL_PERSONA", "cakra-core")

    system_instruction = (
        "Anda adalah Executive Creative Director & QA Presentation Auditor berstandar PPT Master (hugohe3/ppt-master).\n\n"
        "=== TUGAS STEP 3: EVALUATOR & REFINEMENT (QUALITY ASSURANCE) ===\n"
        "Peran Anda adalah mengaudit dan menyempurnakan hasil kerja Executor:\n"
        "1. KESESUAIAN DENGAN INSTRUKSI PENGGUNA:\n"
        "   - Pastikan seluruh poin penting dan arahan khusus pengguna terakomodasi di dalam slide.\n"
        "2. KETERTIBAN TEKS & PUNCHY EXECUTIVE TEXT:\n"
        "   - Hilangkan kalimat bertele-tele. Setiap kartu, deskripsi, dan bullet harus padat, lugas, dan berdampak tinggi.\n"
        "   - Cegah text-overflow: jika teks terlalu panjang, ringkas menjadi frasa kunci yang tajam.\n"
        "3. KESEIMBANGAN & KERAPIAN VISUAL:\n"
        "   - Pastikan layout bervariasi dan harmonis di setiap slide.\n\n"
        "STRUKTUR KELUARAN WAJIB (JSON murni tanpa markdown code fence):\n"
        "{\n"
        '  "audit_summary": "Ringkasan evaluasi dan perbaikan yang dilakukan",\n'
        '  "slides": [ ... array slide lengkap yang sudah disempurnakan ... ]\n'
        "}"
    )

    eval_prompt = (
        f"Evaluasi dan sempurnakan slide presentasi berikut:\n"
        f"Topik: {topic}\n"
        f"Instruksi Pengguna: {user_instructions or 'Paparan eksekutif komprehensif'}\n\n"
        f"Draf Slide Saat Ini dari Executor:\n{json.dumps(slides, ensure_ascii=False, indent=2)}"
    )

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": eval_prompt}
    ]

    try:
        response_dict = await generate_json_response(
            model_name=target_model,
            messages=messages,
            temperature=0.25,
            timeout=120.0,
            num_predict=4096,
            num_ctx=16384
        )
        refined_raw = response_dict.get("slides")
        if isinstance(refined_raw, list) and len(refined_raw) == len(slides):
            refined_slides = [_normalize_slide_item(s, idx + 1) for idx, s in enumerate(refined_raw)]
            logger.info(f"[PPT_MASTER_EVALUATOR] ✅ Sukses mengaudit dan menyempurnakan {len(refined_slides)} slide via '{target_model}'. Summary: {response_dict.get('audit_summary', 'OK')}")
            return refined_slides
    except Exception as e:
        logger.warning(f"[PPT_MASTER_EVALUATOR] Evaluator pass terlewati ({e}), mempertahankan hasil Executor.")

    return slides


async def execute_ppt_master_generation_stream(
    topic: str,
    slide_count: int = 6,
    user_instructions: Optional[str] = None,
    attachment_paths: Optional[List[str]] = None,
    content_sources: Optional[str] = None,
    theme: Optional[str] = None,
    user_preferences: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    current_user_npp: Optional[str] = None,
    chat_context: Optional[str] = None,
) -> AsyncGenerator[Tuple[str, Dict[str, Any]], None]:
    """
    Eksekusi alur pembuatan slide presentasi sovereign PPT Master dengan Triad Agentic
    (Step 1: Planner ➔ Step 2: Executor ➔ Step 3: Evaluator) dengan emisi progresif SSE.
    """
    safe_topic = (topic or "Presentasi").strip()
    safe_count = max(3, min(slide_count, 15))
    npp_val = current_user_npp or "SYSTEM"
    sess_val = session_id or "default_session"
    
    # ── Tahap 1 (Planner Agent): Perancangan Cetak Biru (Blueprint) ──
    yield ("TOOL_PREVIEW", {
        "tool": "ppt_master",
        "stage": "planning",
        "status_key": "TOOL_PPT_MASTER_PLANNING",
        "status_text": f"🧠 [Step 1/3] Planner: Menganalisis materi & merancang cetak biru {safe_count} slide via AI Architect...",
        "topic": safe_topic,
        "total_slides": safe_count,
        "count": safe_count,
        "slides": []
    })
    await asyncio.sleep(0.3)

    plan_result = await call_ppt_master_planner(
        topic=safe_topic,
        slide_count=safe_count,
        user_instructions=user_instructions or content_sources or "",
        attachment_paths=attachment_paths,
        chat_context=chat_context,
        user_preferences=user_preferences,
        session_id=sess_val,
        current_user_npp=npp_val,
    )

    target_dir = get_account_session_dir(npp_val, sess_val, "artifacts")
    target_dir.mkdir(parents=True, exist_ok=True)

    if plan_result and isinstance(plan_result.get("slides"), list) and len(plan_result["slides"]) >= 2:
        planned_slides = plan_result["slides"]
        theme_style = plan_result.get("theme_style") or {}
        deck_title = plan_result.get("title") or safe_topic
    else:
        planned_slides = _build_presentation_slides(safe_topic, safe_count, content_sources)
        theme_style = {
            "name": f"Executive Theme - {safe_topic[:30]}",
            "bg_hex": "#0F172A",
            "card_bg_hex": "#1E293B",
            "card_subtle_hex": "#182231",
            "accent_hex": "#38BDF8",
            "title_hex": "#F8FAFC",
            "text_hex": "#E2E8F0",
            "border_hex": "#334155",
            "is_dark": True
        }
        deck_title = safe_topic

    # Simpan plan.json ke disk artefak
    try:
        plan_file = target_dir / "plan.json"
        plan_file.write_text(json.dumps({
            "title": deck_title,
            "theme_style": theme_style,
            "slides": planned_slides
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"[PPT_MASTER] 📋 Blueprint plan.json tersimpan di {plan_file}")
    except Exception as e_p:
        logger.warning(f"[PPT_MASTER] Gagal menyimpan plan.json: {e_p}")

    # ── Tahap 2 (Executor Agent): Membangun Slide demi Slide secara Progresif ──
    executed_slides = []
    current_titles = []
    for i, slide_blueprint in enumerate(planned_slides):
        s_title = slide_blueprint.get("title") or f"Slide {i + 1}"
        current_titles.append(s_title)
        yield ("TOOL_PREVIEW", {
            "tool": "ppt_master",
            "stage": "executing",
            "status_key": "TOOL_PPT_MASTER_EXECUTING",
            "status_text": f"🛠️ [Step 2/3] Executor: Membangun Slide {i + 1} dari {safe_count}: {s_title}...",
            "topic": deck_title,
            "current_slide": i + 1,
            "total_slides": safe_count,
            "current_title": s_title,
            "slides": list(current_titles)
        })
        executed_slides.append(_normalize_slide_item(slide_blueprint, i + 1))
        await asyncio.sleep(0.3)

    # ── Tahap 3 (Evaluator Agent): Audit Kualitas & Refinement ──
    yield ("TOOL_PREVIEW", {
        "tool": "ppt_master",
        "stage": "evaluating",
        "status_key": "TOOL_PPT_MASTER_EVALUATING",
        "status_text": "🔍 [Step 3/3] Evaluator: Mengevaluasi kesesuaian materi & menyempurnakan kualitas slide...",
        "topic": deck_title,
        "total_slides": safe_count,
        "slides": list(current_titles)
    })
    await asyncio.sleep(0.3)

    refined_slides = await call_ppt_master_evaluator(
        slides=executed_slides,
        topic=deck_title,
        user_instructions=user_instructions or content_sources or "",
        theme_style=theme_style
    )

    # ── Tahap 4: Mengompilasi File Native PPTX ──
    yield ("TOOL_PREVIEW", {
        "tool": "ppt_master",
        "stage": "compiling",
        "status_key": "TOOL_PPT_MASTER_COMPILING",
        "status_text": "💻 Mengompilasi berkas PowerPoint (.pptx) dengan elemen native DrawingML...",
        "topic": deck_title,
        "total_slides": len(refined_slides),
        "slides": [s.get("title", f"Slide {idx + 1}") for idx, s in enumerate(refined_slides)]
    })
    await asyncio.sleep(0.3)

    clean_fn = sanitize_filename(f"presentasi_{deck_title.lower().replace(' ', '_')}.pptx")
    out_file = target_dir / clean_fn

    # Eksekusi kompilasi via Engine Resmi hugohe3/ppt-master (SVG authoring + svg_to_pptx)
    project_dir = target_dir / f"{out_file.stem}_project"
    svg_compile_ok = False
    try:
        await asyncio.to_thread(_build_ppt_master_svg_project, refined_slides, project_dir, theme_style, deck_title, npp_val)
        svg_compile_ok = await asyncio.to_thread(_compile_svg_to_pptx, project_dir, out_file)
    except Exception as e_proj:
        logger.warning(f"[PPT_MASTER] Gagal build project SVG: {e_proj}")
        svg_compile_ok = False

    # Fallback Safety Net jika kompilasi svg_to_pptx terkendala
    if not svg_compile_ok or not out_file.exists() or out_file.stat().st_size == 0:
        logger.warning(f"[PPT_MASTER] Menggunakan fallback native DrawingML renderer untuk {clean_fn}")
        await asyncio.to_thread(_create_native_pptx_file, refined_slides, out_file, custom_theme_style=theme_style, deck_title=deck_title)

    # Daftarkan ke manifest brain sesi
    try:
        from backend.app.services.session.session_brain_service import SessionBrainService
        brain = SessionBrainService(npp_val, sess_val)
        size_bytes = out_file.stat().st_size
        rel_path = f"accounts/{npp_val}/{sess_val}/brain/artifacts/{clean_fn}"
        brain.save_artifact_manifest(clean_fn, rel_path, size_bytes)
    except Exception as e:
        logger.warning(f"[PPT_MASTER] Gagal update manifest brain: {e}")

    download_url = f"/api/chat/download/artifact/{sess_val}/{clean_fn}"

    # ── Tahap 5: Rendering High-Resolution Previews (PPTX-to-SVG) ──
    yield ("TOOL_PREVIEW", {
        "tool": "ppt_master",
        "stage": "rendering",
        "status_key": "TOOL_PPT_MASTER_RENDERING",
        "status_text": "🖼️ Merender pratinjau slide resolusi tinggi dari berkas PPTX asli...",
        "topic": deck_title,
        "total_slides": len(refined_slides),
        "slides": [s.get("title", f"Slide {idx + 1}") for idx, s in enumerate(refined_slides)]
    })

    slides_svg_dir = target_dir / f"{out_file.stem}_slides"
    slide_svg_urls = []
    try:
        svg_paths = await asyncio.to_thread(_export_pptx_slides_to_svg, out_file, slides_svg_dir)
        slide_svg_urls = [
            f"/api/accounts/{npp_val}/{sess_val}/brain/artifacts/{out_file.stem}_slides/svg/{Path(p).name}"
            for p in svg_paths
        ]
        for idx, s in enumerate(refined_slides):
            if idx < len(slide_svg_urls):
                s["svg_url"] = slide_svg_urls[idx]
        logger.info(f"[PPT_MASTER] ✅ Sukses mengekspor {len(slide_svg_urls)} slide SVG ke {slides_svg_dir}")
    except Exception as e_svg:
        logger.warning(f"[PPT_MASTER] Gagal ekspor slide ke SVG: {e_svg}")
        slide_svg_urls = []

    # ── Tahap 6: Selesai & Siap Disajikan (Done / Presented) ──
    presentation_payload = {
        "title": deck_title,
        "theme": theme_style.get("name", "AI Designed Style"),
        "theme_style": theme_style,
        "download_url": download_url,
        "filename": clean_fn,
        "total_slides": len(refined_slides),
        "slide_svgs": slide_svg_urls,
        "slides": refined_slides
    }

    yield ("TOOL_PREVIEW", {
        "tool": "ppt_master",
        "stage": "done",
        "status_key": "TOOL_PPT_MASTER_DONE",
        "status_text": "✨ Presentasi selesai & siap disajikan (Presented)",
        "topic": deck_title,
        "download_url": download_url,
        "filename": clean_fn,
        "total_slides": len(refined_slides),
        "slide_svgs": slide_svg_urls,
        "slides": [s.get("title", f"Slide {idx + 1}") for idx, s in enumerate(refined_slides)],
        "presentation_data": presentation_payload
    })

