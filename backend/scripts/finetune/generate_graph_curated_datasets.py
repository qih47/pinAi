#!/usr/bin/env python3
"""
CAKRA AI — Knowledge Graph Curated Dataset Generator (Core & Router)
===================================================================
Mengekstrak data relasi otentik dari PostgreSQL `ragdb` (knowledge_graph_edges & knowledge_graph_nodes)
untuk melatih model `cakra-core` (Call 2) dan `cakra-router` (Call 1).

Fitur:
1. Core Graph Enriched (~500 sampel):
   - CoT penalaran <think> yang mengurai relasi struktural, divisi, wewenang, dan regulasi.
   - Jawaban elaboratif, profesional (anti-brevity), dengan diagram alur relasi (Mermaid/tabel).
   - Digabungkan dengan data/finetune/curated_cakra_core_2000.jsonl -> data/finetune/curated_cakra_core_2500.jsonl.
2. Router Graph Aware (~800 sampel):
   - Klasifikasi deterministik sparse JSON untuk kueri kewenangan, struktur divisi, dan bagan alur.
   - Mengaktifkan need_rag: true, requires_visual: true, visual_types: ["mermaid"].
   - Menghasilkan data/finetune/curated_cakra_router_3000.jsonl.
"""

import os
import sys
import json
import random
import asyncio
import argparse
from typing import List, Dict, Any, Tuple
from pathlib import Path

# Add backend to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.services.training.nightly.db_setup import get_ragdb_conn

CORE_SYSTEM_PROMPT = (
    "Kamu adalah CAKRA AI, asisten kecerdasan buatan berdaulat PT PINDAD. "
    "Sebelum menjawab, lakukan penalaran mendalam di dalam tag <think>...</think> "
    "lalu sajikan jawaban yang komprehensif, mengalir secara natural dan dinamis, profesional, serta akurat. "
    "Bersikaplah adaptif: jelaskan secara kaya, kontekstual, dan elaboratif secara default; "
    "sajikan secara ringkas/to-the-point HANYA jika pengguna secara eksplisit memintanya."
)

ROUTER_SYSTEM_PROMPT = (
    "Kamu adalah Cakra Router (Call 1) yang sangat presisi dan deterministik. "
    "Analisis pesan pengguna dan kembalikan sparse JSON routing payload murni."
)


async def fetch_graph_relation_clusters(min_edges_per_doc: int = 2, max_clusters: int = 600) -> List[Dict[str, Any]]:
    """
    Mengelompokkan relasi Knowledge Graph per dokumen yang memiliki entitas divisi, wewenang, dan kewajiban.
    """
    print("🔍 Mengambil kluster relasi Knowledge Graph otentik dari ragdb...")
    async with get_ragdb_conn() as conn:
        rows = await conn.fetch("""
            SELECT 
                d.id as doc_id,
                COALESCE(d.judul, 'Pedoman Operasional PT Pindad') as doc_title,
                COALESCE(d.nomor, '-') as doc_number,
                sn.entity_name as source_name,
                sn.entity_type as source_type,
                e.relation_type,
                tn.entity_name as target_name,
                tn.entity_type as target_type
            FROM knowledge_graph_edges e
            JOIN knowledge_graph_nodes sn ON e.source_node_id = sn.id
            JOIN knowledge_graph_nodes tn ON e.target_node_id = tn.id
            JOIN dokumen d ON e.dokumen_id = d.id
            WHERE e.relation_type IN (
                'BERTANGGUNG_JAWAB', 'MENGATUR', 'MENETAPKAN', 'MENYETUJUI', 
                'MENERBITKAN', 'SANKSI_UNTUK', 'MENGESAHKAN', 'BERTANGGUNG_JAWAB_ATAS'
            )
              AND LENGTH(sn.entity_name) > 3
              AND LENGTH(tn.entity_name) > 3
              AND sn.entity_name != tn.entity_name
            LIMIT 50000
        """)

    # Kelompokkan berdasarkan doc_id
    clusters_by_doc: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        did = r["doc_id"]
        if did not in clusters_by_doc:
            clusters_by_doc[did] = {
                "doc_id": did,
                "doc_title": r["doc_title"].strip(),
                "doc_number": r["doc_number"].strip(),
                "relations": []
            }
        clusters_by_doc[did]["relations"].append({
            "source_name": r["source_name"].strip(),
            "source_type": r["source_type"].strip(),
            "relation_type": r["relation_type"].strip(),
            "target_name": r["target_name"].strip(),
            "target_type": r["target_type"].strip(),
        })

    valid_clusters = [
        c for c in clusters_by_doc.values() 
        if len(c["relations"]) >= min_edges_per_doc
    ]
    random.shuffle(valid_clusters)
    print(f"✅ Ditemukan {len(valid_clusters)} kluster dokumen dengan relasi Knowledge Graph aktif.")
    return valid_clusters[:max_clusters]


