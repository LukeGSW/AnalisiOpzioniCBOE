# File: app.py
#
# [VERSIONE AGGIORNATA & PULITA - CON EXPORT JSON]
# - Include tutte le funzionalità originali (Drift Chart, GEX, OI, Stats).
# - INCLUDE: Pulsante per scaricare i dati di analisi in formato JSON (LLM Ready).
# - RISOLTO: Sostituito parametro deprecato 'use_container_width' con "width='stretch'".
# -----------------------------------------------------------------------------

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import datetime as dt
import json

# --- Importa i nostri moduli custom ---
from data_module import parse_cboe_csv
from calculations_module import (
    calculate_gex_metrics, 
    calculate_oi_walls,
    calculate_max_pain,
    calculate_pc_ratios,
    calculate_expected_move,
    calculate_volume_profile,
    calculate_activity_ratio
)
from visualization_module import (
    create_gex_profile_chart, 
    create_oi_profile_chart, 
    create_volatility_surface_3d,
    create_volume_profile_chart,
    create_max_pain_chart,
    create_activity_ratio_chart,
    create_drift_arrow_chart 
)

# -----------------------------------------------------------------------------
# HELPER: SERIALIZZAZIONE JSON
# -----------------------------------------------------------------------------
class NumpyEncoder(json.JSONEncoder):
    """
    Encoder personalizzato per gestire tipi NumPy e Pandas durante 
    la conversione in JSON. Fondamentale per evitare errori di tipo.
    """
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient='records')
        elif isinstance(obj, (pd.Timestamp, dt.date, dt.datetime)):
            return obj.isoformat()
        return super(NumpyEncoder, self).default(obj)

