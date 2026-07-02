import logging
from backend.app.core.database import get_db
from backend.app.services.rag.rag_service import rag_service

logger = logging.getLogger("CAKRA_DOC_MANAGER")

class DocumentManager:
    async def process_document_background(self, doc_id: int, file_path: str):
        """
        Background task: chunk dokumen + embed chunks.
        Dijalankan async tanpa menunggu response endpoint.
        """
        try:
            logger.info(f"🔄 [BG] Starting document processing: {doc_id}")
            
            # 1. Extract text dari file
            from backend.app.services.pipeline import extract_pdf_text
            text_content = await extract_pdf_text(file_path)
            
            if not text_content:
                logger.warning(f"⚠️ [BG] No text extracted from {file_path}")
                async with get_db() as conn:
                    await conn.execute(
                        "UPDATE dokumen SET embedding_status = $1 WHERE id = $2",
                        "failed",
                        doc_id,
                    )
                return
            
            # 2. Chunk dokumen
            from backend.app.services.document_chunking.manager import chunk_text
            chunks = await chunk_text(text_content)
            
            logger.info(f"✂️ [BG] Created {len(chunks)} chunks for document {doc_id}")
            
            # 3. Embed chunks
            async with get_db() as conn:
                async with conn.transaction():
                    for idx, chunk_text_content in enumerate(chunks):
                        # Get embedding dari rag_service
                        embedding = await rag_service.embed_text(chunk_text_content)
                        
                        # Insert chunk
                        await conn.execute(
                            """
                            INSERT INTO dokumen_chunk (dokumen_id, chunk_index, content, embedding)
                            VALUES ($1, $2, $3, $4)
                            """,
                            doc_id,
                            idx,
                            chunk_text_content,
                            embedding,  # pgvector format
                        )
                    
                    # Update dokumen status to completed
                    await conn.execute(
                        "UPDATE dokumen SET embedding_status = $1, updated_at = NOW() WHERE id = $2",
                        "completed",
                        doc_id,
                    )
            
            logger.info(f"✅ [BG] Document {doc_id} processing completed")
        
        except Exception as e:
            logger.error(f"❌ [BG] Document processing failed: {e}")
            async with get_db() as conn:
                await conn.execute(
                    "UPDATE dokumen SET embedding_status = $1 WHERE id = $2",
                    "failed",
                    doc_id,
                )

    async def reindex_document_background(self, doc_id: int, force_rechunk: bool):
        """
        Background task: re-embed existing dokumen chunks.
        """
        try:
            logger.info(f"🔄 [BG] Starting reindex: {doc_id} (force_rechunk={force_rechunk})")
            
            async with get_db() as conn:
                if force_rechunk:
                    # Delete old chunks
                    await conn.execute(
                        "DELETE FROM dokumen_chunk WHERE dokumen_id = $1",
                        doc_id,
                    )
                    
                    # Get file path dan re-process
                    file_path = await conn.fetchval(
                        "SELECT file_path FROM dokumen WHERE id = $1",
                        doc_id,
                    )
                    
                    # Trigger full processing
                    await self.process_document_background(doc_id, file_path)
                else:
                    # Just re-embed existing chunks
                    chunks = await conn.fetch(
                        "SELECT id, content FROM dokumen_chunk WHERE dokumen_id = $1 ORDER BY chunk_index",
                        doc_id,
                    )
                    
                    for chunk in chunks:
                        embedding = await rag_service.embed_text(chunk["content"])
                        await conn.execute(
                            "UPDATE dokumen_chunk SET embedding = $1 WHERE id = $2",
                            embedding,
                            chunk["id"],
                        )
                    
                    # Mark as completed
                    await conn.execute(
                        "UPDATE dokumen SET embedding_status = $1, updated_at = NOW() WHERE id = $2",
                        "completed",
                        doc_id,
                    )
            
            logger.info(f"✅ [BG] Reindex completed for document {doc_id}")
        
        except Exception as e:
            logger.error(f"❌ [BG] Reindex failed: {e}")
            async with get_db() as conn:
                await conn.execute(
                    "UPDATE dokumen SET embedding_status = $1 WHERE id = $2",
                    "failed",
                    doc_id,
                )

document_manager = DocumentManager()