def build_core_graph_sample(cluster: Dict[str, Any]) -> Dict[str, Any]:
    """Membangun 1 sampel Core dengan penalaran CoT berbasis Knowledge Graph & Mermaid."""
    doc_id = cluster["doc_id"]
    doc_title = cluster["doc_title"]
    doc_number = cluster["doc_number"]
    relations = cluster["relations"][:5]

    # Ambil sumber dan target utama
    primary_rel = relations[0]
    src_actor = primary_rel["source_name"]
    rel_verb = primary_rel["relation_type"].replace("_", " ").lower()
    tgt_obj = primary_rel["target_name"]

    # Variasi pertanyaan pengguna mengenai kewenangan / alur
    q_templates = [
        f"Bagaimana pembagian kewenangan dan tanggung jawab terkait {tgt_obj} menurut regulasi perusahaan?",
        f"Siapa pihak atau fungsi yang {rel_verb} dalam pelaksanaan {tgt_obj} dan bagaimana alur kerjanya?",
        f"Jelaskan struktur penanggung jawab dan tata kelola untuk {tgt_obj} pada {doc_title}.",
        f"Berdasarkan dokumen {doc_number}, apa peran dan tugas dari {src_actor} serta unit terkait lainnya?",
        f"Bagaimana alur koordinasi dan hierarki tanggung jawab antara {src_actor} dengan pihak terkait dalam {tgt_obj}?"
    ]
    user_query = random.choice(q_templates)

    # Format ringkasan Knowledge Graph
    graph_lines = ["[PETA RELASI STRUKTUR & KEWENANGAN (KNOWLEDGE GRAPH)]"]
    mermaid_nodes = []
    mermaid_edges = []
    
    for i, r in enumerate(relations):
        graph_lines.append(
            f"• [{r['source_type']}: {r['source_name']}] ──({r['relation_type']})──► [{r['target_type']}: {r['target_name']}] (Dasar: {doc_number})"
        )
        s_id = f"A{i}"
        t_id = f"B{i}"
        mermaid_nodes.append(f'    {s_id}["{r["source_name"][:35]}"]')
        mermaid_nodes.append(f'    {t_id}["{r["target_name"][:35]}"]')
        mermaid_edges.append(f'    {s_id} -->|{r["relation_type"]}| {t_id}')

    graph_block = "\n".join(graph_lines)
    
    # Diagram Mermaid ringkas
    mermaid_unique_nodes = list(dict.fromkeys(mermaid_nodes))[:6]
    mermaid_diagram = "```mermaid\ngraph TD\n" + "\n".join(mermaid_unique_nodes) + "\n" + "\n".join(mermaid_edges[:4]) + "\n```"

    # CoT Reasoning di dalam <think>
    thought = (
        f"1. Analisis Kebutuhan: Pengguna menanyakan alur tanggung jawab, hierarki kewenangan, atau peran unit kerja mengenai '{tgt_obj}'.\n"
        f"2. Peta Knowledge Graph & Rujukan Dokumen:\n"
        f"   - Dokumen Acuan: '{doc_title}' (Nomor: {doc_number}).\n"
        f"   - Relasi Kunci Graph: {src_actor} ({primary_rel['source_type']}) memiliki keterikatan langsung '{primary_rel['relation_type']}' terhadap {tgt_obj}.\n"
        f"   - Teridentifikasi {len(relations)} simpul relasi kewenangan dalam kluster regulasi ini.\n"
        f"3. Verifikasi Substansi & Pembagian Wewenang:\n"
        f"   - {src_actor} bertindak sebagai leading unit/eksekutor sesuai ketentuan operasional.\n"
        f"   - Terdapat keterkaitan proses antar fungsi guna menjamin kepatuhan (compliance), mitigasi risiko, dan tata kelola yang tertib.\n"
        f"4. Strategi Respon:\n"
        f"   - Awali dengan konfirmasi dasar regulasi resmi perusahaan.\n"
        f"   - Jabarkan rincian pembagian peran dan tanggung jawab secara komprehensif (anti-singkat).\n"
        f"   - Tampilkan diagram alur hubungan kewenangan (Mermaid diagram) untuk kejelasan visual.\n"
        f"   - Berikan rekomendasi operasional dan sitasi resmi dokumen."
    )

    # Uraian poin tanggung jawab
    bullet_items = []
    for r in relations:
        bullet_items.append(
            f"- **{r['source_name']} ({r['source_type']}):** Memiliki kewenangan dan mandat resmi untuk **{r['relation_type'].replace('_', ' ').lower()}** terkait *{r['target_name']}* sesuai batas yurisdiksi kerja yang ditetapkan."
        )
    bullets_text = "\n".join(bullet_items)

    response_text = (
        f"Berdasarkan dokumen pedoman resmi **{doc_title}** (Nomor: `{doc_number}`), berikut adalah uraian komprehensif mengenai pembagian kewenangan dan alur tanggung jawab terkait:\n\n"
        f"### 🏛️ Struktur Kewenangan & Penanggung Jawab\n"
        f"{bullets_text}\n\n"
        f"### 🔄 Bagan Alur Koordinasi & Hierarki Kewenangan\n"
        f"{mermaid_diagram}\n\n"
        f"### 💡 Ketentuan & Prosedur Operasional:\n"
        f"1. **Pemisahan Fungsi & Validasi Bertingkat:** Setiap tahapan kewenangan wajib divalidasi oleh pejabat berwenang sebelum proses administrasi/operasional dieksekusi ke tahap selanjutnya.\n"
        f"2. **Dokumentasi & Audit Trail:** Seluruh dokumen pendukung, berita acara, atau pengajuan persetujuan wajib diarsipkan secara sistematis guna keperluan audit kepatuhan internal PT Pindad.\n\n"
        f"<sources_json>[{{\"id\": {doc_id}, \"judul\": \"{doc_title}\", \"nomor\": \"{doc_number}\", \"halaman\": \"1-5\"}}]</sources_json>"
    )

    return {
        "conversations": [
            {"from": "system", "value": CORE_SYSTEM_PROMPT},
            {"from": "human", "value": f"{graph_block}\n\nPertanyaan: {user_query}"},
            {"from": "gpt", "value": f"<think>\n{thought}\n</think>\n\n{response_text}"}
        ]
    }


