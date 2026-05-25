#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 11 03:21:15 2025
@author: zsolt

A konfigurációs fájlból nyelvi modell nevét betöltő segédfüggvény.

Ez a modul lehetővé teszi, hogy a `models/models.ini` fájlban megadott modellnevet
olvassuk ki. Ha a konfigurációs fájl nem érhető el vagy érvénytelen értéket tartalmaz,
az alapértelmezett modellnév kerül visszaadásra. A naplózáshoz a `logging` modult használja.

A konfigurációs fájl elvárt formátuma:

    [models]
    language_model = mistral

Functions:
    get_model(path=MODEL_PATH, default_model='mistral'):
        Beolvassa a nyelvi modell nevét a konfigurációs fájlból.
"""

import configparser
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

MODEL_PATH=Path('models/models.ini')

def get_model(path=MODEL_PATH, default_model='mistral'):
    """
    Betölti a nyelvi modell nevét a konfigurációs fájlból.

    Args:
        path (str): A konfigurációs fájl elérési útja.
        default_model (str): Alapértelmezett modell, ha a fájl nem érhető el vagy hibás.

    Returns:
        str: A nyelvi modell neve a konfigurációból, vagy az alapértelmezett.
    """
    config = configparser.ConfigParser()
    
    try:
        config.read(path, encoding='utf-8')
        model_name = config.get('models', 'language_model', fallback='').strip()

        if model_name and len(model_name) <= 100:
            logger.info("Sikeresen betöltött modell: %s", model_name)
            return model_name
        else:
            logger.info("Érvénytelen vagy hiányzó modellnév, alapértelmezettet használunk: %s", default_model)
            return default_model

    except configparser.Error as error:
        logger.warning("Konfigurációs hiba (%s), alapértelmezett modell: %s", error, default_model)
        return default_model