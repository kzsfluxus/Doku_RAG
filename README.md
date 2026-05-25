# KZSfluxus – Doku_RAG 🗂️🔍

Retrieval-Augmented Generation rendszer helyi dokumentumok feldolgozásához, lokális LLM (Ollama), FAISS vektorindexelés és Flask-alapú keresőfelület.

A Doku RAG egy intelligens, helyi dokumentumtárat kereshető tudásbázissá alakító rendszer. A könyvtárstruktúra és a fájlok leírása az ini konfigurációban adható meg; a rendszer csak az ott felsorolt, leírással ellátott könyvtárakat dolgozza fel. A kinyert szövegek chunk-okra bontva kerülnek vektoros indexbe, így nagy fájloknál is pontos a keresés. A kérdésekre helyi Ollama LLM válaszol a releváns részletek alapján.

Tipikus felhasználási területek: vállalati iratkezelés, HR-dokumentáció, számlák és szerződések keresése, belső tudásbázis, több részleg önálló vagy közös dokumentumtára.

## ✨ Főbb jellemzők

- 📁 Helyi fájlrendszer hierarchikus bejárása, konfigurálható mélységgel
- 🔒 Fehérlista-alapú könyvtárkezelés: csak az ini-ban leírt mappák kerülnek feldolgozásra
- ✂️ Automatikus chunk-olás átfedéssel (bekezdéshatár-preferált)
- 🔄 Intelligens cache-frissítés: config mtime + fájl-snapshot összehasonlítás
- 🧠 Embedding: `sentence-transformers/LaBSE` (többnyelvű, 768 dim)
- ⚡ FAISS-alapú vektoros keresés
- 🤖 Lokális LLM Ollama-n keresztül (alapértelmezett: mistral)
- 🌐 Flask webes keresőfelület + REST API
- 💻 CLI interaktív mód

## 📄 Támogatott dokumentumtípusok

| Típus | Könyvtár |
|-------|----------|
| TXT, MD, HTML | beépített |
| PDF | pypdf |
| DOCX | python-docx |
| XLSX, XLSM | openpyxl |
| XLS (legacy) | xlrd |
| PPTX | python-pptx |
| ODT | odfpy |
| ODS | pandas + odf |
| RTF | striprtf |
| CSV | pandas |
| JSON | beépített |

---

## 🧰 Követelmények

- Python 3.10+
- [Ollama](https://ollama.com/) – telepített és futó modell (pl. `mistral`)
- `venv` vagy `virtualenv`

### Hardverkövetelmények

| Konfiguráció | CPU | RAM | Tárhely |
|---|---|---|---|
| CPU-only (min.) | 8 mag (i7 / Ryzen 7) | 16 GB | 50 GB SSD |
| GPU (min.) | 4 mag | 16 GB | 50 GB SSD + NVIDIA 8 GB VRAM |
| GPU (optimális) | 8+ mag | 32 GB | 100 GB SSD + NVIDIA 24 GB VRAM |

---

## Telepítés

```bash
git clone https://github.com/kzsfluxus/Doku_RAG
cd Doku_RAG
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt          # CPU-only
# vagy
pip install -r requirements-gpu.txt      # NVIDIA GPU + CUDA
```

---

## Konfiguráció

Másold az example fájlt és szerkeszd:

```bash
cp doku_rag.ini.example doku_rag.ini
```

### `doku_rag.ini` felépítése

```ini
[documents]
root_dir     = /home/user/ceg_iratai   # Gyökérkönyvtár (kötelező)
max_depth    = 2                        # Könyvtármélység (0 = csak gyökér)
chunk_size   = 1000                     # Chunk mérete karakterben
chunk_overlap = 150                     # Átfedés chunk-ok között
extensions   = txt, md, pdf, docx, xlsx, pptx

[models]
language_model = mistral

# Csak leírással ellátott könyvtárak kerülnek feldolgozásra.
# Gyökér: [dir], alkönyvtárak: [dir.<név>] vagy [dir.<szülő>/<gyerek>]

[dir]
description = XY Kft összes irata

[dir.számlák]
description = kiállított és beérkezett számlák

[dir.életrajzok]
description = jelentkezők önéletrajzai

[dir.szerződések]
description = ügyféllel kötött szerződések

[dir.szerződések/aktív]
description = jelenleg érvényes szerződések
```

> **Fontos:** A `doku_rag.ini` érzékeny fájlútvonalakat tartalmazhat, ezért a `.gitignore` kizárja a verziókezelőből. Csak az `doku_rag.ini.example` kerül a repóba.

### Nyelvi modell beállítása

```bash
ollama pull llama3.2:latest
```

`models/models.ini`:
```ini
[models]
language_model = llama3.2:latest
```

---

## Használat

**CLI:**
```bash
./cli_start
```

**Web:**
```bash
./web_start
```
Elérhető: [http://localhost:5000](http://localhost:5000)

---

## HTTP végpontok

| Végpont | Metódus | Leírás |
|---------|---------|--------|
| `/` | GET, POST | Főoldal – kérdés-válasz felület |
| `/refresh` | POST | Dokumentumok újrafeldolgozása |
| `/api/ask` | POST (JSON) | REST API kérdéshez |
| `/api/health` | GET | Egészségügyi ellenőrzés |
| `/api/status` | GET | Részletes rendszerállapot |
| `/api/reload-model` | POST | Modell konfiguráció újratöltése |

---

## Projekt struktúra

```
Doku_RAG/
├── app.py                  # Flask webalkalmazás
├── main.py                 # CLI belépési pont
├── rag_system.py           # Központi RAGSystem osztály
├── doc_loader.py           # Könyvtárbejárás, chunk-olás, cache
├── extractors.py           # Fájltípusonkénti szövegkinyerők
├── embedder.py             # FAISS + sentence-transformers
├── prompt_builder.py       # Prompt összeállítás
├── text_cleaner.py         # Szövegtisztítás (betöltés + LLM válasz)
├── ollama_runner.py        # Ollama subprocess kezelés
├── model_loader.py         # Modellnév beolvasása konfigból
├── models/
│   └── models.ini          # Aktív LLM neve
├── templates/
│   └── index.html
├── static/
├── development_plan/
│   └── fejlesztesi_terv.md
├── doku_rag.ini.example
├── requirements.txt
└── .gitignore
```
