# Doku RAG – Fejlesztési terv

**Verzió:** 2.0  
**Állapot:** tervezet  
**Cél:** a jelenlegi prototípus fokozatos fejlesztése professzionális, céges környezetben is bevethető rendszerré

---

## Összefoglalás

A jelenlegi Doku RAG (v1.1) egy működőképes, egyszemélyes vagy kis csapatban használható dokumentum-kereső rendszer, amely az eredeti kérdés-válasz funkció mellett most már forrás dokumentumok letöltését és full-text keresést is biztosít. Az alábbiakban öt fejlesztési fázis kerül leírásra, amelyek végén a rendszer képes lesz:

- forrás dokumentumokat és full-text találatokat biztonságosan kiszolgálni többfelhasználós környezetben,
- több részleg párhuzamos, izolált dokumentumtárát kezelni,
- jogosultságszinteket érvényesíteni a letöltési és keresési funkciókon is,
- Samba-megosztásokon tárolt dokumentumokat feldolgozni és letöltésre visszaszolgáltatni,
- PostgreSQL-alapú, tartós metaadat-tárolást és teljes szöveges keresést biztosítani,
- webes felületen hitelesítést és audit-naplózást nyújtani minden funkcióhoz,
- és skálázhatóan, konténerizáltan futni.

---

## Jelenlegi állapot (v1.1)

### Kérdés-válasz funkció

A főoldalon natural language kérdést lehet feltenni. Az LLM a FAISS-indexből visszakeresett legrelevánabb chunk-ok alapján generálja a választ. A válasz alatt megjelennek a forrás dokumentumok letöltési linkként.

**Ismert korlátok többfelhasználós környezetben:**

- A `/download` végpont csak `root_dir`-ellenőrzést végez, nincs felhasználóhoz kötött jogosultság: bárki letöltheti a konfigurált könyvtárban lévő bármely dokumentumot, aki eléri az alkalmazást.
- A letöltési URL-ben az abszolút fájlútvonal szerepel query paraméterként (`?path=/home/...`), ami belső szerverstruktúrát szivárogtat ki.
- Egyszerre sok kérdés esetén az Ollama hívások sorban állnak, párhuzamos kiszolgálás nincs.
- Forrás deduplikáció fájlszinten történik: ha egy fájl több chunk-ból kerül be a kontextusba, csak egyszer jelenik meg a forráslistában – ez helyes viselkedés, de a chunk-ok száma és relevanciaszkórja nem látható.

### Full-text keresés funkció

A `/search` oldalon egyszerű, case-insensitive keresés fut a memóriában lévő chunk-lista `text` mezőjein.

**Ismert korlátok többfelhasználós környezetben:**

- A keresés az összes betöltött dokumentumon fut, részlegalapú szűrés és jogosultság-ellenőrzés nélkül.
- Nincs találat-kiemelés (highlight): a keresett kifejezés nem kerül kiemelve megjelenítésre a kivonatban.
- A `max_results` paramétert az API fogadja, de a webes felületen nem állítható.
- Nagy dokumentumtárnál (több ezer chunk) a lineáris Python `in` keresés lassú lehet; nincs cache, minden kérésnél újra fut.
- A keresés csak egész szóra és karaktersorozatra keres; nincs morfémakövetés, szótőazonosítás vagy szinonimakezelés.
- Egy dokumentum több chunkon is átnyúlhat: ha a keresett kifejezés egy chunk határán van szétválasztva, nem lesz találat.

---

## 1. fázis – Stabilitás és tesztelhetőség

*Becsült időigény: 2–3 hét*

Ez a fázis nem ad új funkciókat, de nélküle a későbbi fejlesztés kockázatos. A meglévő kódbázis tesztelhetőségét és megbízhatóságát növeli.

### 1.1 Egységtesztek

A meglévő kódbázishoz tesztek készítése:

