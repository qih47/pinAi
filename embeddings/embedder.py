# pinAi/embeddings/embedder.py
from sentence_transformers import SentenceTransformer

embedder = SentenceTransformer("intfloat/multilingual-e5-base", device="cuda")