# -----------------------------------------------------------------------------
# 1. IMPOSTAZIONE PAGINA E TEMA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Kriterion Quant - SPX Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    body, .stApp, .stTextInput > div > div > input, .stSelectbox > div > div { 
        font-family: 'Inter', sans-serif; color: #e5e7eb; 
    }
    div[data-testid="stMetric"] {
        background-color: #111827; border: 1px solid #1f2937; 
        border-radius: 8px; padding: 10px;
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
    try:
        df_processed, spot_price, data_timestamp = parse_cboe_csv(uploaded_file)
        if df_processed is None: return None, None, None
        return df_processed, spot_price, data_timestamp
    except Exception as e:
        st.error(f"Errore irreversibile durante il parsing: {e}")
        return None, None, None

uploaded_file = st.file_uploader("Carica il file CSV della CBOE Options Chain", type=["csv"])
df_processed, spot_price, data_timestamp = (None, None, None)
if uploaded_file is not None:
    df_processed, spot_price, data_timestamp = load_data(uploaded_file)
else:
    st.info("In attesa del caricamento del file CSV...")

# -----------------------------------------------------------------------------
# 3. CORPO PRINCIPALE DELL'APP
# -----------------------------------------------------------------------------
if df_processed is not None and spot_price is not None:
    
    # --- 3.1. Barra dei Controlli (Selettore Scadenza) ---
    unique_expirations = sorted(df_processed['Expiration Date'].unique())
    expiry_options_map = {date.strftime('%Y-%m-%d (%a)'): date for date in unique_expirations}
    
    # Safety check se il file non ha scadenze leggibili
    if not expiry_options_map:
        st.error("Nessuna scadenza valida trovata nel file.")
        st.stop()

    df_expiry_oi = df_processed.groupby('Expiration Date')['OI'].sum()
    default_expiry_label = df_expiry_oi.idxmax().strftime('%Y-%m-%d (%a)')
    
    selected_expiry_label = st.selectbox(
        'Seleziona la Scadenza:', options=expiry_options_map.keys(),
        index=list(expiry_options_map.keys()).index(default_expiry_label)
    )
    selected_expiry_date = expiry_options_map[selected_expiry_label]
    
    # --- 3.2. Filtra Dati per Scadenza ---
    df_selected_expiry = df_processed[df_processed['Expiration Date'] == selected_expiry_date].copy()

    # --- 3.3. Calcola TUTTI i KPI (una sola volta) ---
    with st.spinner("Calcolo metriche per la scadenza..."):
        gex_metrics = calculate_gex_metrics(df_selected_expiry, spot_price)
        oi_metrics = calculate_oi_walls(df_selected_expiry, spot_price)
        vol_metrics = calculate_volume_profile(df_selected_expiry, spot_price)
        activity_metrics = calculate_activity_ratio(df_selected_expiry, spot_price)
        max_pain_strike, df_payouts = calculate_max_pain(df_selected_expiry)
        pc_ratios = calculate_pc_ratios(df_selected_expiry)
        expected_move = calculate_expected_move(df_selected_expiry, spot_price)
    
    # =========================================================================
    #  UPGRADE: PREPARAZIONE EXPORT JSON
    # =========================================================================
    export_data = {
        "metadata": {
            "application": "Kriterion Quant - SPX Analyzer",
            "export_date": dt.datetime.now().isoformat(),
            "analyzed_expiry": selected_expiry_label,
            "spot_price": spot_price,
            "data_timestamp_file": str(data_timestamp)
        },
        "market_summary": {
            "max_pain": max_pain_strike,
            "put_call_ratio_oi": pc_ratios['pc_oi_ratio'],
            "put_call_ratio_vol": pc_ratios['pc_vol_ratio'],
            "expected_move_value": expected_move['move'],
            "expected_move_range": [expected_move['lower_band'], expected_move['upper_band']],
            "implied_vol_atm": expected_move['iv_atm']
        },
        "gamma_analysis": {
            "total_net_gex": gex_metrics['total_net_gex'],
            "gamma_switch_point": gex_metrics['gamma_switch_point'],
            "spot_switch_delta": gex_metrics['spot_switch_delta'],
            # Convertiamo il DF del profilo GEX in lista di dizionari per l'LLM
            "gex_profile_data": gex_metrics['df_gex_profile'].to_dict(orient='records')
        },
        "levels_support_resistance": {
            "put_wall_strike": oi_metrics['put_wall_strike'],
            "put_wall_oi": oi_metrics['put_wall_oi'],
            "call_wall_strike": oi_metrics['call_wall_strike'],
            "call_wall_oi": oi_metrics['call_wall_oi'],
            # Dati completi per analisi struttura OI
            "oi_structure": oi_metrics['df_oi_profile'].to_dict(orient='records')
        },
        "drift_analysis": {
            "vwas_drift_score": activity_metrics['drift_score'],
            "drift_bias": "BULLISH" if activity_metrics['drift_score'] > spot_price else "BEARISH",
            "volume_structure": vol_metrics['df_vol_profile'].to_dict(orient='records'),
            "activity_ratios": activity_metrics['df_activity_profile'].to_dict(orient='records')
        }
    }
    
    # Serializzazione in stringa JSON
    json_string = json.dumps(export_data, cls=NumpyEncoder, indent=4)

    # --- 3.4. Architettura Tab ---
    tab_summary, tab_gex, tab_oi_vol, tab_stats, tab_vol_surf = st.tabs([
        '📋 Summary Dashboard', '📊 Gamma Analysis',
        '🎯 Support/Resistance (OI & Vol)', '📉 Statistical Models', '📈 Volatility Surface'
    ])

    # -----------------------------------------------------------------
    # POPOLAMENTO SIDEBAR (Download Button)
    # -----------------------------------------------------------------
    with st.sidebar:
        st.divider()
        st.header("📥 Export Dati")
        st.download_button(
            label="Scarica JSON Analisi (LLM Ready)",
            data=json_string,
            file_name=f"kriterion_spx_analysis_{selected_expiry_label.split()[0]}.json",
            mime="application/json",
            help="Scarica un file JSON strutturato contenente tutti i calcoli (GEX, OI, Drift, Max Pain) per la scadenza selezionata."
        )

    # -----------------------------------------------------------------
    # POPOLAMENTO TAB 0: SUMMARY DASHBOARD
    # -----------------------------------------------------------------
    with tab_summary:
        st.header(f"Executive Summary per {selected_expiry_label}")
        
        st.subheader("Key Metrics Grid (per la scadenza selezionata)")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric(label="Spot Price", value=f"{spot_price:.2f}")
        col2.metric(label="Net GEX (Scadenza)", value=f"${gex_metrics['total_net_gex'] / 1_000_000_000:.2f} B",
                    delta="SHORT" if gex_metrics['total_net_gex'] < 0 else "LONG", delta_color="inverse")
        col3.metric(label="🛡️ Put Wall (Supporto)", value=f"{oi_metrics['put_wall_strike']:.0f}" if oi_metrics['put_wall_strike'] else "N/A")
        col4.metric(label="🛑 Call Wall (Resistenza)", value=f"{oi_metrics['call_wall_strike']:.0f}" if oi_metrics['call_wall_strike'] else "N/A")
        col5.metric(label="📍 Max Pain", value=f"{max_pain_strike:.0f}" if max_pain_strike else "N/A")
        
        st.divider()
        st.subheader("Charts Dashboard (GEX, OI, Volume)")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("#### Profilo GEX")
            fig_gex = create_gex_profile_chart(
                gex_metrics['df_gex_profile'], spot_price, gex_metrics['gamma_switch_point'], selected_expiry_label
            )
            st.plotly_chart(fig_gex, width="stretch", key="summary_gex_chart")
        with col2:
            st.markdown("#### Distribuzione OI")
            fig_oi = create_oi_profile_chart(
                oi_metrics['df_oi_profile'], spot_price, selected_expiry_label
            )
            st.plotly_chart(fig_oi, width="stretch", key="summary_oi_chart")
        with col3:
            st.markdown("#### Distribuzione Volumi")
            fig_vol = create_volume_profile_chart(
                vol_metrics['df_vol_profile'], spot_price, selected_expiry_label
            )
            st.plotly_chart(fig_vol, width="stretch", key="summary_vol_chart")

    # -----------------------------------------------------------------
    # POPOLAMENTO TAB 1: GAMMA ANALYSIS
    # -----------------------------------------------------------------
    with tab_gex:
        st.header(f"Analisi Gamma (GEX) per {selected_expiry_label}")
        col1, col2, col3 = st.columns(3)
        col1.metric(label="Net GEX", value=f"${gex_metrics['total_net_gex'] / 1_000_000_000:.2f} B")
        col2.metric(label="Gamma Switch Point", value=f"{gex_metrics['gamma_switch_point']:.2f}" if gex_metrics['gamma_switch_point'] else "N/A")
        col3.metric(label="Spot-Switch Delta", value=f"{gex_metrics['spot_switch_delta']:.2f}" if gex_metrics['spot_switch_delta'] else "N/A")
        st.plotly_chart(fig_gex, width="stretch", key="gex_tab_chart")

    # -----------------------------------------------------------------
    # POPOLAMENTO TAB 2: SUPPORT/RESISTANCE (OI & Vol)
    # -----------------------------------------------------------------
    with tab_oi_vol:
        st.header(f"Supporti e Resistenze (OI & Volumi) per {selected_expiry_label}")
        
        st.subheader("Metriche Open Interest (Posizionamento)")
        col1, col2 = st.columns(2)
        col1.metric(label="🛡️ Put Wall", value=f"{oi_metrics['put_wall_strike']:.0f}" if oi_metrics['put_wall_strike'] else "N/A", help=f"OI: {oi_metrics['put_wall_oi']:,.0f}")
        col2.metric(label="🛑 Call Wall", value=f"{oi_metrics['call_wall_strike']:.0f}" if oi_metrics['call_wall_strike'] else "N/A", help=f"OI: {oi_metrics['call_wall_oi']:,.0f}")
        st.plotly_chart(fig_oi, width="stretch", key="oi_tab_chart")
        
        st.divider()
        st.subheader("Metriche Volumi (Attività di Giornata)")
        st.plotly_chart(fig_vol, width="stretch", key="vol_tab_chart")
        
        st.divider()
        st.subheader("Analisi Drift (Sintesi e Dettaglio)")
        st.info("La 'Sintesi Drift Volumi' calcola il VWAS (Volume Weighted Average Strike) e lo confronta con lo Spot. Una freccia a destra indica che l'attività odierna è concentrata su strike più alti (bias rialzista); una freccia a sinistra indica un bias ribassista.")
        
        # Grafico Freccia Drift
        fig_drift_arrow = create_drift_arrow_chart(
            activity_metrics['drift_score'], spot_price, selected_expiry_label
        )
        st.plotly_chart(fig_drift_arrow, width="stretch", key="drift_arrow_chart")

        st.markdown("##### Dettaglio Rapporto Vol/OI")
        st.info("Questo grafico mostra gli strike 'caldi'. Un rapporto > 1.0 indica che il volume odierno ha superato l'intero Open Interest esistente, segnalando un'attività insolita.")
        fig_drift_detail = create_activity_ratio_chart(
            activity_metrics['df_activity_profile'], spot_price, selected_expiry_label
        )
        st.plotly_chart(fig_drift_detail, width="stretch", key="drift_detail_chart")
        
    # -----------------------------------------------------------------
    # POPOLAMENTO TAB 3: STATISTICAL MODELS
    # -----------------------------------------------------------------
    with tab_stats:
        st.header(f"Modelli Statistici per {selected_expiry_label}")
        
        st.subheader("Metriche Chiave di Posizionamento e Sentiment")
        col1, col2, col3 = st.columns(3)
        col1.metric(label="📍 Max Pain Strike", value=f"{max_pain_strike:.0f}" if max_pain_strike else "N/A", help="Lo strike che causa la massima perdita per i compratori di opzioni a scadenza.")
        col2.metric(label="P/C Ratio (Open Interest)", value=f"{pc_ratios['pc_oi_ratio']:.3f}", help="Sentiment di posizionamento (Put OI / Call OI). > 1 = Bearish")
        col3.metric(label="P/C Ratio (Volume)", value=f"{pc_ratios['pc_vol_ratio']:.3f}", help="Sentiment di attività (Put Vol / Call Vol). > 1 = Bearish")
        
        st.subheader("Movimento Atteso (Expected Move)")
        em = expected_move
        if em['move']:
            col1, col2, col3 = st.columns(3)
            col1.metric(label="Banda Superiore Attesa", value=f"{em['upper_band']:.2f}")
            col2.metric(label="Banda Inferiore Attesa", value=f"{em['lower_band']:.2f}")
            col3.metric(label="Movimento Atteso (+/-)", value=f"{em['move']:.2f}", help=f"Calcolato con IV ATM: {em['iv_atm']:.2%}")
        else:
            st.warning("Impossibile calcolare l'Expected Move (dati IV ATM mancanti).")

        st.divider()
        st.subheader(f"Grafico Max Pain (Payout Totale a Scadenza)")
        fig_max_pain = create_max_pain_chart(df_payouts, max_pain_strike, selected_expiry_label)
        st.plotly_chart(fig_max_pain, width="stretch", key="max_pain_chart")
        
    # -----------------------------------------------------------------
    # POPOLAMENTO TAB 4: VOLATILITY SURFACE
    # -----------------------------------------------------------------
    with tab_vol_surf:
        st.header("Superficie di Volatilità (Tutte le Scadenze)")
        with st.spinner("Calcolo e interpolazione superficie 3D in corso..."):
            fig_vol_surf = create_volatility_surface_3d(df_processed)
            st.plotly_chart(fig_vol_surf, width="stretch", key="vol_surface_chart")
