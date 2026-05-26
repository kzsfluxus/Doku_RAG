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
- 📄 Forrás dokumentumok letöltése közvetlenül a válasz alól
- 🔍 Full-text keresés a teljes dokumentumtárban

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

pip install -r requirements-cpu.txt      # CPU-only
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

## 🖥️ Webes felület

A webes felület két tabból áll.

### ❓ Kérdés-válasz tab (`/`)

A főoldalon természetes nyelven tehetsz fel kérdéseket a dokumentumtár tartalmával kapcsolatban. Az LLM a legrelevánabb chunk-ok alapján generálja a választ. A válasz alatt a rendszer megjeleníti azokat a forrásdokumentumokat, amelyekből a kontextus összeállt – minden forrás egy kattintható letöltési link.

```
┌──────────────────────────────────┐
│ Kérdés: [_____________________]  │
│ [Küldés]                         │
├──────────────────────────────────┤
│ Az LLM válasza itt jelenik meg.  │
│                                  │
│ 📄 Forrás dokumentumok           │
│  • szerződés_2024.pdf  ↓         │
│  • árajánlat_Q1.docx   ↓         │
└──────────────────────────────────┘
```

### 🔍 Keresés tab (`/search`)

A keresés tab egyszerű, teljes szöveges (full-text) keresést biztosít a dokumentumtárban. A keresés a memóriában lévő chunk-lista `text` mezőjében fut, case-insensitive egyeztetéssel. Az eredménylista találatonként tartalmazza:

- a fájl nevét letöltési linkként
- egy ~200 karakteres szövegkivonatot a találat közvetlen környezetéből

```
┌──────────────────────────────────┐
│ Keresés: [__________________]    │
│ [Keresés]                        │
├──────────────────────────────────┤
│ 3 találat a „nettó fizetendő"    │
│ kifejezésre:                     │
│                                  │
│ 📄 számla_2024_03.pdf  ↓         │
│  …összesen nettó fizetendő       │
│   összeg: 450 000 Ft…            │
│                                  │
│ 📄 árajánlat_Q1.xlsx   ↓         │
│  …a nettó fizetendő díj az       │
│   egyedi megállapodás alapján…   │
└──────────────────────────────────┘
```

### 📥 Dokumentum letöltés

Mindkét tabban a dokumentumok neve kattintható letöltési link. A `/download?path=<útvonal>` végpont ellenőrzi, hogy a kért fájl az `ini`-ben megadott `root_dir` könyvtáron belül van-e; azon kívüli elérési út `403 Forbidden` választ kap.

---

## HTTP végpontok

| Végpont | Metódus | Leírás |
|---------|---------|--------|
| `/` | GET, POST | Főoldal – kérdés-válasz felület |
| `/search` | GET, POST | Full-text keresés a dokumentumtárban |
| `/download` | GET | Dokumentum letöltése (`?path=<abszolút útvonal>`) |
| `/refresh` | POST | Dokumentumok újrafeldolgozása |
| `/api/ask` | POST (JSON) | REST API kérdéshez – válasz + forrás lista |
| `/api/search` | POST (JSON) | REST API full-text kereséshez |
| `/api/health` | GET | Egészségügyi ellenőrzés |
| `/api/status` | GET | Részletes rendszerállapot |
| `/api/reload-model` | POST | Modell konfiguráció újratöltése |

### `/api/ask` kérés/válasz

```json
// POST /api/ask
{ "question": "Mikor jár le a bérleti szerződés?" }

// Válasz
{
  "question": "Mikor jár le a bérleti szerződés?",
  "answer": "A bérleti szerződés 2025. december 31-én jár le.",
  "sources": [
    { "title": "Szerződések / berleti_szerzodes_2023.pdf", "path": "/home/user/ceg_iratai/szerződések/berleti_szerzodes_2023.pdf" }
  ],
  "status": "success"
}
```

### `/api/search` kérés/válasz

```json
// POST /api/search
{ "query": "nettó fizetendő", "max_results": 10 }

// Válasz
{
  "query": "nettó fizetendő",
  "results": [
    {
      "title": "Számlák / szamla_2024_03.pdf",
      "path": "/home/user/ceg_iratai/számlák/szamla_2024_03.pdf",
      "excerpt": "…összesen nettó fizetendő összeg: 450 000 Ft…"
    }
  ],
  "status": "success"
}
```

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
│   └── index.html          # Kérdés-válasz + full-text keresés felület
├── static/
├── development_plan/
│   └── fejlesztesi_terv.md
├── doku_rag.ini.example
├── requirements.txt
└── .gitignore
```