- `test_extractors.py` – minden fájltípushoz legalább egy pozitív és egy hibás eset
- `test_doc_loader.py` – könyvtárbejárás, chunk-olás, snapshot-logika
- `test_text_cleaner.py` – `clean_extracted_text` és `clean_llm_response` külön tesztelve
- `test_embedder.py` – index építés, mentés, betöltés, lekérdezés
- `test_rag_system.py` – inicializálás, `process_question` (tuple visszatérés ellenőrzése), `full_text_search`, hibakezelés
- `test_app.py` – Flask route-ok: `/`, `/search`, `/download` (path traversal kísérletek, hiányzó fájl, root_dir-on kívüli útvonal)

Ajánlott keretrendszer: `pytest` + `unittest.mock` (Ollama és LLM hívások mockolásához).

**Különös figyelmet igénylő tesztesetek a két új funkcióhoz:**

- `process_question` üres `results` esetén üres `sources` listát ad vissza, nem kivételt
- `full_text_search` üres lekérdezésre üres listát ad vissza
- `full_text_search` chunk-határon szétválasztott kifejezés esetén nem talál – ezt dokumentálni kell, nem javítani ebben a fázisban
- `/download` path traversal: `?path=/etc/passwd` → 403
- `/download` szimbolikus link root_dir-en kívülre → 403 (a `resolve()` feloldja, de tesztelni kell)

### 1.2 Konfiguráció-validáció

Jelenleg a `doc_loader.py` némán sikertelen, ha a konfig hiányos vagy hibás. Érdemes egy `validate_config()` függvényt bevezetni, amely induláskor ellenőrzi:

- `root_dir` létezik és olvasható
- `max_depth` pozitív egész
- `chunk_size > chunk_overlap`
- legalább egy `[dir*]` szekció van leírással
- az `extensions` csak ismert értékeket tartalmaz

### 1.3 Logging egységesítése

A jelenlegi logolás vegyes részletességű. Egységes szintek bevezetése:

- `DEBUG` – chunk-szintű részletek, embedding-méretek
- `INFO` – fájl beolvasva, cache frissítve, kérdés feldolgozva, keresés futott
- `WARNING` – nem olvasható fájl, hiányzó könyvtár, sikertelen letöltési kísérlet
- `ERROR` – inicializálási hiba, LLM nem válaszol

A logfájl elérési útja legyen konfigurálható az ini-ban. A `/download` végpont minden kérésnél naplózza a kért útvonalat és a kiszolgáló felhasználó azonosítóját (ha van).

---

## 2. fázis – Letöltés és keresés biztonságossá tétele

*Becsült időigény: 2–4 hét*  
*Előfeltétel: 1. fázis*

Ez a fázis a két új funkció – forrás letöltés és full-text keresés – termelési szintű megbízhatóságát és biztonságát teremti meg, még a jogosultságrendszer bevezetése előtt.

### 2.1 Letöltési végpont megerősítése

**Útvonal-elrejtés:** az abszolút fájlútvonal query paraméterként való átadása belső szerverstruktúrát szivárogtat ki. Helyette a dokumentumokhoz egyedi, átlátszatlan azonosítót kell rendelni.

```python
# doc_loader.py – _build_doc_entry kiegészítése
import hashlib

def _build_doc_entry(file, dir_description, chunk_text, chunk_index, total_chunks):
    doc_id = hashlib.sha256(str(file).encode()).hexdigest()[:16]
    ...
    return {
        "id":    doc_id,
        "title": ...,
        "path":  str(file),
        ...
    }
```

A letöltési link ezután `/download?id=a3f8c2d1...` alakú, az `id` → `path` leképezés a szerver oldalán történik (memóriában vagy adatbázisban). A felhasználó soha nem látja a tényleges fájlútvonalat.

**Rate limiting:** a `/download` és `/search` végpontokon kérés-korlát bevezetése, hogy tömeges letöltés vagy keresési lavina ne terhelje le a szervert.

```python
# Flask-Limiter csomag
from flask_limiter import Limiter
limiter = Limiter(app, default_limits=["200 per day", "50 per hour"])

@app.route("/download")
@limiter.limit("30 per minute")
def download_file():
    ...
```

