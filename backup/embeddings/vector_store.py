import psycopg2
from psycopg2.extras import Json
import hashlib
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
from .chunk_se import chunk_se
from ..database.db import get_db

EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-m3")

def insert_se_document(text: str, doc_metadata: Dict[str, Any]) -> int:
    """
    Insert Surat Edaran document into database with proper chunking and embeddings.
    
    Args:
        text: Full text of the Surat Edaran
        doc_metadata: Document metadata including title, number, date, etc.
    
    Returns:
        int: Document ID of the inserted document
    """
    # Chunk the SE document
    sections = chunk_se(text)
    
    # Prepare document metadata
    metadata = {
        "doc_type": "SE",
        "nomor": doc_metadata.get("nomor"),
        "tanggal": doc_metadata.get("tanggal"),
        "tentang": doc_metadata.get("tentang"),
        "judul": doc_metadata.get("judul", doc_metadata.get("tentang")),
        "filename": doc_metadata.get("filename", "surat_edaran.txt")
    }
    
    # Prepare chunks with metadata
    chunks_with_meta = []
    for i, sec in enumerate(sections):
        if not sec["content"].strip():
            continue
        chunk_meta = metadata.copy()
        chunk_meta.update({
            "chunk_id": i + 1,
            "content": sec["content"],
            "section_type": sec["type"],
            "section_title": sec["title"],
            "level": sec["level"],
            "order": sec["order"],
            "parent_id": sec["parent_id"]
        })
        chunks_with_meta.append(chunk_meta)

    # Connect to database and insert
    conn = get_db()
    cur = conn.cursor()

    try:
        # Insert document record first
        cur.execute("""
            INSERT INTO dokumen (
                judul, nomor, id_jenis, tanggal, tempat,
                filename, clean_text, status_ocr,
                ocr_text_length, last_processed, ocr_page_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'cleaned', %s, NOW(), %s)
            RETURNING id
        """, (
            metadata["judul"] or "Surat Edaran",
            metadata["nomor"] or "SE-Unknown",
            2,  # SE type (assuming SKEP is type 1, SE is type 2)
            metadata["tanggal"],
            doc_metadata.get("tempat", "Indonesia"),
            metadata["filename"],
            text,
            len(text),
            0
        ))
        dokumen_id = cur.fetchone()[0]

        # Insert sections
        section_ids = {}
        temp_sections = []

        for chunk in chunks_with_meta:
            content = chunk["content"]
            if not content.strip():
                continue

            section_type = chunk.get("section_type", "bagian")
            section_title = chunk.get("section_title", f"Bagian {chunk['chunk_id']}")
            section_order = chunk["order"]
            parent_id = chunk.get("parent_id")

            cur.execute("""
                INSERT INTO dokumen_section (
                    dokumen_id, section_type, section_title, content, section_order, parent_id
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                dokumen_id,
                section_type,
                section_title,
                content,
                section_order,
                parent_id
            ))
            sec_id = cur.fetchone()[0]

            temp_sections.append((sec_id, parent_id, section_title, section_order))
            section_ids[(section_title, section_order)] = sec_id

        # Insert chunks with embeddings
        for chunk in chunks_with_meta:
            content = chunk["content"]
            if not content.strip():
                continue

            text_hash = hashlib.md5(content.encode()).hexdigest()
            embedding = EMBEDDING_MODEL.encode(content).tolist()

            # Prepare metadata for the chunk
            chunk_metadata = {
                "section_type": chunk["section_type"],
                "section_title": chunk["section_title"],
                "level": chunk["level"],
                "order": chunk["order"],
                "parent_id": chunk["parent_id"],
                "doc_type": "SE"
            }
            
            cur.execute("""
                INSERT INTO dokumen_chunk (
                    dokumen_id, chunk_id, content, metadata,
                    embedding, embedding_model, chunk_size, text_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                dokumen_id,
                chunk["chunk_id"],
                content,
                Json(chunk_metadata),
                embedding,
                "BAAI/bge-m3",
                len(content),
                text_hash
            ))

        conn.commit()
        cur.close()
        conn.close()

        return dokumen_id

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise e