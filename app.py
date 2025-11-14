# File: app.py
#
# File principale dell'applicazione Streamlit SPX Analyzer.
# [CORRETTO DEFINITIVO]
# 1. Risolto 'StreamlitDuplicateElementId' aggiungendo 'key' uniche
#    ai grafici Plotly.
# 2. Rimosse le schede (tab) vuote come richiesto.
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
    /* Tema scuro di base */
    .main { background-color: #0e1117; }
    /* Font (come da Sez. 5.3) */
    body, .stApp, .stTextInput > div > div > input, .stSelectbox > div > div { 
        font-family: 'Inter', sans-serif; 
        color: #e5e7eb; 
    }
    /* Stile per le 'Metrics Cards' (st.metric) */
    div[data-testid="stMetric"] {
        background-color: #111827; /* Colore plot_bgcolor */
        border: 1px solid #1f2937; /* Colore griglia */
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

    # --- 3.3. Calcola TUTTI i KPI *una sola volta* ---
    gex_metrics = calculate_gex_metrics(df_selected_expiry, spot_price)
    oi_metrics = calculate_oi_walls(df_selected_expiry, spot_price)
    
    # --- 3.4. Architettura Tab (Pulita) ---
    # [CORREZIONE] Rimosse le tab non utilizzate
    tab_summary, tab_gex, tab_oi, tab_vol = st.tabs([
        '📋 Summary Dashboard',
        '📊 Gamma Analysis',
        '🎯 Support/Resistance', 
        '📈 Volatility Surface'
    ])

    # -----------------------------------------------------------------
    # POPOLAMENTO TAB 0: SUMMARY DASHBOARD (Sez 5.2, Tab 7)
    # -----------------------------------------------------------------
    with tab_summary:
        st.header(f"Executive Summary per {selected_expiry_label}")
        
        # Key Metrics Grid (Sez 5.2, Tab 7)
        st.subheader("Key Metrics Grid (per la scadenza selezionata)")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(label="Spot Price", value=f"{spot_price:.2f}")
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
        
        # Mini Charts Dashboard (Sez 5.2, Tab 7)
        st.subheader("Mini Charts Dashboard")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Profilo GEX (per Scadenza)")
            fig_gex = create_gex_profile_chart(
                gex_metrics['df_gex_profile'], spot_price, gex_metrics['gamma_switch_point'], selected_expiry_label
            )
            # [CORREZIONE] Aggiunta key unica
            st.plotly_chart(fig_gex, use_container_width=True, key="summary_gex_chart")

        with col2:
            st.markdown("#### Distribuzione OI (per Scadenza)")
            fig_oi = create_oi_profile_chart(
                oi_metrics['df_oi_profile'], spot_price, selected_expiry_label
            )
            # [CORREZIONE] Aggiunta key unica
            st.plotly_chart(fig_oi, use_container_width=True, key="summary_oi_chart")

    # -----------------------------------------------------------------
    # POPOLAMENTO TAB 1: GAMMA ANALYSIS (Sez 5.2)
    # -----------------------------------------------------------------
    with tab_gex:
        st.header(f"Analisi Gamma (GEX) per {selected_expiry_label}")
        
        col1, col2, col3 = st.columns(3)
        col1.metric(label="Net GEX (per questa scadenza)", value=f"${gex_metrics['total_net_gex'] / 1_000_000_000:.2f} B")
        col2.metric(label="Gamma Switch Point (GEX=0)", value=f"{gex_metrics['gamma_switch_point']:.2f}" if gex_metrics['gamma_switch_point'] else "N/A")
        col3.metric(label="Spot-Switch Delta", value=f"{gex_metrics['spot_switch_delta']:.2f}" if gex_metrics['spot_switch_delta'] else "N/A")
        
        # [CORREZIONE] Aggiunta key unica
        st.plotly_chart(fig_gex, use_container_width=True, key="gex_tab_chart")

    # -----------------------------------------------------------------
    # POPOLAMENTO TAB 2: SUPPORT/RESISTANCE (Sez 5.2)
    # -----------------------------------------------------------------
    with tab_oi:
        st.header(f"Supporti e Resistenze (OI) per {selected_expiry_label}")
        
        col1, col2 = st.columns(2)
        col1.metric(label="🛡️ Put Wall (Supporto)", value=f"{oi_metrics['put_wall_strike']:.0f}" if oi_metrics['put_wall_strike'] else "N/A", help=f"OI: {oi_metrics['put_wall_oi']:,.0f}")
        col2.metric(label="🛑 Call Wall (Resistenza)", value=f"{oi_metrics['call_wall_strike']:.0f}" if oi_metrics['call_wall_strike'] else "N/A", help=f"OI: {oi_metrics['call_wall_oi']:,.0f}")
        
        # [CORREZIONE] Aggiunta key unica
        st.plotly_chart(fig_oi, use_container_width=True, key="oi_tab_chart")

    # -----------------------------------------------------------------
    # POPOLAMENTO TAB 3: VOLATILITY SURFACE (Sez 5.2)
    # -----------------------------------------------------------------
    with tab_vol:
        st.header("Superficie di Volatilità (Tutte le Scadenze)")
        
        with st.spinner("Calcolo e interpolazione superficie 3D in corso..."):
            fig_vol = create_volatility_surface_3d(df_processed)
            # [CORREZIONE] Aggiunta key unica (anche se non strettamente duplicata, è buona norma)
            st.plotly_chart(fig_vol, use_container_width=True, key="vol_surface_chart")