**MIME-típus és Content-Disposition:** a `send_file` hívás jelenleg is beállítja ezeket, de ellenőrizni kell, hogy az `as_attachment=True` minden böngészőben letöltést vált ki, nem megnyitást. PDF esetén megfontolandó a `inline` Content-Disposition, hogy a böngészőben megnyíljon, ne letöltődjön.

**Fájlméret-korlát:** nagy fájloknál (pl. 500 MB-os PPTX) a `send_file` blokkolhatja a Flask munkaszálat. Ha a dokumentumok nagy méretűek lehetnek, X-Accel-Redirect (Nginx) vagy streaming response alkalmazása javasolt.

### 2.2 Full-text keresés teljesítménye

**In-memory keresés gyorsítása:** a jelenlegi lineáris scan minden kérésnél újra végigmegy az összes chunkon. Két javítási lehetőség, amelyek kizárják egymást:

*A) Invertált index (Python, adatbázis nélkül):* betöltéskor felépül egy `{szó: [doc_index, ...]}` szótár. A keresés a szótárban közvetlen lookup, nem lineáris scan. Memóriaigénye mérsékelt, elkészítési ideje egyszer kell ráfordítani.

```python
from collections import defaultdict
import re

class InvertedIndex:
    def __init__(self):
        self._index = defaultdict(set)

    def build(self, docs):
        for i, doc in enumerate(docs):
            for word in re.findall(r'\w+', doc['text'].lower()):
                self._index[word].add(i)

    def search(self, query):
        words = re.findall(r'\w+', query.lower())
        if not words:
            return set()
        result = self._index.get(words[0], set()).copy()
        for word in words[1:]:
            result &= self._index.get(word, set())
        return result
```

*B) SQLite FTS5 (könnyűsúlyú, adatbázis alapú):* a `documents.json` mellé egy `fts.db` SQLite adatbázis, amelybe az összes chunk szövege bekerül. Az FTS5 modul tokenizálást, morfémakövetést és relevancia-pontozást ad ingyen.

```sql
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    doc_id UNINDEXED, text, title UNINDEXED,
    tokenize='unicode61 remove_diacritics 1'
);
```

A 3. fázisban ez PostgreSQL `tsvector`-ra cserélhető; addig az SQLite változat már most használható teljesítménynövekményként.

**Találat-kiemelés (highlight):** a kivonatban a keresett kifejezés legyen vizuálisan jelölve. A backend a `<mark>` HTML-taget szúrja be Jinja escape után:

```python
import html, re

def highlight(text: str, query: str) -> str:
    escaped = html.escape(text)
    pattern = re.compile(re.escape(html.escape(query)), re.IGNORECASE)
    return pattern.sub(lambda m: f"<mark>{m.group()}</mark>", escaped)
```

A template-ben `{{ result.excerpt|safe }}` – az escape a backenden történt, nem kell dupla escape.

**Chunk-határ probléma:** ha a keresett kifejezés két chunk határán van szétválasztva, a jelenlegi implementáció nem talál. Megoldási lehetőségek:

- Az overlap növelése (jelenleg 150 karakter) mérsékeli a problémát, de nem szünteti meg.
- Invertált index esetén a keresés az eredeti (nem darabolás előtti) szövegen is futhat, ha az megőrződik.
- SQLite/PostgreSQL FTS esetén a tokenizáló nem ismeri a chunk-határokat: az egész szöveget egységként kezeli, ezért ez a probléma ott nem lép fel.

**`max_results` a webes felületen:** a keresési formon egy `<select>` vagy `<input type="number">` elem, alapértelmezett értéke 10, maximum 50.

### 2.3 Keresési eredmény típusai

A jelenlegi keresés csak szöveg alapján dolgozik. Többfelhasználós környezetben hasznos lehet szűrők bevezetése:

- **Fájltípus szerinti szűrés:** `?type=pdf` – csak PDF-ek jelennek meg
- **Könyvtár/részleg szerinti szűrés:** `?dir=számlák` – csak az adott `dir_description` szekció alatti fájlok
- **Dátum szerinti szűrés:** `?modified_after=2024-01-01` – a fájl `mtime` alapján

