#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prompt_builder.py – Prompt építő modul a Doku RAG rendszerhez.
@author: zsolt

Általános prompt epítés, dokumentumok alapján, általános dokumentum-alapú
kontextust épít, felhasználva a könyvtárleírásokat is.
"""


def build_prompt(contexts: list[dict], question: str) -> str:
    """
    Prompt összeállítása dokumentum-kontextusok és kérdés alapján.

    Args:
        contexts (list[dict]): Releváns dokumentumok listája.
            Minden elem 'title', 'text' (és opcionálisan 'dir_description',
            'path') kulcsokkal.
        question (str): A felhasználó kérdése.

    Returns:
        str: Az elkészített prompt.
    """
    if not contexts:
        return (
            f"Kérdés: {question}\n\n"
            "Válasz: Sajnos nincs releváns információ a dokumentumokban."
        )

    prompt = (
        "Az alábbi dokumentumrészletek alapján válaszolj a kérdésre "
        "**helyes és természetes magyar nyelven**.\n"
        "A válasz legyen részletes, tényszerű és jól megfogalmazott, "
        "ügyelve az alany–állítmány egyeztetésre, helyesírásra és "
        "nyelvtani pontosságra.\n"
        "Elsősorban a megadott dokumentumokat használd, de ha szükséges, "
        "egészítsd ki általános tudással is.\n\n"
        "## FORRÁSOK:\n\n"
    )

    for i, doc in enumerate(contexts, 1):
        title = doc.get("title", f"Dokumentum {i}")
        dir_desc = doc.get("dir_description", "")
        text = doc.get("text", "").strip()[:1500]

        header = f"=== {title} ==="
        if dir_desc:
            header += f"  [{dir_desc}]"
        prompt += f"{header}\n{text}\n\n"

    prompt += f"KÉRDÉS: {question}\n\n"
    prompt += (
        "RÉSZLETES VÁLASZ:\n"
        "(Adj átfogó, informatív választ a dokumentumok tartalma alapján, "
        "kiegészítve releváns háttér-információkkal.)\n\n"
        "Válasz:"
    )
    return prompt
