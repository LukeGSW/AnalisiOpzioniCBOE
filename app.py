# File: app.py
#
# File principale dell'applicazione Streamlit SPX Analyzer.
# [AGGIORNATO DEFINITIVO]
# 1. Refactor: Calcola i KPI una sola volta, prima dei tab.
# 2. Popola il Tab 7 (Summary Dashboard) con i KPI aggregati.
# -----------------------------------------------------------------------------

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime as dt

# --- Importa i nostri moduli custom ---
from data_module import parse_cboe_csv
from calculations_module import calculate_gex_metrics, calculate_oi_walls
from visualization_module import (
    create_gex_profile_chart, 
    create_oi_profile_chart, 
    create_volatility_surface_3d
)

# -----------------------------------------------------------------------------
# 1. IMPOSTAZIONE PAGINA E TEMA
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Kriterion Quant - SPX Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Applica il tema scuro professionale (Sez 5.3)
st.markdown("""
<style>
    /* ... (Stile CSS come prima, non è necessario ricopiarlo se è già lì) ... */
    .main { background-color: #0e1117; }
    body, .stApp, .stTextInput > div > div > input, .stSelectbox > div > div { 
        font-family: 'Inter', sans-serif; 
        color: #e5e7eb; 
    }
    div[data-testid="stMetric"] {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 8px;
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- TITOLO E HEADER ---
st.title("📊 SPX Options Chain Analyzer")
st.markdown(f"Powered by **Kriterion Quant**") 

# -----------------------------------------------------------------------------
# 2. LOGICA DI CARICAMENTO E CACHING DEI DATI
# -----------------------------------------------------------------------------

@st.cache_data
def load_data(uploaded_file):
    """Funzione wrapper (cache) per il nostro modulo di parsing."""
    try:
        df_processed, spot_price, data_timestamp = parse_cboe_csv(uploaded_file)
        if df_processed is None:
            return None, None, None
        return df_processed, spot_price, data_timestamp
    except Exception as e:
        st.error(f"Errore irreversibile durante il parsing: {e}")
        return None, None, None

uploaded_file = st.file_uploader(
    "Carica il file CSV della CBOE Options Chain",
    type=["csv"]
)

df_processed = None
spot_price = None
data_timestamp = None

if uploaded_file is not None:
    df_processed, spot_price, data_timestamp = load_data(uploaded_file)
else:
    st.info("In attesa del caricamento del file CSV...")

# -----------------------------------------------------------------------------
# 3. CORPO PRINCIPALE DELL'APP (Appare solo se i dati sono caricati)
# -----------------------------------------------------------------------------

if df_processed is not None and spot_price is not None:
    
    # --- 3.1. Barra dei Controlli (Selettore Scadenza) ---
    unique_expirations = sorted(df_processed['Expiration Date'].unique())
    expiry_options_map = {
        date.strftime('%Y-%m-%d (%a)'): date for date in unique_expirations
    }
    df_expiry_oi = df_processed.groupby('Expiration Date')['OI'].sum()
    default_expiry_label = df_expiry_oi.idxmax().strftime('%Y-%m-%d (%a)')
    
    selected_expiry_label = st.selectbox(
        'Seleziona la Scadenza:',
        options=expiry_options_map.keys(),
        index=list(expiry_options_map.keys()).index(default_expiry_label)
    )
    
    selected_expiry_date = expiry_options_map[selected_expiry_label]
    
    # --- 3.2. Filtra Dati per Scadenza ---
    df_selected_expiry = df_processed[
        df_processed['Expiration Date'] == selected_expiry_date
    ].copy()

    # --- [INIZIO REFACTOR] ---
    # 3.3. Calcola TUTTI i KPI *una sola volta* (prima dei tab)
    #
    # Calcola Metriche GEX
    gex_metrics = calculate_gex_metrics(df_selected_expiry, spot_price)
    
    # Calcola Metriche OI
    oi_metrics = calculate_oi_walls(df_selected_expiry, spot_price)
    # --- [FINE REFACTOR] ---


    # --- 3.4. Architettura Tab (Sezione 5.1) ---
    tab_summary, tab_gex, tab_oi, tab_vol, tab_flow, tab_stats, tab_risk = st.tabs([
        '📋 Summary Dashboard', # Spostato all'inizio
        '📊 Gamma Analysis',
        '🎯 Support/Resistance', 
        '📈 Volatility Surface',
        '💹 Flow Analysis',
        '📉 Statistical Models',
        '⚠️ Risk Scenarios'
    ])

    # -----------------------------------------------------------------
    # POPOLAMENTO TAB 0: SUMMARY DASHBOARD (Sez 5.2, Tab 7)
    # -----------------------------------------------------------------
    with tab_summary:
        st.header(f"Executive Summary per {selected_expiry_label}")
        
        # Key Metrics Grid (Sez 5.2, Tab 7) [cite: 65-67]
        st.subheader("Key Metrics Grid (per la scadenza selezionata)")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            label="Spot Price",
            value=f"{spot_price:.2f}"
        )
        col2.metric(
            label="Net GEX (Scadenza)",
            value=f"${gex_metrics['total_net_gex'] / 1_000_000_000:.2f} B",
            delta="SHORT" if gex_metrics['total_net_gex'] < 0 else "LONG",
            delta_color="inverse"
        )
        col3.metric(
            label="🛡️ Put Wall (Supporto)",
            value=f"{oi_metrics['put_wall_strike']:.0f}" if oi_metrics['put_wall_strike'] else "N/A"
        )
        col4.metric(
            label="🛑 Call Wall (Resistenza)",
            value=f"{oi_metrics['call_wall_strike']:.0f}" if oi_metrics['call_wall_strike'] else "N/A"
        )
        
        st.divider()
        
        # Mini Charts Dashboard (Sez 5.2, Tab 7) [cite: 68-69]
        st.subheader("Mini Charts Dashboard")
        
        # Usiamo due colonne per i grafici principali
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Profilo GEX (per Scadenza)")
            fig_gex = create_gex_profile_chart(
                df_gex_profile=gex_metrics['df_gex_profile'],
                spot_price=spot_price,
                gamma_switch_point=gex_metrics['gamma_switch_point'],
                expiry_label=selected_expiry_label
            )
            st.plotly_chart(fig_gex, use_container_width=True)

        with col2:
            st.markdown("#### Distribuzione OI (per Scadenza)")
            fig_oi = create_oi_profile_chart(
                df_oi_profile=oi_metrics['df_oi_profile'],
                spot_price=spot_price,
                expiry_label=selected_expiry_label
            )
            st.plotly_chart(fig_oi, use_container_width=True)


    # -----------------------------------------------------------------
    # POPOLAMENTO TAB 1: GAMMA ANALYSIS (Sez 5.2)
    # -----------------------------------------------------------------
    with tab_gex:
        st.header(f"Analisi Gamma (GEX) per {selected_expiry_label}")
        
        # 1. Mostra KPI (ora li abbiamo già calcolati)
        col1, col2, col3 = st.columns(3)
        col1.metric(
            label="Net GEX (per questa scadenza)",
            value=f"${gex_metrics['total_net_gex'] / 1_000_000_000:.2f} B"
        )
        col2.metric(
            label="Gamma Switch Point (GEX=0)",
            value=f"{gex_metrics['gamma_switch_point']:.2f}" if gex_metrics['gamma_switch_point'] else "N/A"
        )
        col3.metric(
            label="Spot-Switch Delta",
            value=f"{gex_metrics['spot_switch_delta']:.2f}" if gex_metrics['spot_switch_delta'] else "N/A"
        )
        
        # 2. Mostra Grafico (ora lo abbiamo già creato nel tab Summary)
        st.plotly_chart(fig_gex, use_container_width=True) # Riusiamo fig_gex

    # -----------------------------------------------------------------
    # POPOLAMENTO TAB 2: SUPPORT/RESISTANCE (Sez 5.2)
    # -----------------------------------------------------------------
    with tab_oi:
        st.header(f"Supporti e Resistenze (OI) per {selected_expiry_label}")
        
        # 1. Mostra KPI (già calcolati)
        col1, col2 = st.columns(2)
        col1.metric(
            label="🛡️ Put Wall (Supporto)",
            value=f"{oi_metrics['put_wall_strike']:.0f}" if oi_metrics['put_wall_strike'] else "N/A",
            help=f"OI: {oi_metrics['put_wall_oi']:,.0f}"
        )
        col2.metric(
            label="🛑 Call Wall (Resistenza)",
            value=f"{oi_metrics['call_wall_strike']:.0f}" if oi_metrics['call_wall_strike'] else "N/A",
            help=f"OI: {oi_metrics['call_wall_oi']:,.0f}"
        )
        
        # 2. Mostra Grafico (già creato nel tab Summary)
        st.plotly_chart(fig_oi, use_container_width=True) # Riusiamo fig_oi

    # -----------------------------------------------------------------
    # POPOLAMENTO TAB 3: VOLATILITY SURFACE (Sez 5.2)
    # -----------------------------------------------------------------
    with tab_vol:
        st.header("Superficie di Volatilità (Tutte le Scadenze)")
        
        with st.spinner("Calcolo e interpolazione superficie 3D in corso..."):
            # Questo grafico è l'unico che calcoliamo qui,
            # perché non dipende dalla scadenza selezionata.
            fig_vol = create_volatility_surface_3d(df_processed)
            st.plotly_chart(fig_vol, use_container_width=True)

    # -----------------------------------------------------------------
    # PLACEHOLDER PER GLI ALTRI TAB (Fase 2)
    # -----------------------------------------------------------------
    with tab_flow:
        st.header("Flow Analysis (Fase 2)")
        st.info("Come da Sezione 4.2 del progetto (Large trades, UOA, Delta-weighted metrics).")
        st.warning("Questa analisi richiede dati tick-by-tick, non disponibili nel CSV corrente.")

    with tab_stats:
        st.header("Statistical Models (Fase 2)")
        st.info("Come da Sezione 4.4 del progetto (Regime Detection, Probability Models).")

    with tab_risk:
        st.header("Risk Scenarios (Fase 2)")
        st.info("Come da Sezione 5.2, Tab 6 (Stress Test, VaR, Greeks Sensitivities).")
