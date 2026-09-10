"""
CAKRA AI — Nightly Training & Fine-Tuning Package
=================================================
Dedicated isolated pipeline for 5-worker synchronized training:
- Worker 1: Text RAG (Hierarchical Chunker + Vector Embedding)
- Worker 2: Synthetic Q&A (Unlimited Q&A pairs via Gemma-4 31B)
- Worker 3: Graph RAG (Knowledge Graph Entity & Relationship Extraction)
- Worker 4: Vision RAG (Page visual feature embedding)
- Worker 5: LoRA Fine-Tuning (Instruction Tuning dataset generator & QLoRA trainer)
"""

from .orchestrator import NightlyTrainingOrchestrator

__all__ = ["NightlyTrainingOrchestrator"]
