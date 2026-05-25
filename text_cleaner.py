#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
text_cleaner.py – Szövegtisztító modul a Doku RAG rendszerhez.
@author: zsolt

Két külön függvényt biztosít:
  - clean_extracted_text(): dokumentumbeolvasás utáni normalizálás
  - clean_llm_response():   LLM válasz tisztítása megjelenítés előtt
"""

import re


def clean_extracted_text(text: str) -> str:
    """
    Nyers dokumentumszöveg normalizálása indexelés előtt.

    Elvégzi:
    - Vezérlőkarakterek eltávolítása (sortörés és tab megtartásával)
    - Sorvégi szóközök törlése
    - Ismétlődő szóközök normalizálása
    - Háromnál több egymást követő üres sor összevonása kettőre

    Args:
        text (str): Nyers, kinyert dokumentumszöveg.

    Returns:
        str: Megtisztított szöveg.
    """
    if not text:
        return text

    # Vezérlőkarakterek (form feed, null byte stb.) eltávolítása
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)

    # Sorvégi szóközök
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)

    # Többszörös szóközök soron belül
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Háromnál több egymást követő üres sor → dupla sortörés
    text = re.sub(r"\n{3,}", "\n\n", text)

    # HTML tagek (pl. ha HTML fájlt olvasunk be nyers szövegként)
    text = re.sub(r"<[^>]{1,200}>", "", text)

    return text.strip()


def clean_llm_response(text: str) -> str:
    """
    LLM által generált válasz tisztítása megjelenítés előtt.

    Elvégzi:
    - Wiki markup maradványok eltávolítása (ha a modell ilyet produkál)
    - Sorvégi szóközök és többszörös üres sorok normalizálása
    - Vezérlőkarakterek törlése

    Args:
        text (str): Az LLM nyers kimenete.

    Returns:
        str: Megtisztított válasz szöveg.
    """
    if not text:
        return text

    # Wiki markup maradványok
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\{\{[^}]+\}\}", "", text)

    # HTML tagek
    text = re.sub(r"<[^>]{1,200}>", "", text)

    # Vezérlőkarakterek
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)

    # Sorvégi szóközök
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)

    # Többszörös szóközök
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Többszörös üres sorok
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# Visszafelé-kompatibilis alias
clean_wiki_text = clean_llm_response
