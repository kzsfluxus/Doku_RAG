# Doku RAG – Fejlesztési terv

**Verzió:** 1.0  
**Állapot:** tervezet  
**Cél:** a jelenlegi prototípus fokozatos fejlesztése professzionális, céges környezetben is bevethető rendszerré

---

## Összefoglalás

A jelenlegi Doku RAG (v1) egy működőképes, egyszemélyes vagy kis csapatban használható dokumentum-kereső rendszer. Az alábbiakban négy fejlesztési fázis kerül leírásra, amelyek végén a rendszer képes lesz:

- több részleg párhuzamos, izolált dokumentumtárát kezelni,
- jogosultságszinteket érvényesíteni (részleg, szerep, felhasználó szinten),
- Samba-megosztásokon tárolt dokumentumokat feldolgozni,
- PostgreSQL-alapú, tartós metaadat-tárolást és teljeszöveges keresést biztosítani,
- webes felületen hitelesítést és audit-naplózást nyújtani,
- és skálázhatóan, konténerizáltan futni.

---

## 1. fázis – Stabilitás és tesztelhetőség

*Becsült időigény: 2–3 hét*

Ez a fázis nem ad új funkciókat, de nélküle a későbbi fejlesztés kockázatos. A meglévő kódbázis tesztelhetőségét és megbízhatóságát növeli.

### 1.1 Egységtesztek

A Wiki RAG-ból örökölt tesztfájlok (`tests/`) nagy részben MediaWiki-specifikusak. Ezeket ki kell cserélni Doku RAG-specifikus tesztekre:

- `test_extractors.py` – minden fájltípushoz legalább egy pozitív és egy hibás eset
- `test_doc_loader.py` – könyvtárbejárás, chunk-olás, snapshot-logika
- `test_text_cleaner.py` – `clean_extracted_text` és `clean_llm_response` külön tesztelve
- `test_embedder.py` – index építés, mentés, betöltés, lekérdezés
- `test_rag_system.py` – inicializálás, `process_question`, hibakezelés

Ajánlott keretrendszer: `pytest` + `unittest.mock` (Ollama és LLM hívások mockolásához).

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
- `INFO` – fájl beolvasva, cache frissítve, kérdés feldolgozva
- `WARNING` – nem olvasható fájl, hiányzó könyvtár
- `ERROR` – inicializálási hiba, LLM nem válaszol

A logfájl elérési útja legyen konfigurálható az ini-ban.

---

## 2. fázis – Többfelhasználós és többrészleges támogatás

*Becsült időigény: 3–5 hét*

### 2.1 Több ini fájl – részlegenkénti izoláció

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

**Index-izoláció:**

Minden részlegnek külön `data/` alkönyvtár:

```
data/
├── hr/
│   ├── documents.json
│   ├── index.faiss
│   └── file_snapshot.json
├── penzugy/
│   └── ...
```

### 2.2 Samba-megosztások támogatása

Ha a dokumentumok hálózati Samba-megosztáson vannak (pl. `\\szerver\HR`), a rendszernek ezt transzparensen kell kezelnie.

**Megközelítési lehetőségek:**

1. **Mount-alapú (ajánlott):** a Samba-megosztás Linux oldalon fel van csatolva (pl. `/mnt/samba/hr`), és az ini fájlban ez szerepel `root_dir`-ként. A Doku RAG szempontjából ez nem különbözik egy helyi könyvtártól.

2. **SMB-kliens könyvtár:** `smbprotocol` Python csomag segítségével közvetlen SMB-elérés. Ez csak akkor indokolt, ha a csatolás nem megoldható (pl. konténeres környezetben).

Az ini-ban jelezni kell, ha a forrás hálózati meghajtó:

```ini
[documents]
root_dir   = /mnt/samba/hr_iratok
mount_type = smb           # helyi | smb | nfs
smb_server = \\192.168.1.10\HR
smb_user   = domain\felhasznalo
smb_pass   = ${SMB_PASSWORD}   # környezeti változóból
```

A jelszót sosem szabad az ini fájlban tárolni éles környezetben – environment variable vagy titkosított vault (pl. HashiCorp Vault, systemd credentials) javasolt.

### 2.3 Párhuzamos részlegek egyidejű kezelése

A Flask alkalmazásban több `RAGSystem` példány futhat egyszerre, ha minden részlegnek saját példánya van. Ez memóriaigényes lehet; alternatíva a lazy loading: csak az éppen szükséges részleg töltődik be, és egy egyszerű LRU cache tartja életben a legutóbb használtakat.

---

## 3. fázis – PostgreSQL integráció

*Becsült időigény: 4–6 hét*

### 3.1 Mikor indokolt a PostgreSQL?

A jelenlegi FAISS + JSON cache megoldás jól működik egyfelhasználós és kis csoportos használatnál. PostgreSQL-re akkor érdemes áttérni, ha:

- több szervert kell szinkronizálni,
- audit-napló kell (ki, mikor, mit kérdezett),
- teljeszöveges keresés szükséges az vektoros keresés mellett,
- a dokumentum-metaadatokat (feltöltő, dátum, cimkék) tartósan tárolni kell.

### 3.2 Adatbázis-séma

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

CREATE INDEX idx_documents_tsv ON documents USING GIN(content_tsv);
CREATE INDEX idx_documents_dept ON documents(department_id);

