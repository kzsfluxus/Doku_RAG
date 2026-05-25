#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rag_system.py – Doku RAG rendszer központi osztálya.
@author: zsolt
"""

import atexit
import signal
import sys
from pathlib import Path
from typing import Dict, Any
import logging

from doc_loader import (
    clear_cache, should_refresh_data, load_docs, fetch_documents, DOCS_FILE
)
from prompt_builder import build_prompt
from text_cleaner import clean_llm_response
from ollama_runner import run_ollama_model, stop_ollama_model
from embedder import Embedder
from model_loader import get_model

logger = logging.getLogger(__name__)


class RAGInitializationError(Exception):
    pass


class RAGQueryError(Exception):
    pass


class RAGSystem:
    """Doku RAG rendszer központi osztálya."""

    def __init__(self):
        self._docs = None
        self._embedder = None
        self._initialized = False
        self._cleanup_registered = False
        self._cleanup_executed = False

        self._model_name = get_model()
        logger.info("RAG System létrehozva – modell: %s", self._model_name)
        self._register_cleanup()

    @property
    def model_name(self) -> str:
        return self._model_name

    def set_model(self, model_name: str) -> None:
        self._model_name = model_name.strip()

    def reload_model_from_config(self) -> str:
        self._model_name = get_model()
        return self._model_name

    def _register_cleanup(self):
        if not self._cleanup_registered:
            atexit.register(self._cleanup_handler)
            try:
                signal.signal(signal.SIGINT, self._signal_handler)
                signal.signal(signal.SIGTERM, self._signal_handler)
            except ValueError:
                pass
            self._cleanup_registered = True

    def _signal_handler(self, signum, frame):
        self._cleanup_handler()
        sys.exit(0)

    def _cleanup_handler(self):
        if self._cleanup_executed:
            return
        self._cleanup_executed = True
        try:
            stop_ollama_model(self._model_name)
        except Exception as e:
            logger.warning("Cleanup hiba: %s", e)

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def _check_and_refresh_data(self) -> bool:
        try:
            if should_refresh_data():
                logger.info("Dokumentumok feldolgozása...")
                clear_cache()
                docs = fetch_documents()
                if not docs:
                    logger.error("Nem sikerült egyetlen dokumentumot sem beolvasni!")
                    return False
            else:
                logger.info("Cache naprakész.")
            return True
        except Exception as e:
            logger.error("Hiba az adatok frissítése során: %s", e)
            return False

    def _load_documents(self) -> bool:
        try:
            self._docs = load_docs()
            logger.info("Betöltve: %d chunk", len(self._docs))
            return True
        except Exception as e:
            logger.error("Hiba dokumentumok betöltése közben: %s", e)
            return False

    def _initialize_embedder(self) -> bool:
        try:
            self._embedder = Embedder()
            if Path("data/index.faiss").exists() and not should_refresh_data():
                logger.info("Index betöltése...")
                self._embedder.load(
                    index_path=Path("data/index.faiss"),
                    docs_path=DOCS_FILE,
                )
            else:
                logger.info("Index építése...")
                if not self._docs:
                    logger.error("Nincs betöltött dokumentum!")
                    return False
                self._embedder.build_index(self._docs)
                self._embedder.save(
                    index_path=Path("data/index.faiss"),
                    docs_path=DOCS_FILE,
                )
            return True
        except Exception as e:
            logger.error("Hiba az embedder inicializálása során: %s", e)
            return False

    def initialize(self) -> bool:
        try:
            logger.info("RAG rendszer inicializálása...")
            if not self._check_and_refresh_data():
                raise RAGInitializationError("Dokumentumok feldolgozása sikertelen")
            if not self._load_documents():
                raise RAGInitializationError("Dokumentumok betöltése sikertelen")
            if not self._initialize_embedder():
                raise RAGInitializationError("Embedder inicializálása sikertelen")
            self._initialized = True
            logger.info("RAG rendszer kész!")
            return True
        except RAGInitializationError:
            raise
        except Exception as e:
            raise RAGInitializationError(f"Inicializálási hiba: {e}") from e

    def refresh_data(self) -> bool:
        try:
            clear_cache()
            self._initialized = False
            self._docs = None
            self._embedder = None
            return self.initialize()
        except Exception as e:
            logger.error("Hiba az adatfrissítés során: %s", e)
            return False

    def process_question(self, question: str) -> str:
        if not self._initialized:
            raise RAGQueryError("A RAG rendszer nincs inicializálva!")
        if not question or not question.strip():
            return "Kérlek, adj meg egy kérdést!"
        try:
            question = question.strip()
            results = self._embedder.query(question)
            prompt = build_prompt(results, question)
            raw_answer = run_ollama_model(prompt, self._model_name)
            return clean_llm_response(raw_answer)
        except Exception as e:
            raise RAGQueryError(f"Kérdés feldolgozási hiba: {e}") from e

    def get_system_info(self) -> Dict[str, Any]:
        info = {
            "initialized":      self._initialized,
            "documents_loaded": len(self._docs) if self._docs else 0,
            "embedder_ready":   self._embedder is not None,
            "index_exists":     Path("data/index.faiss").exists(),
            "docs_file_exists": DOCS_FILE.exists(),
        }
        if self._docs:
            info["document_titles"] = [d.get("title", "Névtelen") for d in self._docs]
        return info

    def __enter__(self):
        if not self._initialized:
            self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup_handler()
