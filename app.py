#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py – Flask webalkalmazás a Doku RAG rendszerhez.
@author: zsolt
"""

import os
os.environ["PYTHONWARNINGS"] = "ignore::DeprecationWarning"
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
from pathlib import Path
import logging
import mimetypes
from flask import Flask, request, render_template, jsonify, send_file, abort
from rag_system import RAGSystem, RAGInitializationError, RAGQueryError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
rag_system = RAGSystem()


def initialize_app():
    try:
        logger.info("Flask alkalmazás inicializálása...")
        if not rag_system.initialize():
            raise RAGInitializationError("System initialization failed")
    except Exception as e:
        logger.error("Alkalmazás inicializálási hiba: %s", e)
        raise


@app.route("/", methods=["GET", "POST"])
def index():
    try:
        if not rag_system.is_initialized:
            initialize_app()

        question = ""
        clean_answer = ""
        error = False

        sources = []

        if request.method == "POST":
            question = request.form.get("question", "").strip()
            if question:
                try:
                    clean_answer, sources = rag_system.process_question(question)
                except RAGQueryError as e:
                    clean_answer = f"❌ Hiba történt: {e}"
                    error = True
                except Exception as e:
                    clean_answer = f"❌ Váratlan hiba: {e}"
                    error = True
            else:
                clean_answer = "Kérlek, adj meg egy kérdést!"

        return render_template("index.html",
                               question=question,
                               clean_answer=clean_answer,
                               sources=sources,
                               error=error)
    except Exception as e:
        logger.error("Route hiba: %s", e)
        return render_template("index.html",
                               question="",
                               clean_answer=f"❌ Rendszerhiba: {e}",
                               sources=[],
                               error=True)


@app.route("/refresh", methods=["POST"])
def refresh_data():
    try:
        if rag_system.refresh_data():
            return jsonify({"status": "success", "message": "Dokumentumok sikeresen újrafeldolgozva!"})
        return jsonify({"status": "error", "message": "Újrafeldolgozás sikertelen!"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/reload-model", methods=["POST"])
def reload_model():
    try:
        old = rag_system.model_name
        new = rag_system.reload_model_from_config()
        return jsonify({"status": "success", "old_model": old, "new_model": new})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/ask", methods=["POST"])
def api_ask():
    try:
        if not rag_system.is_initialized:
            initialize_app()
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        data = request.get_json()
        question = data.get("question", "").strip()
        if not question:
            return jsonify({"error": "Nincs kérdés megadva"}), 400
        answer, sources = rag_system.process_question(question)
        return jsonify({
            "question": question,
            "answer":   answer,
            "sources":  sources,
            "status":   "success",
        })
    except RAGQueryError as e:
        return jsonify({"error": str(e), "status": "rag_error"}), 500
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500


@app.route("/search", methods=["GET", "POST"])
def search():
    """Full-text keresés oldal."""
    try:
        if not rag_system.is_initialized:
            initialize_app()

        query = ""
        results = []
        error = False

        if request.method == "POST":
            query = request.form.get("query", "").strip()
            if query:
                try:
                    results = rag_system.full_text_search(query)
                except RAGQueryError as e:
                    error = True
                    results = []
            # üres query esetén results = []

        return render_template("index.html",
                               search_query=query,
                               search_results=results,
                               search_error=error)
    except Exception as e:
        logger.error("Search route hiba: %s", e)
        return render_template("index.html",
                               search_query="",
                               search_results=[],
                               search_error=True)


@app.route("/api/search", methods=["POST"])
def api_search():
    """Full-text keresés JSON API."""
    try:
        if not rag_system.is_initialized:
            initialize_app()
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        data = request.get_json()
        query = data.get("query", "").strip()
        if not query:
            return jsonify({"error": "Nincs keresési kifejezés megadva"}), 400
        max_results = int(data.get("max_results", 10))
        results = rag_system.full_text_search(query, max_results=max_results)
        return jsonify({"query": query, "results": results, "status": "success"})
    except RAGQueryError as e:
        return jsonify({"error": str(e), "status": "rag_error"}), 500
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500


@app.route("/download")
def download_file():
    """Dokumentum letöltése az abszolút elérési útvonal alapján.

    Biztonsági ellenőrzés: csak a konfigurált root_dir alatti fájl tölthető le.
    """
    try:
        from doc_loader import load_config, CONFIG_FILE
        from pathlib import Path

        file_path = request.args.get("path", "").strip()
        if not file_path:
            abort(400)

        requested = Path(file_path).resolve()

        # Biztonsági korlátozás: a fájlnak a konfigurált root_dir alatt kell lennie
        config = load_config(CONFIG_FILE)
        root_str = config.get("documents", "root_dir", fallback="").strip()
        if not root_str:
            abort(403)
        root = Path(root_str).expanduser().resolve()

        try:
            requested.relative_to(root)
        except ValueError:
            logger.warning("Letöltési kísérlet root_dir-en kívüli fájlra: %s", requested)
            abort(403)

        if not requested.is_file():
            abort(404)

        mime, _ = mimetypes.guess_type(str(requested))
        return send_file(
            str(requested),
            as_attachment=True,
            download_name=requested.name,
            mimetype=mime or "application/octet-stream",
        )
    except Exception as e:
        logger.error("Letöltési hiba: %s", e)
        abort(500)
def health_check():
    try:
        if not rag_system.is_initialized:
            initialize_app()
        info = rag_system.get_system_info()
        return jsonify({
            "status": "healthy" if info["initialized"] else "initializing",
            "system_info": info,
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route("/api/status")
def system_status():
    try:
        if not rag_system.is_initialized:
            initialize_app()
        info = rag_system.get_system_info()
        return jsonify({
            "initialized": info["initialized"],
            "documents_count": info["documents_loaded"],
            "embedder_ready": info["embedder_ready"],
            "index_exists": info["index_exists"],
            "docs_file_exists": info["docs_file_exists"],
            "document_titles": info.get("document_titles", [])[:10],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    logger.info("Flask szerver indítása: %s:%d (debug=%s)", host, port, debug)
    app.run(debug=debug, host=host, port=port)
