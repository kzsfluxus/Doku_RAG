#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
embedder.py – Dokumentum vektorok kezelése és keresése.
@author: zsolt
"""

import os
os.environ['PYTHONWARNINGS'] = 'ignore::DeprecationWarning'
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import logging
import json
from pathlib import Path
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

INDEX_PATH = Path('data/index.faiss')
DOCS_PATH  = Path('data/documents.json')


class Embedder:
    """
    Dokumentum embedder osztály FAISS indexszel és sentence transformerrel.
    """

    def __init__(self, embedding_model_name='sentence-transformers/LaBSE'):
        self.model = SentenceTransformer(embedding_model_name)
        self.index = faiss.IndexFlatL2(self.model.get_sentence_embedding_dimension())
        self.documents = []
        logger.info("Embedder inicializálva – modell: %s", embedding_model_name)

    def build_index(self, docs):
        logger.info("Index építése: %d chunk", len(docs))
        self.documents = docs
        if not docs:
            logger.warning("Nincs dokumentum az indexeléshez!")
            return
        embeddings = self.model.encode(
            [doc['text'] for doc in docs], show_progress_bar=False)
        self.index.add(np.array(embeddings).astype('float32'))
        logger.info("Index kész: %d vektor", self.index.ntotal)

    def save(self, index_path=INDEX_PATH, docs_path=DOCS_PATH):
        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            docs_path.parent.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self.index, str(index_path))
            with docs_path.open('w', encoding='utf-8') as f:
                json.dump(self.documents, f, ensure_ascii=False, indent=2)
            logger.info("Index mentve: %d chunk → %s", len(self.documents), index_path)
        except Exception as e:
            logger.error("Hiba index mentése közben: %s", e)
            raise

    def load(self, index_path=INDEX_PATH, docs_path=DOCS_PATH):
        try:
            self.index = faiss.read_index(str(index_path))
            with docs_path.open('r', encoding='utf-8') as f:
                self.documents = json.load(f)
            logger.info("Index betöltve: %d chunk, %d vektor",
                        len(self.documents), self.index.ntotal)
        except FileNotFoundError as e:
            logger.error("Index fájl nem található: %s", e)
            raise
        except Exception as e:
            logger.error("Index betöltési hiba: %s", e)
            raise

    def query(self, question, top_k=3):
        if self.index.ntotal == 0:
            logger.warning("Üres index!")
            return []
        if not self.documents:
            logger.warning("Nincs dokumentum!")
            return []
        try:
            q_embed = self.model.encode(
                [question], show_progress_bar=False).astype('float32')
            distances, indices = self.index.search(q_embed, top_k)
            results = []
            for i, idx in enumerate(indices[0]):
                if 0 <= idx < len(self.documents):
                    results.append(self.documents[idx])
                else:
                    logger.warning("Érvénytelen index: %d", idx)
            logger.info("Keresés: %d találat", len(results))
            return results
        except Exception as e:
            logger.error("Hiba keresés közben: %s", e)
            return []