Ezek a szűrők a `full_text_search()` metódus paramétereibe kerülnek; a 3. fázisban az SQL WHERE-feltételek közé mennek át.

---

## 3. fázis – Többfelhasználós és többrészleges támogatás

*Becsült időigény: 3–5 hét*  
*Előfeltétel: 2. fázis*

### 3.1 Több ini fájl – részlegenkénti izoláció

Jelenleg a rendszer egyetlen `doku_rag.ini` fájlt olvas. A cél: minden részleg saját konfigurációval és saját index-könyvtárral rendelkezzen.

**Javasolt könyvtárstruktúra:**

```
/etc/doku_rag/
├── global.ini          # közös LLM, embedding modell, DB
├── hr/
│   └── doku_rag.ini    # HR részleg konfigja
├── penzugy/
│   └── doku_rag.ini
└── jogi/
    └── doku_rag.ini
```

A `RAGSystem` konstruktora kapjon egy opcionális `config_path` paramétert. A webalkalmazás URL-alapon vagy bejelentkezési szerepkör alapján válasszon konfigurációt.

**Index-izoláció:** minden részlegnek külön `data/` alkönyvtár:

```
data/
├── hr/
│   ├── documents.json
│   ├── index.faiss
│   └── file_snapshot.json
├── penzugy/
│   └── ...
```

**A letöltési és keresési funkció szempontjából:** a részlegalapú izoláció azt jelenti, hogy a `/search` végpont alapértelmezetten csak az aktuális részleg dokumentumain keres. Adminisztrátori felhasználó opcionálisan kereshet több részlegben egyszerre (`cross_dept=true` paraméterrel), de ez explicit engedéllyel jár.

### 3.2 Samba-megosztások támogatása

Ha a dokumentumok hálózati Samba-megosztáson vannak (pl. `\\szerver\HR`), a rendszernek ezt transzparensen kell kezelnie.

**Megközelítési lehetőségek:**

1. **Mount-alapú (ajánlott):** a Samba-megosztás Linux oldalon fel van csatolva (pl. `/mnt/samba/hr`), és az ini fájlban ez szerepel `root_dir`-ként. A Doku RAG szempontjából ez nem különbözik egy helyi könyvtártól.

2. **SMB-kliens könyvtár:** `smbprotocol` Python csomag segítségével közvetlen SMB-elérés. Ez csak akkor indokolt, ha a csatolás nem megoldható (pl. konténeres környezetben).

**Letöltési funkció Samba esetén:** a `send_file` hívás a mount-olt elérési úton keresztül működik, tehát transzparens. Ha közvetlen SMB-elérést használunk, a fájlt le kell másolni egy átmeneti könyvtárba, onnan kiszolgálni, majd törölni. A közbenső másolat kezelésekor figyelni kell a párhuzamos letöltésekre (uuid-alapú temp fájlnév javasolt).

Az ini-ban jelezni kell, ha a forrás hálózati meghajtó:

```ini
[documents]
root_dir   = /mnt/samba/hr_iratok
mount_type = smb
smb_server = \\192.168.1.10\HR
smb_user   = domain\felhasznalo
smb_pass   = ${SMB_PASSWORD}
```

A jelszót sosem szabad az ini fájlban tárolni éles környezetben – environment variable vagy titkosított vault (pl. HashiCorp Vault, systemd credentials) javasolt.

### 3.3 Párhuzamos részlegek egyidejű kezelése

A Flask alkalmazásban több `RAGSystem` példány futhat egyszerre, ha minden részlegnek saját példánya van. Ez memóriaigényes lehet; alternatíva a lazy loading: csak az éppen szükséges részleg töltődik be, és egy egyszerű LRU cache tartja életben a legutóbb használtakat.

**A keresési funkció szempontjából:** ha több részleg van betöltve, a `/search` oldal opcionálisan mutasson részleg-szűrőt (select vagy checkbox). Az eredménylistában jelenjen meg a forrás részleg neve is, ne csak a fájlnév.

