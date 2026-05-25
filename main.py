#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py – CLI interfész a Doku RAG rendszerhez.
@author: zsolt

Parancssori kérdés-válasz ciklus, adatfrissítés, státuszkijelzés.
"""

import os
os.environ["PYTHONWARNINGS"] = "ignore::DeprecationWarning"
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import logging
import sys
from rag_system import RAGSystem, RAGInitializationError, RAGQueryError

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def print_banner():
    print("=" * 60)
    print("🗂️  Doku RAG CLI – Dokumentum-alapú Kérdés-Válasz Rendszer")
    print("=" * 60)


def print_help():
    print("\n📋 Elérhető parancsok:")
    print("  - Írj be egy kérdést a válasz eléréséhez")
    print("  - 'help' vagy '?' – ez a súgó")
    print("  - 'status'        – rendszer státusz")
    print("  - 'refresh'       – dokumentumok újrafeldolgozása")
    print("  - 'quit' / 'exit' / üres sor – kilépés")
    print()


def print_status(rag_system: RAGSystem):
    try:
        info = rag_system.get_system_info()
        print("\n📊 Rendszer státusz:")
        print(f"  ✅ Inicializálva:      {'Igen' if info['initialized'] else 'Nem'}")
        print(f"  📚 Dokumentumok:       {info['documents_loaded']} db")
        print(f"  🔍 Embedder kész:      {'Igen' if info['embedder_ready'] else 'Nem'}")
        print(f"  💾 Index létezik:      {'Igen' if info['index_exists'] else 'Nem'}")
        print(f"  📄 Cache fájl létezik: {'Igen' if info['docs_file_exists'] else 'Nem'}")
        if info.get("document_titles"):
            titles = info["document_titles"][:5]
            print(f"  📋 Dokumentumok: {', '.join(titles)}")
            if len(info["document_titles"]) > 5:
                print(f"       ... és még {len(info['document_titles']) - 5} dokumentum")
        print()
    except Exception as e:
        print(f"❌ Státusz lekérdezési hiba: {e}")


def handle_refresh(rag_system: RAGSystem) -> bool:
    try:
        print("🔄 Dokumentumok újrafeldolgozása...")
        if rag_system.refresh_data():
            print("✅ Adatok sikeresen frissítve!")
            return True
        print("❌ Adatok frissítése sikertelen!")
        return False
    except Exception as e:
        print(f"❌ Frissítési hiba: {e}")
        return False


def interactive_mode(rag_system: RAGSystem):
    print("🎯 RAG rendszer kész! Tedd fel a kérdéseidet.")
    print("Írd be 'help'-et a parancsok listájáért.")
    question_count = 0

    while True:
        try:
            prompt = f"\n📌 Kérdés #{question_count + 1} (üres = kilépés): "
            user_input = input(prompt).strip()

            if not user_input or user_input.lower() in ["quit", "exit", "bye"]:
                print("\n👋 Kilépés...")
                break

            if user_input.lower() in ["help", "?", "h"]:
                print_help()
                continue
            elif user_input.lower() in ["status", "stat", "s"]:
                print_status(rag_system)
                continue
            elif user_input.lower() in ["refresh", "reload", "r"]:
                handle_refresh(rag_system)
                continue
            elif user_input.lower() in ["clear", "cls"]:
                os.system("clear" if os.name == "posix" else "cls")
                print_banner()
                continue

            try:
                print("🔍 Keresés és válasz generálása...")
                answer = rag_system.process_question(user_input)
                print(f"\n💬 Válasz:\n{answer}\n")
                print("-" * 60)
                question_count += 1
            except RAGQueryError as e:
                print(f"❌ RAG hiba: {e}")
            except Exception as e:
                print(f"❌ Kérdés feldolgozási hiba: {e}")

        except KeyboardInterrupt:
            print("\n\n👋 Kilépés (Ctrl+C)...")
            break
        except EOFError:
            print("\n\n👋 Kilépés (EOF)...")
            break
        except Exception as e:
            print(f"❌ Váratlan hiba: {e}")


def main():
    try:
        print_banner()
        print("🚀 RAG rendszer inicializálása...")
        with RAGSystem() as rag_system:
            if not rag_system.is_initialized:
                print("❌ RAG rendszer inicializálása sikertelen!")
                return 1
            print_status(rag_system)
            interactive_mode(rag_system)
        print("✅ Program befejezve.")
        return 0
    except RAGInitializationError as e:
        print(f"❌ Inicializálási hiba: {e}")
        print("💡 Ellenőrizd a doku_rag.ini konfigurációt és próbáld újra!")
        return 1
    except KeyboardInterrupt:
        print("\n\n👋 Program megszakítva (Ctrl+C)")
        return 0
    except Exception as e:
        print(f"❌ Kritikus hiba: {e}")
        logger.exception("Részletes hiba információ:")
        return 1


if __name__ == "__main__":
    sys.exit(main())
