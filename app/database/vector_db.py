import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from typing import List, Dict
from loguru import logger

class VectorDatabase:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = faiss.IndexFlatL2(384)  # Dimension pour le modèle
        self.jobs = []  # Liste des jobs pour mapping

    def add_job(self, job: Dict):
        """Ajoute un job à la DB vectorielle"""
        text = f"{job['title']} {job['company']} {job['description']}"
        embedding = self.model.encode([text])[0]
        self.index.add(np.array([embedding]).astype('float32'))
        self.jobs.append(job)

    def find_similar(self, job: Dict, threshold: float = 0.8) -> List[Dict]:
        """Trouve des jobs similaires"""
        text = f"{job['title']} {job['company']} {job['description']}"
        embedding = self.model.encode([text])[0]
        distances, indices = self.index.search(np.array([embedding]).astype('float32'), k=5)

        similar = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(self.jobs) and dist < threshold:
                similar.append(self.jobs[idx])
        return similar