def build_router_graph_sample(cluster: Dict[str, Any]) -> Dict[str, Any]:
    """Membangun 1 sampel Router deterministik dengan sparse JSON untuk kueri kewenangan/grafik."""
    doc_title = cluster["doc_title"]
    doc_number = cluster["doc_number"]
    rel = cluster["relations"][0]
    src_actor = rel["source_name"]
    rel_verb = rel["relation_type"].replace("_", " ").lower()
    tgt_obj = rel["target_name"]

    user_queries = [
        f"siapa pihak yang bertanggung jawab atas {tgt_obj} di {doc_title}?",
        f"bagaimana alur kewenangan {src_actor} dalam {tgt_obj}?",
        f"gambarkan diagram bagan penanggung jawab untuk {tgt_obj} sesuai aturan",
        f"divisi apa yang {rel_verb} pelaksanaan {tgt_obj}?",
        f"tampilkan flowchart alur koordinasi {src_actor} pada regulasi {doc_number}"
    ]
    user_msg = random.choice(user_queries)
    is_flowchart_requested = any(w in user_msg.lower() for w in ["diagram", "bagan", "flowchart", "alur"])

    sparse_json = {
        "active_topic": "Struktur Kewenangan & Prosedur",
        "key_subject": f"Kewenangan {src_actor} Terkait {tgt_obj[:40]}",
        "need_rag": True,
        "query_judul": [doc_title[:60]],
    }
    if is_flowchart_requested:
        sparse_json["requires_visual"] = True
        sparse_json["visual_types"] = ["mermaid"]

    return {
        "conversations": [
            {"from": "system", "value": ROUTER_SYSTEM_PROMPT},
            {"from": "human", "value": user_msg},
            {"from": "gpt", "value": json.dumps(sparse_json, ensure_ascii=False)}
        ]
    }