---

## 4. fázis – PostgreSQL integráció

*Becsült időigény: 4–6 hét*  
*Előfeltétel: 3. fázis*

### 4.1 Mikor indokolt a PostgreSQL?

A jelenlegi FAISS + JSON cache + Python in-memory keresés megoldás jól működik egyfelhasználós és kis csoportos használatnál. PostgreSQL-re akkor érdemes áttérni, ha:

- több szervert kell szinkronizálni,
- audit-napló kell (ki, mikor, mit kérdezett, mit töltött le, mire keresett),
- a full-text keresés teljesítménye Python-szinten már nem kielégítő,
- a dokumentum-metaadatokat (feltöltő, dátum, cimkék) tartósan tárolni kell,
- részlegalapú, joinolt keresési lekérdezések szükségesek.

### 4.2 Adatbázis-séma

```sql
-- Részlegek
CREATE TABLE departments (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    config_path TEXT NOT NULL
);

-- Dokumentumok
CREATE TABLE documents (
    id             SERIAL PRIMARY KEY,
    department_id  INT REFERENCES departments(id),
    doc_id         VARCHAR(16) UNIQUE NOT NULL,   -- letöltési azonosító (SHA256 prefix)
    file_path      TEXT NOT NULL,
    file_mtime     DOUBLE PRECISION,
    title          TEXT NOT NULL,
    dir_description TEXT,
    chunk_index    INT DEFAULT 0,
    total_chunks   INT DEFAULT 1,
    content        TEXT NOT NULL,
    content_tsv    TSVECTOR GENERATED ALWAYS AS
                   (to_tsvector('hungarian', content)) STORED,
    indexed_at     TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_documents_tsv  ON documents USING GIN(content_tsv);
CREATE INDEX idx_documents_dept ON documents(department_id);
CREATE INDEX idx_documents_docid ON documents(doc_id);

-- Audit napló
CREATE TABLE query_log (
    id            SERIAL PRIMARY KEY,
    event_type    VARCHAR(20) NOT NULL,  -- 'ask' | 'search' | 'download'
    department_id INT REFERENCES departments(id),
    user_id       INT,
    payload       TEXT,                  -- kérdés szövege vagy keresési kifejezés
    file_path     TEXT,                  -- letöltésnél a fájl útvonala
    result_count  INT,                   -- találatok száma
    duration_ms   INT,
    ip_address    INET,
    occurred_at   TIMESTAMP DEFAULT NOW()
);
```

**Megjegyzés az `event_type` mezőhöz:** mindhárom funkció – kérdezés, keresés, letöltés – külön eseménytípusként kerül naplózásra. Ez szükséges, hogy auditálható legyen: ki töltött le milyen dokumentumot, ki keresett milyen kifejezésre.

### 4.3 `tsvector` – hibrid keresés

A `tsvector` lehetővé teszi, hogy az embedding-alapú kérdés-válasz mellé valódi teljeszöveges keresést alkalmazzunk. A full-text search funkció így két üzemmódban futhat:

**Keresés üzemmód (2. fázis Python → 4. fázis SQL):**

```sql
-- Keresés egy részlegen belül
SELECT doc_id, title, file_path,
       ts_headline('hungarian', content,
                   plainto_tsquery('hungarian', $1),
                   'MaxWords=30, MinWords=15') AS excerpt
FROM documents
WHERE department_id = $2
  AND content_tsv @@ plainto_tsquery('hungarian', $1)
ORDER BY ts_rank(content_tsv, plainto_tsquery('hungarian', $1)) DESC
LIMIT $3;
```

Az `ts_headline` automatikusan generálja a találatot kiemelő kivonatot, kiváltva a 2. fázisban bevezetett Python-szintű `highlight()` függvényt.

**Hibrid lekérdezés (kérdés-válasz funkcióhoz):**

