import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import os

model_text = SentenceTransformer('all-MiniLM-L6-v2')
with open('d:/LUAN_AN/vector_store.pkl', 'rb') as f:
    store_text = pickle.load(f)

def test_search(query, top_k=7):
    query_embedding = model_text.encode([query])
    similarities = cosine_similarity(query_embedding, store_text['embeddings'])[0]
    top_indices = similarities.argsort()[-top_k:][::-1]
    
    for idx in top_indices:
        print(f"Score: {similarities[idx]:.4f} - {store_text['texts'][idx][:100]}...")

test_search("tầm 20 triệu")