-- Audit napló
CREATE TABLE query_log (
    id            SERIAL PRIMARY KEY,
    department_id INT REFERENCES departments(id),
    user_id       INT,
    question      TEXT NOT NULL,
    answer_length INT,
    duration_ms   INT,
    queried_at    TIMESTAMP DEFAULT NOW()
);
```

### 3.3 `tsvector` – hibrid keresés

A `tsvector` lehetővé teszi, hogy az embedding-alapú keresés mellé teljeszöveges szűrést is alkalmazzunk. A kombinált megközelítés:

1. `tsvector` szűrés: jelöltlistát állít elő azokból a chunk-okból, amelyek tartalmazzák a kulcsszavakat,
2. FAISS re-ranking: a jelöltek közül az embedding-távolság alapján kerülnek ki a legjobb találatok.

Ez különösen hasznos, ha pontos szóegyezésre is szükség van (pl. számlaszámok, szerződésazonosítók).

```python
# Hibrid lekérdezés pszeudokód
candidates = db.query(
    "SELECT id, content FROM documents "
    "WHERE department_id = %s "
    "AND content_tsv @@ plainto_tsquery('hungarian', %s) "
    "LIMIT 50",
    [dept_id, question]
)
# → ezek közül FAISS re-rank top_k
```

### 3.4 Migrációs stratégia

A JSON cache → PostgreSQL átállás nem kell egyszerre megtörténjen. Ajánlott lépések:

1. PostgreSQL-be kerül a metaadat és a nyers szöveg,
2. a FAISS index marad fájlalapú (könnyebb rebuild),
3. hosszabb távon a FAISS helyett `pgvector` extension is szóba jöhet, ha az adatbázis-alapú keresés elegendő teljesítményt nyújt.

---

## 4. fázis – Jogosultságkezelés és céges integráció

*Becsült időigény: 5–8 hét*

### 4.1 Hitelesítés

A Flask alkalmazás jelenleg teljesen nyitott. Céges környezetben legalább az alábbi rétegek szükségesek:

**Opció A – egyszerű, gyors:** HTTP Basic Auth vagy API-kulcs Nginx reverse proxy mögött. Elegendő, ha a rendszer csak belső hálózaton érhető el.

**Opció B – LDAP/Active Directory:** a `flask-ldap3-login` csomag segítségével a meglévő céges felhasználói fiókokkal lehet belépni. A csoporttagság alapján dől el, melyik részleg dokumentumai láthatók.

**Opció C – SSO/OAuth2:** `flask-oauthlib` vagy `authlib` segítségével Google Workspace, Microsoft Entra ID (Azure AD) vagy Keycloak integrálható. Ez a legkomplexebb, de a legkényelmesebb felhasználói élményt adja.

### 4.2 Jogosultsági modell

```
Szerepkörök:
  admin        – minden részleg, konfiguráció módosítása, audit log
  dept_admin   – saját részleg, refresh indítása, felhasználók kezelése
  user         – olvasás, kérdezés a hozzárendelt részlegekben
  readonly     – csak kérdezés, nincs refresh jog
```

Adatbázis-szinten a `users` és `user_departments` táblák kezelik a hozzárendeléseket. A Flask route-okon `@login_required` és `@requires_role('dept_admin')` dekorátorokkal érvényesíthetők a jogok.

### 4.3 Auditnapló a webes felületen

Minden kérdés, refresh-esemény és bejelentkezési próbálkozás kerüljön a `query_log` táblába. Az admin felületen szűrhető, exportálható lista biztosítson átláthatóságot.

### 4.4 Konténerizálás

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

### 4.5 Ütemezett újraindexelés

Cron job vagy systemd timer segítségével a rendszer automatikusan ellenőrzi a dokumentumokat és szükség esetén újraindexel:

```bash
# /etc/cron.d/doku_rag
0 2 * * *  doku_rag  cd /app && .venv/bin/python -c \
  "from rag_system import RAGSystem; RAGSystem().refresh_data()"
```

---

## Prioritási sorrend

| Fázis | Prioritás | Előfeltétel |
|-------|-----------|-------------|
| 1 – Stabilitás, tesztek | magas | – |
| 2.1 – Több ini fájl | magas | 1. fázis |
| 2.2 – Samba támogatás | közepes | 2.1 |
| 2.3 – Párhuzamos részlegek | közepes | 2.1 |
| 3.1–3.3 – PostgreSQL | közepes | 2. fázis |
| 4.1–4.2 – Jogosultságok | magas (céges bevezetésnél) | 3. fázis |
| 4.3 – Docker | közepes | 3. fázis |
| 4.4 – Ütemezett indexelés | alacsony | 2. fázis |

---

## Függőségek bővítése fázisonként

| Csomag | Fázis | Cél |
|--------|-------|-----|
| `pytest`, `pytest-mock` | 1 | egységtesztek |
| `psycopg2-binary` | 3 | PostgreSQL kapcsolat |
| `pgvector` | 3 (opcionális) | vektor keresés PG-ben |
| `flask-login` | 4 | munkamenet-kezelés |
| `flask-ldap3-login` | 4 | AD/LDAP hitelesítés |
| `authlib` | 4 | OAuth2/SSO |
| `smbprotocol` | 2.2 (opcionális) | közvetlen SMB elérés |