1. `tsvector` szűrés: jelöltlistát állít elő azokból a chunk-okból, amelyek tartalmazzák a kulcsszavakat
2. FAISS re-ranking: a jelöltek közül az embedding-távolság alapján kerülnek ki a legjobb találatok

Ez különösen hasznos, ha pontos szóegyezésre is szükség van (pl. számlaszámok, szerződésazonosítók).

### 4.4 Migrációs stratégia

A JSON cache → PostgreSQL átállás nem kell egyszerre megtörténjen. Ajánlott lépések:

1. PostgreSQL-be kerül a metaadat, a nyers szöveg és a `doc_id` → `file_path` leképezés
2. a FAISS index marad fájlalapú (könnyebb rebuild)
3. a `/download?id=...` végpont a `doc_id` alapján az adatbázisból keresi ki az útvonalat
4. hosszabb távon a FAISS helyett `pgvector` extension is szóba jöhet, ha az adatbázis-alapú keresés elegendő teljesítményt nyújt

---

## 5. fázis – Jogosultságkezelés és céges integráció

*Becsült időigény: 5–8 hét*  
*Előfeltétel: 4. fázis*

### 5.1 Hitelesítés

A Flask alkalmazás jelenleg teljesen nyitott. Céges környezetben legalább az alábbi rétegek szükségesek:

**Opció A – egyszerű, gyors:** HTTP Basic Auth vagy API-kulcs Nginx reverse proxy mögött. Elegendő, ha a rendszer csak belső hálózaton érhető el.

**Opció B – LDAP/Active Directory:** a `flask-ldap3-login` csomag segítségével a meglévő céges felhasználói fiókokkal lehet belépni. A csoporttagság alapján dől el, melyik részleg dokumentumai láthatók és tölthetők le.

**Opció C – SSO/OAuth2:** `flask-oauthlib` vagy `authlib` segítségével Google Workspace, Microsoft Entra ID (Azure AD) vagy Keycloak integrálható. Ez a legkomplexebb, de a legkényelmesebb felhasználói élményt adja.

### 5.2 Jogosultsági modell

```
Szerepkörök:
  admin        – minden részleg, konfiguráció módosítása, audit log megtekintése
  dept_admin   – saját részleg, refresh indítása, felhasználók kezelése
  user         – olvasás, kérdezés, keresés, letöltés a hozzárendelt részlegekben
  readonly     – csak kérdezés és keresés; letöltési jog nélkül
```

A `readonly` szerepkör bevezetése azt jelenti, hogy a letöltési link a `/search` és a kérdés-válasz oldalon is feltételesen jelenik meg: ha a felhasználónak nincs letöltési joga, a dokumentum neve szövegként jelenik meg link helyett.

Adatbázis-szinten a `users` és `user_departments` táblák kezelik a hozzárendeléseket:

```sql
CREATE TABLE users (
    id           SERIAL PRIMARY KEY,
    username     VARCHAR(100) UNIQUE NOT NULL,
    role         VARCHAR(20) NOT NULL DEFAULT 'user',
    created_at   TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_departments (
    user_id       INT REFERENCES users(id),
    department_id INT REFERENCES departments(id),
    can_download  BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (user_id, department_id)
);
```

A Flask route-okon `@login_required` és `@requires_role('dept_admin')` dekorátorokkal érvényesíthetők a jogok. A `/download` végponton külön ellenőrzés: a bejelentkezett felhasználónak `can_download = true` kell az adott részlegre.

### 5.3 Auditnapló a webes felületen

Minden esemény – kérdés, keresés, letöltés, refresh, bejelentkezési próbálkozás – kerüljön a `query_log` táblába. Az admin felületen szűrhető, exportálható lista biztosítson átláthatóságot:

- Ki töltött le milyen dokumentumot és mikor?
- Milyen keresési kifejezéseket használtak leggyakrabban?
- Melyik részleg dokumentumai a legnépszerűbbek?
- Hány sikertelen letöltési kísérlet érkezett (403)?

### 5.4 Konténerizálás

