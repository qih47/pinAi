-- CAKRA AI: Nightly Training Schema for ragdb ONLY
CREATE TABLE IF NOT EXISTS nightly_training_checkpoints (
    dokumen_id INT PRIMARY KEY,
    judul TEXT,
    nomor_dokumen VARCHAR(255),
    file_path TEXT,
    total_pages INT NOT NULL DEFAULT 0,
    last_completed_page INT NOT NULL DEFAULT 0,
    pending_buffer JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(30) DEFAULT 'PENDING',
    is_berlaku BOOLEAN DEFAULT TRUE,
    w1_text_status VARCHAR(20) DEFAULT 'PENDING',
    w2_qa_status VARCHAR(20) DEFAULT 'PENDING',
    w3_graph_status VARCHAR(20) DEFAULT 'PENDING',
    w4_vision_status VARCHAR(20) DEFAULT 'PENDING',
    w5_lora_status VARCHAR(20) DEFAULT 'PENDING',
    qa_count INT DEFAULT 0,
    graph_nodes_count INT DEFAULT 0,
    last_synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_nightly_ckpt_status ON nightly_training_checkpoints(status);
CREATE INDEX IF NOT EXISTS idx_nightly_ckpt_berlaku ON nightly_training_checkpoints(is_berlaku);

CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
    id SERIAL PRIMARY KEY,
    dokumen_id INT,
    page_number INT,
    page_range VARCHAR(50),
    entity_name TEXT NOT NULL,
    entity_type VARCHAR(50),
    properties JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_doc ON knowledge_graph_nodes(dokumen_id);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_entity ON knowledge_graph_nodes(entity_name);

CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
    id SERIAL PRIMARY KEY,
    source_node_id INT REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
    target_node_id INT REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
    relation_type VARCHAR(50),
    weight FLOAT DEFAULT 1.0,
    dokumen_id INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_kg_edges_doc ON knowledge_graph_edges(dokumen_id);
CREATE INDEX IF NOT EXISTS idx_kg_edges_rel ON knowledge_graph_edges(relation_type);

CREATE TABLE IF NOT EXISTS nightly_training_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(30) DEFAULT 'RUNNING',
    current_doc_id INT,
    total_docs_processed INT DEFAULT 0,
    total_pages_processed INT DEFAULT 0,
    total_qa_generated INT DEFAULT 0,
    vram_status JSONB DEFAULT '{}'::jsonb,
    logs TEXT
);

-- Lineage & Priority Tier Migration for nightly_training_checkpoints
ALTER TABLE nightly_training_checkpoints ADD COLUMN IF NOT EXISTS priority_tier INT DEFAULT 1;
ALTER TABLE nightly_training_checkpoints ADD COLUMN IF NOT EXISTS mencabut_ids TEXT;
ALTER TABLE nightly_training_checkpoints ADD COLUMN IF NOT EXISTS revoked_by_ids TEXT;
ALTER TABLE nightly_training_checkpoints ADD COLUMN IF NOT EXISTS latest_active_id INT;
ALTER TABLE nightly_training_checkpoints ADD COLUMN IF NOT EXISTS linkper TEXT;

CREATE INDEX IF NOT EXISTS idx_nightly_priority ON nightly_training_checkpoints(priority_tier, is_berlaku, status);


ALTER TABLE dokumen ADD COLUMN IF NOT EXISTS is_berlaku BOOLEAN DEFAULT TRUE;
ALTER TABLE dokumen ADD COLUMN IF NOT EXISTS file_path TEXT;
ALTER TABLE rag_document_questions ADD COLUMN IF NOT EXISTS answer TEXT;
ALTER TABLE rag_document_questions ADD COLUMN IF NOT EXISTS page_range VARCHAR(50);
