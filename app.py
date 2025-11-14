# File: app.py
#
# File principale dell'applicazione Streamlit SPX Analyzer.
# Gestisce l'UI, l'upload dei file e orchestra i moduli.
# -----------------------------------------------------------------------------

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime as dt

# --- Importa i nostri moduli custom ---
from data_module import parse_cboe_csv
# (Più avanti importeremo anche calculations_module e visualization_module)

# -----------------------------------------------------------------------------
# 1. IMPOSTAZIONE PAGINA E TEMA
# -----------------------------------------------------------------------------

# set_page_config deve essere il primo comando Streamlit
st.set_page_config(
    page_title="Kriterion Quant - SPX Analyzer",
    page_icon="📊",
    layout="wide",  # Usa l'intero schermo
    initial_sidebar_state="collapsed"
)

# Applica il tema scuro professionale (Sez 5.3)
st.markdown("""
<style>
    /* Tema scuro di base */
    .main { background-color: #0e1117; }
    /* Font (come da Sez. 5.3) */
    body, .stApp, .stTextInput > div > div > input, .stSelectbox > div > div { 
        font-family: 'Inter', sans-serif; 
        color: #e5e7eb; 
    }
    /* Colori del tema Kriterion */
    .stButton>button {
        background-color: #10b981; /* accent_bullish */
        color: #0e1117;
    }
    .stSelectbox > div > div:hover {
        border-color: #10b981;
    }
</style>
""", unsafe_allow_html=True)

# --- TITOLO E HEADER ---
st.title("📊 SPX Options Chain Analyzer")
st.markdown(f"Powered by **Kriterion Quant**") # Branding (Sez 5.3)

# -----------------------------------------------------------------------------
# 2. LOGICA DI CARICAMENTO E CACHING DEI DATI
# -----------------------------------------------------------------------------

# Usiamo @st.cache_data per assicurarci che il parsing avvenga
# SOLO una volta per file, e non ad ogni interazione dell'utente.
@st.cache_data
def load_data(uploaded_file):
    """
    Funzione wrapper (cache) per il nostro modulo di parsing.
    """
    df_processed, spot_price, data_timestamp = parse_cboe_csv(uploaded_file)
    if df_processed is None:
        return None, None, None # Fallimento
    return df_processed, spot_price, data_timestamp

# --- Widget File Uploader ---
uploaded_file = st.file_uploader(
    "Carica il file CSV della CBOE Options Chain",
    type=["csv"]
)

# Variabili principali
df_processed = None
spot_price = None
data_timestamp = None

if uploaded_file is not None:
    # Se un file è caricato, esegui la funzione cachata
    df_processed, spot_price, data_timestamp = load_data(uploaded_file)
else:
    st.info("In attesa del caricamento del file CSV...")

# -----------------------------------------------------------------------------
# 3. CORPO PRINCIPALE DELL'APP (Appare solo se i dati sono caricati)
# -----------------------------------------------------------------------------

if df_processed is not None and spot_price is not None:
    
    st.success(f"File processato. Spot: **{spot_price:.2f}** | Timestamp: {data_timestamp}")
    
    # --- 3.1. Barra dei Controlli (Selettore Scadenza) ---
    # Come da Sezione 3.3 e 5.2
    
    # Estrai scadenze uniche
    unique_expirations = sorted(df_processed['Expiration Date'].unique())
    
    # Crea mappa {Label: Valore} (Logica Cella 10 Corretta)
    expiry_options_map = {}
    for date in unique_expirations:
        label = date.strftime('%Y-%m-%d (%a)')
        expiry_options_map[label] = date
        
    # Trova default (Max OI)
    df_expiry_oi = df_processed.groupby('Expiration Date')['OI'].sum()
    default_expiry_label = df_expiry_oi.idxmax().strftime('%Y-%m-%d (%a)')
    
    # Crea il Selettore (Selectbox)
    selected_expiry_label = st.selectbox(
        'Seleziona la Scadenza:',
        options=expiry_options_map.keys(),
        index=list(expiry_options_map.keys()).index(default_expiry_label), # Imposta default
        key='expiry_selector'
    )
    
    # Ottieni il valore Timestamp (il valore reale, non la label)
    selected_expiry_date = expiry_options_map[selected_expiry_label]
    
    st.markdown(f"### Analisi per Scadenza: {selected_expiry_label}")
    
    # --- 3.2. Architettura Tab (Sezione 5.1) ---
    
    # Filtra il DataFrame per la *sola* scadenza selezionata
    # Questo è il DataFrame che tutti i moduli useranno
    df_selected_expiry = df_processed[
        df_processed['Expiration Date'] == selected_expiry_date
    ].copy()

    # Creazione dei Tab
    tab_gex, tab_oi, tab_vol, tab_flow, tab_stats, tab_risk, tab_summary = st.tabs([
        '📊 Gamma Analysis',
        '🎯 Support/Resistance', 
        '📈 Volatility Surface',
        '💹 Flow Analysis',
        '📉 Statistical Models',
        '⚠️ Risk Scenarios',
        '📋 Summary Dashboard'
    ])

    # --- Riempimento dei Tab (per ora, placeholder) ---
    
    with tab_gex:
        st.header("Analisi Gamma Exposure (GEX)")
        st.write("Prossimo passo: Creare `calculations_module.py` e `visualization_module.py` per popolare questo tab.")
        st.dataframe(df_selected_expiry.head()) # Mostra un'anteprima

    with tab_oi:
        st.header("Analisi Supporti e Resistenze (OI)")
        st.write("Questo tab mostrerà il grafico OI bidirezionale.")

    with tab_vol:
        st.header("Superficie di Volatilità")
        st.write("Questo tab mostrerà il grafico 3D della volatilità.")
        
    # Gli altri tab (come da progetto)
    with tab_flow:
        st.header("Flow Analysis (Fase 2)")
        st.write("Come da Sezione 4.2 del progetto.")

    with tab_stats:
        st.header("Statistical Models (Fase 2)")
        st.write("Come da Sezione 4.4 del progetto.")

    with tab_risk:
        st.header("Risk Scenarios (Fase 2)")
        st.write("Come da Sezione 5.2, Tab 6.")

    with tab_summary:
        st.header("Executive Summary (Fase 2)")
        st.write("Come da Sezione 5.2, Tab 7.")
