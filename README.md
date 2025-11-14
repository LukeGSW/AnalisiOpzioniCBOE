````python?code_reference&code_event_index=2
import re

# Get the README content from the previous turn
readme_content = """
# Kriterion Quant - Analizzatore Chain Opzioni SPX

Una dashboard Streamlit ad alte prestazioni per l'analisi quantitativa posizionale della chain di opzioni SPX, basata su file CSV scaricati dalla CBOE.

Questo strumento traduce un singolo file CSV in un'analisi interattiva completa, focalizzandosi su Gamma Exposure (GEX), livelli di Open Interest/Volume, Max Pain e modelli di volatilità, come definito nel progetto Kriterion Quant [cite: 2025-05-24].

## 📸 Anteprima Dashboard

(Qui puoi inserire l'immagine `grafici.png` che mi hai mostrato)
`![Anteprima Dashboard](grafici.png)`

---

## 🎯 Caratteristiche Principali

Questo strumento implementa diverse analisi chiave dal documento di progettazione:

* **Uploader CSV Interattivo**: Permette di caricare il file `.csv` della chain CBOE direttamente nell'app.
* **Parsing Avanzato**: Esegue automaticamente il parsing del formato CSV CBOE, estraendo metadati chiave come lo Spot Price (da Bid/Ask) e il timestamp.
* **Dashboard Riepilogativo**: Una vista "summary" con i KPI principali e i tre grafici chiave (GEX, OI, Volume) disposti in colonne per un confronto immediato.
* **Analisi Gamma Exposure (GEX)**:
    * Calcolo del Net GEX ($) per la scadenza selezionata.
    * Identificazione del Gamma Switch Point (livello GEX=0).
    * Grafico a barre orizzontale per visualizzare l'esposizione gamma per strike.
* **Analisi Supporti/Resistenze (OI & Volumi)**:
    * Identificazione dei "Put Wall" (supporto) e "Call Wall" (resistenza) basati sul max OI rilevante.
    * Grafici a barre orizzontali bidirezionali per visualizzare il posizionamento (OI) e l'attività (Volume) per strike.
* [cite_start]**Modelli Statistici** [cite: 53-58]:
    * Calcolo del **Max Pain** (Dolore Massimo) per la scadenza.
    * Calcolo dei **Put/Call Ratios** (sia per OI che per Volume) come indicatori di sentiment.
    * Calcolo del **Movimento Atteso (Expected Move)** basato sulla IV At-The-Money (ATM).
* **Superficie di Volatilità**:
    * Grafico 3D interattivo della superficie di volatilità implicita (IV) (Strike vs DTE vs IV).

---

## 🛠️ Stack Tecnologico

* **Python 3.10+**
* **Streamlit**: Per l'interfaccia utente web e la dashboard.
* **Pandas**: Per il parsing, la pulizia e la manipolazione dei dati.
* **NumPy**: Per i calcoli quantitativi (Max Pain, GEX).
* **Plotly**: Per tutte le visualizzazioni interattive 2D e 3D.
* **SciPy**: Per l'interpolazione della superficie di volatilità 3D.

---

## 🚀 Installazione e Avvio

Per eseguire questa applicazione localmente:

1.  **Clona il repository:**
    ```
```text?code_stdout&code_event_index=2
README.md pulito (senza citazioni):

# Kriterion Quant - Analizzatore Chain Opzioni SPX

Una dashboard Streamlit ad alte prestazioni per l'analisi quantitativa posizionale della chain di opzioni SPX, basata su file CSV scaricati dalla CBOE.

Questo strumento traduce un singolo file CSV in un'analisi interattiva completa, focalizzandosi su Gamma Exposure (GEX), livelli di Open Interest/Volume, Max Pain e modelli di volatilità, come definito nel progetto Kriterion Quant.

## 📸 Anteprima Dashboard

(Qui puoi inserire l'immagine `grafici.png` che mi hai mostrato)
`![Anteprima Dashboard](grafici.png)`

---

## 🎯 Caratteristiche Principali

Questo strumento implementa diverse analisi chiave dal documento di progettazione:

* **Uploader CSV Interattivo**: Permette di caricare il file `.csv` della chain CBOE direttamente nell'app.
* **Parsing Avanzato**: Esegue automaticamente il parsing del formato CSV CBOE, estraendo metadati chiave come lo Spot Price (da Bid/Ask) e il timestamp.
* **Dashboard Riepilogativo**: Una vista "summary" con i KPI principali e i tre grafici chiave (GEX, OI, Volume) disposti in colonne per un confronto immediato.
* **Analisi Gamma Exposure (GEX)**:
    * Calcolo del Net GEX ($) per la scadenza selezionata.
    * Identificazione del Gamma Switch Point (livello GEX=0).
    * Grafico a barre orizzontale per visualizzare l'esposizione gamma per strike.
* **Analisi Supporti/Resistenze (OI & Volumi)**:
    * Identificazione dei "Put Wall" (supporto) e "Call Wall" (resistenza) basati sul max OI rilevante.
    * Grafici a barre orizzontali bidirezionali per visualizzare il posizionamento (OI) e l'attività (Volume) per strike.
* **Modelli Statistici**:
    * Calcolo del **Max Pain** (Dolore Massimo) per la scadenza.
    * Calcolo dei **Put/Call Ratios** (sia per OI che per Volume) come indicatori di sentiment.
    * Calcolo del **Movimento Atteso (Expected Move)** basato sulla IV At-The-Money (ATM).
* **Superficie di Volatilità**:
    * Grafico 3D interattivo della superficie di volatilità implicita (IV) (Strike vs DTE vs IV).

---

## 🛠️ Stack Tecnologico

* **Python 3.10+**
* **Streamlit**: Per l'interfaccia utente web e la dashboard.
* **Pandas**: Per il parsing, la pulizia e la manipolazione dei dati.
* **NumPy**: Per i calcoli quantitativi (Max Pain, GEX).
* **Plotly**: Per tutte le visualizzazioni interattive 2D e 3D.
* **SciPy**: Per l'interpolazione della superficie di volatilità 3D.

---

## 🚀 Installazione e Avvio

Per eseguire questa applicazione localmente:

1.  **Clona il repository:**
    ```bash
    git clone https://[TUO_URL_REPOSITORY_GITHUB]
    cd [NOME_CARTELLA_PROGETTO]
    ```

2.  **Crea e attiva un ambiente virtuale:**
    ```bash
    # (macOS/Linux)
    python3 -m venv venv
    source venv/bin/activate
    
    # (Windows)
    python -m venv venv
    .env\Scriptsctivate
    ```

3.  **Installa le dipendenze:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Esegui l'app Streamlit:**
    ```bash
    streamlit run app.py
    ```

L'applicazione si aprirà automaticamente nel tuo browser.

---

## 📁 Struttura del Progetto

Il progetto segue una struttura modulare per separare le responsabilità:

````

SPX\_Options\_Analyzer/
│
├── 📄 app.py                  \# File principale Streamlit (UI e orchestrazione)
├── 📄 data\_module.py           \# Modulo per il parsing CSV e preprocessing
├── 📄 calculations\_module.py   \# Modulo per tutti i calcoli (GEX, OI, Max Pain)
├── 📄 visualization\_module.py  \# Modulo per creare i grafici Plotly
├── 📄 requirements.txt         \# Dipendenze Python
└── 📄 README.md                \# Questo file

````


```bash
    git clone https://[TUO_URL_REPOSITORY_GITHUB]
    cd [NOME_CARTELLA_PROGETTO]
    ```

2.  **Crea e attiva un ambiente virtuale:**
    ```bash
    # (macOS/Linux)
    python3 -m venv venv
    source venv/bin/activate
    
    # (Windows)
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Installa le dipendenze:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Esegui l'app Streamlit:**
    ```bash
    streamlit run app.py
    ```

L'applicazione si aprirà automaticamente nel tuo browser.

---

## 📁 Struttura del Progetto

Il progetto segue una struttura modulare per separare le responsabilità:

````

SPX\_Options\_Analyzer/
│
├── 📄 app.py                  \# File principale Streamlit (UI e orchestrazione)
├── 📄 data\_module.py           \# Modulo per il parsing CSV e preprocessing
├── 📄 calculations\_module.py   \# Modulo per tutti i calcoli (GEX, OI, Max Pain)
├── 📄 visualization\_module.py  \# Modulo per creare i grafici Plotly
├── 📄 requirements.txt         \# Dipendenze Python
└── 📄 README.md                \# Questo file

```
"""

