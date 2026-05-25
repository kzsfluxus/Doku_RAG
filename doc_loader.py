#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
doc_loader.py – Könyvtárbejárás, chunk-olás és cache-kezelés a Doku RAG rendszerhez.
@author: zsolt

Felelősségei:
- Konfiguráció beolvasása és az engedélyezett könyvtárak meghatározása.
- Fájlrendszer hierarchikus bejárása a max_depth korlátig.
- Kinyert szövegek darabolása (chunk-olás) a CHUNK_SIZE és CHUNK_OVERLAP
  paraméterek alapján.
- JSON cache mentése és betöltése.
- Frissítési szükségesség eldöntése: config mtime + fájl-snapshot összehasonlítás.

A szöveg tényleges kinyerését az `extractors` modul végzi.
"""

import json
import logging
import os
import configparser
import shutil
from pathlib import Path

from extractors import extract_text, SUPPORTED_EXTENSIONS
from text_cleaner import clean_extracted_text

logger = logging.getLogger(__name__)

DOCS_FILE     = Path("data/documents.json")
SNAPSHOT_FILE = Path("data/file_snapshot.json")
CONFIG_FILE   = Path("doku_rag.ini")

DEFAULT_CHUNK_SIZE    = 1000
DEFAULT_CHUNK_OVERLAP = 150


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config(path=CONFIG_FILE) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(path, encoding="utf-8")
    return config


def _get_allowed_dirs(config: configparser.ConfigParser) -> dict:
    allowed = {}
    for section in config.sections():
        if section == "dir":
            desc = config.get(section, "description", fallback="").strip()
            if desc:
                allowed[""] = desc
        elif section.startswith("dir."):
            rel = section[4:].replace(".", os.sep)
            desc = config.get(section, "description", fallback="").strip()
            if desc:
                allowed[rel] = desc
    return allowed


def _get_extensions(config: configparser.ConfigParser) -> set:
    raw = config.get("documents", "extensions", fallback="").strip()
    if not raw:
        return SUPPORTED_EXTENSIONS
    requested = {e.strip().lstrip(".").lower() for e in raw.split(",") if e.strip()}
    unsupported = requested - SUPPORTED_EXTENSIONS
    if unsupported:
        logger.warning("Nem támogatott kiterjesztések (figyelmen kívül hagyva): %s", unsupported)
    return requested & SUPPORTED_EXTENSIONS


def _get_chunk_params(config: configparser.ConfigParser) -> tuple:
    size    = config.getint("documents", "chunk_size",    fallback=DEFAULT_CHUNK_SIZE)
    overlap = config.getint("documents", "chunk_overlap", fallback=DEFAULT_CHUNK_OVERLAP)
    return size, overlap


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_text(text: str, chunk_size: int, overlap: int) -> list:
    if len(text) <= chunk_size:
        return [text]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""

    for para in paragraphs:
        if len(para) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""
            for i in range(0, len(para), chunk_size - overlap):
                chunks.append(para[i:i + chunk_size])
            current = para[-overlap:] if overlap else ""
            continue

        if len(current) + len(para) + 2 > chunk_size:
            chunks.append(current.strip())
            current = (current[-overlap:] + "\n\n" + para) if overlap else para
        else:
            current = (current + "\n\n" + para).lstrip()

    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if c]


# ---------------------------------------------------------------------------
# Directory walker
# ---------------------------------------------------------------------------

def _build_doc_entry(file, dir_description, chunk_text, chunk_index, total_chunks):
    suffix = f" [{chunk_index + 1}/{total_chunks}]" if total_chunks > 1 else ""
    return {
        "title":           f"{dir_description} / {file.name}{suffix}",
        "text":            chunk_text,
        "path":            str(file),
        "dir_description": dir_description,
        "chunk_index":     chunk_index,
        "total_chunks":    total_chunks,
    }


def scan_documents(config: configparser.ConfigParser) -> list:
    root_str = config.get("documents", "root_dir", fallback="").strip()
    if not root_str:
        logger.error("Nincs megadva root_dir a [documents] szekcióban!")
        return []

    root = Path(root_str).expanduser().resolve()
    if not root.is_dir():
        logger.error("A gyökérkönyvtár nem létezik: %s", root)
        return []

    max_depth    = config.getint("documents", "max_depth", fallback=2)
    extensions   = _get_extensions(config)
    allowed_dirs = _get_allowed_dirs(config)
    chunk_size, overlap = _get_chunk_params(config)

    if not allowed_dirs:
        logger.warning("Nincs egyetlen leírással ellátott könyvtár sem az ini fájlban.")
        return []

    logger.info("Gyökér: %s | Mélység: %d | Chunk: %d/%d | Könyvtárak: %s",
                root, max_depth, chunk_size, overlap, list(allowed_dirs.keys()))

    documents = []
    _walk(root, root, 0, max_depth, extensions, allowed_dirs,
          chunk_size, overlap, documents)
    logger.info("Összesen betöltött chunk: %d", len(documents))
    return documents


def _walk(current, root, depth, max_depth, extensions, allowed_dirs,
          chunk_size, overlap, result):
    try:
        rel = str(current.relative_to(root))
    except ValueError:
        return
    if rel == ".":
        rel = ""

    if rel not in allowed_dirs:
        if depth < max_depth:
            for child in sorted(current.iterdir()):
                if child.is_dir():
                    _walk(child, root, depth + 1, max_depth,
                          extensions, allowed_dirs, chunk_size, overlap, result)
        return

    dir_description = allowed_dirs[rel]
    logger.debug("Feldolgozás: %s (%s)", current, dir_description)

    for file in sorted(current.iterdir()):
        if not file.is_file():
            continue
        if file.suffix.lower().lstrip(".") not in extensions:
            continue

        raw_text = extract_text(file)
        if not raw_text.strip():
            logger.debug("Üres/nem olvasható fájl kihagyva: %s", file)
            continue

        clean_text = clean_extracted_text(raw_text)
        chunks = _chunk_text(clean_text, chunk_size, overlap)

        for i, chunk in enumerate(chunks):
            result.append(_build_doc_entry(file, dir_description, chunk, i, len(chunks)))

        logger.info("Beolvasva: %s – %d chunk (%d karakter összesen)",
                    file.name, len(chunks), len(clean_text))

    if depth < max_depth:
        for child in sorted(current.iterdir()):
            if child.is_dir():
                _walk(child, root, depth + 1, max_depth,
                      extensions, allowed_dirs, chunk_size, overlap, result)


# ---------------------------------------------------------------------------
# File snapshot
# ---------------------------------------------------------------------------

def _build_snapshot(documents: list) -> dict:
    snapshot = {}
    for doc in documents:
        p = Path(doc["path"])
        try:
            snapshot[str(p)] = p.stat().st_mtime
        except FileNotFoundError:
            pass
    return snapshot


def _load_snapshot() -> dict:
    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_snapshot(snapshot: dict):
    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def clear_cache():
    try:
        data_dir = Path("data")
        if data_dir.exists():
            shutil.rmtree(data_dir)
            logger.info("Cache törölve.")
        return True
    except Exception as e:
        logger.error("Hiba cache törlése közben: %s", e)
        return False


def should_refresh_data() -> bool:
    if not DOCS_FILE.exists():
        logger.info("Nincs cache, feldolgozás szükséges.")
        return True

    if CONFIG_FILE.exists():
        try:
            if CONFIG_FILE.stat().st_mtime > DOCS_FILE.stat().st_mtime:
                logger.info("A konfiguráció módosult, újrafeldolgozás szükséges.")
                return True
        except Exception as e:
            logger.warning("mtime ellenőrzési hiba: %s", e)

    saved_snapshot = _load_snapshot()
    if not saved_snapshot:
        logger.info("Nincs fájl-snapshot, újrafeldolgozás szükséges.")
        return True

    for path_str, saved_mtime in saved_snapshot.items():
        p = Path(path_str)
        if not p.exists():
            logger.info("Fájl törlődött: %s", p)
            return True
        if p.stat().st_mtime != saved_mtime:
            logger.info("Fájl módosult: %s", p)
            return True

    return False


def save_docs(documents: list):
    DOCS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DOCS_FILE, "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)
    snapshot = _build_snapshot(documents)
    _save_snapshot(snapshot)
    logger.info("Cache mentve: %d chunk → %s", len(documents), DOCS_FILE)


def load_docs() -> list:
    try:
        with open(DOCS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Cache betöltve: %d chunk", len(data))
        return data
    except Exception as e:
        logger.error("Hiba cache betöltése közben: %s", e)
        raise


def fetch_documents(conf_file="doku_rag.ini") -> list:
    if not Path(conf_file).exists():
        logger.error("Konfigurációs fájl nem található: %s", conf_file)
        return []
    config = load_config(conf_file)
    documents = scan_documents(config)
    if documents:
        save_docs(documents)
    else:
        logger.warning("Nem sikerült egyetlen dokumentumot sem beolvasni.")
    return documents