```yaml
# docker-compose.yml vázlat
services:
  doku_rag:
    build: .
    volumes:
      - /mnt/samba/iratok:/data/docs:ro   # dokumentumok (csak olvasás)
      - ./configs:/etc/doku_rag:ro         # ini fájlok
      - rag_index:/app/data                # FAISS index
    environment:
      - SMB_PASSWORD=${SMB_PASSWORD}
      - DB_URL=postgresql://user:pass@db/doku_rag
    depends_on:
      - db

  db:
    image: postgres:16
    volumes:
      - pg_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: doku_rag
      POSTGRES_USER: doku
      POSTGRES_PASSWORD: ${DB_PASSWORD}

volumes:
  rag_index:
  pg_data:
```

**Konténeres letöltési szempont:** ha a dokumentumok bind-mount-ként érhetők el (`:ro`), a `send_file` közvetlenül kiszolgálja azokat. Ha nem mount-olt útvonalról kell kiszolgálni (pl. közvetlen SMB-elérés), a temp könyvtárnak is kötetnek kell lennie, és gondoskodni kell a temp fájlok törléséről konténer-újraindítás után.

### 5.5 Ütemezett újraindexelés

Cron job vagy systemd timer segítségével a rendszer automatikusan ellenőrzi a dokumentumokat és szükség esetén újraindexel:

```bash
# /etc/cron.d/doku_rag
0 2 * * *  doku_rag  cd /app && .venv/bin/python -c \
  "from rag_system import RAGSystem; RAGSystem().refresh_data()"
```

Újraindexeléskor a `doc_id` értékek – mivel SHA256 hash az abszolút fájlútvonalból – stabil maradnak, így a már kiosztott letöltési linkek érvényes maradnak mindaddig, amíg a fájl útvonala nem változik.

---

## Prioritási sorrend

| Fázis | Prioritás | Előfeltétel |
|-------|-----------|-------------|
| 1 – Stabilitás, tesztek | magas | – |
| 2.1 – Letöltési végpont biztonság (doc_id, rate limit) | **kritikus** | 1. fázis |
| 2.2 – Full-text keresés gyorsítása, highlight | magas | 1. fázis |
| 2.3 – Keresési szűrők (típus, könyvtár, dátum) | közepes | 2.2 |
| 3.1 – Több ini fájl, részleg-izoláció | magas | 1. fázis |
| 3.2 – Samba támogatás | közepes | 3.1 |
| 3.3 – Párhuzamos részlegek, LRU cache | közepes | 3.1 |
| 4 – PostgreSQL (metaadat, FTS, audit) | közepes | 3. fázis |
| 5.1–5.2 – Jogosultságok, letöltési engedély | magas (céges bevezetésnél) | 4. fázis |
| 5.3 – Auditnapló felület | közepes | 5.2 |
| 5.4 – Docker | közepes | 4. fázis |
| 5.5 – Ütemezett indexelés | alacsony | 3. fázis |

> **Megjegyzés:** a 2.1 pont (letöltési végpont biztonság) kritikus prioritású, mert a jelenlegi megvalósítás belső fájlútvonalakat szivárogtat ki és nincs felhasználói jogosultság-ellenőrzése. Ha az alkalmazás több felhasználó számára is elérhető, ezt az 1. fázissal párhuzamosan kell elvégezni.

---

## Függőségek bővítése fázisonként

| Csomag | Fázis | Cél |
|--------|-------|-----|
| `pytest`, `pytest-mock` | 1 | egységtesztek |
| `flask-limiter` | 2.1 | rate limiting letöltési és keresési végpontokon |
| `psycopg2-binary` | 4 | PostgreSQL kapcsolat |
| `pgvector` | 4 (opcionális) | vektoros keresés PostgreSQL-ben |
| `flask-login` | 5 | munkamenet-kezelés |
| `flask-ldap3-login` | 5 | AD/LDAP hitelesítés |
| `authlib` | 5 | OAuth2/SSO |
| `smbprotocol` | 3.2 (opcionális) | közvetlen SMB elérés csatolás nélkül |
