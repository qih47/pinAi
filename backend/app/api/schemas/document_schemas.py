from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class DocumentBaseSchema(BaseModel):
    """Base schema untuk document info"""
    title: str = Field(..., min_length=1, max_length=2000, description="Judul dokumen")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi detail dokumen")
    source_type: str = Field("upload", description="Tipe sumber: upload, url, atau internal")
    
    class Config:
        from_attributes = True


class DocumentCreateSchema(DocumentBaseSchema):
    """Schema untuk membuat dokumen baru"""
    file_path: Optional[str] = Field(None, description="Path ke file fisik (jika upload)")
    file_size: int = Field(..., ge=0, description="Ukuran file dalam bytes")
    file_type: str = Field(..., description="MIME type: application/pdf, text/plain, dll")


class DocumentSchema(DocumentBaseSchema):
    """Schema untuk respon read dokumen"""
    id: int = Field(..., description="Document ID")
    file_path: Optional[str] = Field(None, description="Path ke file fisik")
    file_size: int = Field(..., description="Ukuran file dalam bytes")
    file_type: str = Field(..., description="MIME type dokumen")
    created_at: datetime = Field(..., description="Timestamp pembuatan")
    updated_at: Optional[datetime] = Field(None, description="Timestamp update terakhir")
    chunk_count: int = Field(0, description="Jumlah chunks dari dokumen ini")
    embedding_status: str = Field("pending", description="Status embedding: pending, processing, completed, failed")
    nomor: Optional[str] = Field(None, description="Nomor dokumen")
    tanggal: Optional[datetime] = Field(None, description="Tanggal dokumen")
    filename: Optional[str] = Field(None, description="Filename asli dokumen")
    jenis_dokumen: Optional[str] = Field(None, description="Nama jenis dokumen")
    stataktif: Optional[str] = Field(None, description="Status aktif dokumen (batal/obsolete/kosong)")
    
    class Config:
        from_attributes = True


class DocumentListSchema(BaseModel):
    """Schema untuk paginated document list"""
    items: List[DocumentSchema] = Field(..., description="Daftar dokumen")
    total: int = Field(..., description="Total dokumen di database")
    offset: int = Field(..., description="Offset saat ini")
    limit: int = Field(..., description="Limit items per halaman")
    
    class Config:
        from_attributes = True


class DocumentIngestSchema(BaseModel):
    """Schema untuk document ingest (upload + chunk + embed)"""
    title: str = Field(..., min_length=1, max_length=2000, description="Judul dokumen")
    description: Optional[str] = Field(None, max_length=1000, description="Deskripsi dokumen")
    
    class Config:
        from_attributes = True


class DocumentReindexSchema(BaseModel):
    """Schema untuk request re-indexing dokumen"""
    force_rechunk: bool = Field(False, description="Apakah perlu re-chunk ulang dari file")
    
    class Config:
        from_attributes = True


class DocumentDeleteSchema(BaseModel):
    """Schema untuk delete dokumen dengan cascade"""
    delete_file: bool = Field(True, description="Hapus file fisik juga dari storage")
    
    class Config:
        from_attributes = True


class DocumentChunkSchema(BaseModel):
    """Schema untuk dokumen chunk"""
    id: int = Field(..., description="Chunk ID")
    document_id: int = Field(..., description="Document ID")
    chunk_index: int = Field(..., description="Nomor chunk (0-indexed)")
    content: str = Field(..., description="Isi teks chunk")
    embedding_vector: Optional[List[float]] = Field(None, description="Embedding vector (opsional untuk list)")
    
    class Config:
        from_attributes = True


class DocumentStatsSchema(BaseModel):
    """Schema untuk document statistics"""
    total_documents: int = Field(..., description="Total dokumen")
    total_chunks: int = Field(..., description="Total chunks")
    total_file_size: int = Field(..., description="Total ukuran file (bytes)")
    documents_pending: int = Field(..., description="Dokumen pending embedding")
    documents_completed: int = Field(..., description="Dokumen completed embedding")
    documents_failed: int = Field(..., description="Dokumen failed embedding")
    
    class Config:
        from_attributes = True