# Use regex to remove all patterns.
# \s* matches any whitespace before the citation.
# \ matches the citation itself.
cleaned_readme = re.sub(r'\s*\', '', readme_content)

print("README.md pulito (senza citazioni):")
print(cleaned_readme)

```

Ecco fatto. Ho rimosso tutti i tag \`\` dal testo.

Puoi copiare e incollare questo contenuto direttamente nel tuo file `README.md`.

-----

# Kriterion Quant - Analizzatore Chain Opzioni SPX

Una dashboard Streamlit ad alte prestazioni per l'analisi quantitativa posizionale della chain di opzioni SPX, basata su file CSV scaricati dalla CBOE.

Questo strumento traduce un singolo file CSV in un'analisi interattiva completa, focalizzandosi su Gamma Exposure (GEX), livelli di Open Interest/Volume, Max Pain e modelli di volatilità, come definito nel progetto Kriterion Quant.

## 📸 Anteprima Dashboard

(Qui puoi inserire l'immagine `grafici.png` che mi hai mostrato)
`![Anteprima Dashboard](grafici.png)`

-----

## 🎯 Caratteristiche Principali

Questo strumento implementa diverse analisi chiave dal documento di progettazione:

  * **Uploader CSV Interattivo**: Permette di caricare il file `.csv` della chain CBOE direttamente nell'app.
  * **Parsing Avanzato**: Esegue automaticamente il parsing del formato CSV CBOE, estraendo metadati chiave come lo Spot Price (da Bid/Ask) e il timestamp.
  * **Dashboard Riepilogativo**: Una vista "summary" con i KPI principali e i tre grafici chiave (GEX, OI, Volume) disposti in colonne per un confronto immediato.
  * **Analisi Gamma Exposure (GEX)**:
      * Calcolo del Net GEX ($) per la scadenza selezionata.
      * Identificazione del Gamma Switch Point (livello GEX=0).
      * Grafico a barre orizzontale per visualizzare l'esposizione gamma per strike.
  * **Analisi Supporti/Resistenze (OI & Volumi)**:
      * Identificazione dei "Put Wall" (supporto) e "Call Wall" (resistenza) basati sul max OI rilevante.
      * Grafici a barre orizzontali bidirezionali per visualizzare il posizionamento (OI) e l'attività (Volume) per strike.
  * **Modelli Statistici**:
      * Calcolo del **Max Pain** (Dolore Massimo) per la scadenza.
      * Calcolo dei **Put/Call Ratios** (sia per OI che per Volume) come indicatori di sentiment.
      * Calcolo del **Movimento Atteso (Expected Move)** basato sulla IV At-The-Money (ATM).
  * **Superficie di Volatilità**:
      * Grafico 3D interattivo della superficie di volatilità implicita (IV) (Strike vs DTE vs IV).

-----

## 🛠️ Stack Tecnologico

  * **Python 3.10+**
  * **Streamlit**: Per l'interfaccia utente web e la dashboard.
  * **Pandas**: Per il parsing, la pulizia e la manipolazione dei dati.
  * **NumPy**: Per i calcoli quantitativi (Max Pain, GEX).
  * **Plotly**: Per tutte le visualizzazioni interattive 2D e 3D.
  * **SciPy**: Per l'interpolazione della superficie di volatilità 3D.

-----

## 🚀 Installazione e Avvio

Per eseguire questa applicazione localmente:

1.  **Clona il repository:**

    ```bash
    git clone https://[TUO_URL_REPOSITORY_GITHUB]
    cd [NOME_CARTELLA_PROGETTO]
    ```

2.  **Crea e attiva un ambiente virtuale:**

    ```bash
    # (macOS/Linux)
    python3 -m venv venv
    source venv/bin/activate

    # (Windows)
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Installa le dipendenze:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Esegui l'app Streamlit:**

    ```bash
    streamlit run app.py
    ```

L'applicazione si aprirà automaticamente nel tuo browser.

-----

## 📁 Struttura del Progetto

Il progetto segue una struttura modulare per separare le responsabilità:

```
SPX_Options_Analyzer/
│
├── 📄 app.py                  # File principale Streamlit (UI e orchestrazione)
├── 📄 data_module.py           # Modulo per il parsing CSV e preprocessing
├── 📄 calculations_module.py   # Modulo per tutti i calcoli (GEX, OI, Max Pain)
├── 📄 visualization_module.py  # Modulo per creare i grafici Plotly
├── 📄 requirements.txt         # Dipendenze Python
└── 📄 README.md                # Questo file
```