async def main():
    parser = argparse.ArgumentParser(description="Generate Curated Graph Datasets for Core & Router")
    parser.add_argument("--core-target", type=int, default=500, help="Jumlah sampel Core tambahan")
    parser.add_argument("--router-target", type=int, default=800, help="Jumlah sampel Router tambahan")
    parser.add_argument("--existing-core", type=str, default="data/finetune/curated_cakra_core_2000.jsonl", help="File dataset core yang sudah ada")
    parser.add_argument("--output-core", type=str, default="data/finetune/curated_cakra_core_2500.jsonl", help="File output dataset core gabungan")
    parser.add_argument("--output-router", type=str, default="data/finetune/curated_cakra_router_3500.jsonl", help="File output dataset router gabungan")
    args = parser.parse_args()

    print("=================================================================")
    print("🚀 GENERASI DATASET TERKURASI BERBASIS KNOWLEDGE GRAPH (CORE & ROUTE)")
    print("=================================================================")

    # 1. Ambil kluster relasi dari database
    clusters = await fetch_graph_relation_clusters(min_edges_per_doc=2, max_clusters=max(args.core_target, args.router_target) + 100)
    if not clusters:
        print("❌ Tidak ada kluster relasi yang ditemukan. Batalkan proses.")
        return

    # 2. Bangkitkan sampel Core
    print(f"\n🧠 Membangkitkan {args.core_target} sampel Core Graph Reasoning...")
    core_samples = []
    for c in clusters[:args.core_target]:
        core_samples.append(build_core_graph_sample(c))
    print(f"✅ Selesai membangkitkan {len(core_samples)} sampel Core.")

    # 3. Gabungkan dengan dataset Core yang ada (2.000 sampel)
    existing_core_path = Path(args.existing_core)
    combined_core = []
    if existing_core_path.exists():
        print(f"📂 Membaca dataset core yang sudah ada dari {existing_core_path}...")
        with open(existing_core_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    combined_core.append(json.loads(line_str))
        print(f"   Memuat {len(combined_core)} sampel eksisting.")
    else:
        print(f"⚠️ File {existing_core_path} tidak ditemukan, membuat dari nol.")

    combined_core.extend(core_samples)
    random.shuffle(combined_core)

    output_core_path = Path(args.output_core)
    output_core_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_core_path, "w", encoding="utf-8") as f:
        for item in combined_core:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"🎉 Dataset Core gabungan berhasil disimpan di: {output_core_path} ({len(combined_core)} baris).")

    # 4. Bangkitkan sampel Router
    print(f"\n🧭 Membangkitkan {args.router_target} sampel Router Graph-Aware...")
    router_samples = []
    for c in clusters[:args.router_target]:
        router_samples.append(build_router_graph_sample(c))
    
    # Tambahkan variasi router umum (agar tidak overfit hanya ke kueri kewenangan)
    from backend.scripts.finetune.generate_dispatcher_dataset import generate_sample as gen_disp_sample
    general_types = ["DOCUMENTS", "WEB_SEARCH", "CODING", "EMAIL", "DOCWRITER", "URL_READ"]
    for _ in range(args.router_target):
        stype = random.choice(general_types)
        router_samples.append(gen_disp_sample(stype))

    random.shuffle(router_samples)
    print(f"✅ Selesai membangkitkan {len(router_samples)} sampel Router terkurasi.")

    # Gabungkan dengan dataset router yang ada jika ada (misal call1_train_3000.jsonl)
    existing_router_path = Path("data/finetune/call1_train_3000.jsonl")
    combined_router = []
    if existing_router_path.exists():
        print(f"📂 Menggabungkan dengan {existing_router_path}...")
        with open(existing_router_path, "r", encoding="utf-8") as f:
            for line in f:
                l_str = line.strip()
                if l_str:
                    combined_router.append(json.loads(l_str))
    combined_router.extend(router_samples)
    random.shuffle(combined_router)

    output_router_path = Path(args.output_router)
    with open(output_router_path, "w", encoding="utf-8") as f:
        for item in combined_router:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"🎉 Dataset Router gabungan berhasil disimpan di: {output_router_path} ({len(combined_router)} baris).")

    print("\n=================================================================")
    print("✅ SELURUH DATASET GRAPH CORE & ROUTER BERHASIL DIBUAT DAN DIGABUNGKAN!")
    print(f"   • File Core   : {output_core_path} (Total: {len(combined_core)} sampel)")
    print(f"   • File Router : {output_router_path} (Total: {len(combined_router)} sampel)")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(main())
