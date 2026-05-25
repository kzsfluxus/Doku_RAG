#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun  5 15:33:22 2025
@author: zsolt

Ez a modul az Ollama parancssori eszköz automatizált futtatására és 
kezelésére szolgál.
Lehetővé teszi különböző Ollama modellek indítását és leállítását Python kódból, 
programozott módon.
A modul főként alacsony szintű futtatási hibák és folyamat-kimenetek kezelésében 
segít, naplózással támogatva.

Fő funkciók:
    - run_ollama_model: Egy tetszőleges szöveges promptot futtat le a megadott Ollama modellen.
    - stop_ollama_model: Egy futó Ollama modell folyamatát állítja le.
"""
import subprocess
import logging

logger = logging.getLogger(__name__)

def run_ollama_model(prompt, model_name):
    """
    Futtat egy szöveges promptot a megadott Ollama modellen.

    Args:
        prompt (str): A bemeneti szöveg, amit a modellnek elküldünk.
        model_name (str, optional): A futtatandó Ollama modell neve.

    Returns:
        str: A modell futtatásának eredménye (standard output),
            vagy hibaüzenet, ha a folyamat sikertelen volt vagy timeout történt.

    Raises:
        subprocess.TimeoutExpired: Ha a modell futtatása 10 percen túl elhúzódik.
    """
    try:
        logger.debug("Ollama modell indítása: %s", model_name)
        result = subprocess.run(
            ['ollama', 'run', model_name],
            input=prompt.encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=600  # 10 perc az első betöltéshez
        )
        if result.returncode == 0:
            logger.info("✅ Ollama modell sikeresen betöltődött: %s", model_name)
            return result.stdout.decode()

        logger.error("Ollama hiba: %s", result.stderr.decode())
        return "Hiba történt a modell futtatásakor."
    except subprocess.TimeoutExpired:
        logger.warning(
            "Timeout - a modell túl sokáig nem válaszolt (%s)",
            model_name)
        return "A modell túl sokáig nem válaszolt, próbáld újra."
    except Exception as error:
        logger.error("Subprocess hiba: %s", error)
        return "Hiba történt a modell hívásakor."

def stop_ollama_model(model_name):
    """
    Leállít egy futó Ollama modellt.

    Args:
        model_name (str, optional): A leállítandó Ollama modell neve.

    Returns:
        str: A leállítás eredménye (standard output),
            vagy hibaüzenet, ha a folyamat sikertelen volt.

    """
    try:
        result = subprocess.run(
            ['ollama', 'stop', model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            logger.info(
                "✅ A %s modell sikeresen leállítva",
                model_name)
            return result.stdout.decode()

        logger.error("Ollama hiba: %s", result.stderr.decode())
        return "Hiba történt a modell leállításakor."
    except Exception as error:
        logger.error("Subprocess hiba: %s", error)
        return "Hiba történt a modell leállításakor."
