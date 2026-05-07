# File: app.py
#
# [VERSIONE v2 - CON ANALISI VEX/DEX]
# - Include tutte le funzionalità originali (GEX, OI, Stats, Drift, Volatility Surface).
# - NUOVO: Analisi Delta Exposure (DEX) e Vanna Exposure (VEX) con tab dedicato.
# - AGGIORNATO: Export JSON con nodi 'delta_analysis' e 'vanna_analysis'.
# - AGGIORNATA: Architettura a 6 tab.
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
    calculate_activity_ratio,
    calculate_dex_metrics,        # NUOVO
    calculate_vex_metrics         # NUOVO
)
from visualization_module import (
    create_gex_profile_chart,
    create_oi_profile_chart,
    create_volatility_surface_3d,
    create_volume_profile_chart,
    create_max_pain_chart,
    create_activity_ratio_chart,
    create_drift_arrow_chart,
    create_dex_profile_chart,     # NUOVO
    create_vex_profile_chart      # NUOVO
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

st.title("📊 SPX Options Chain Analyzer")
st.markdown("Powered by **Kriterion Quant**")

# -----------------------------------------------------------------------------
# 2. LOGICA DI CARICAMENTO E CACHING DEI DATI
# -----------------------------------------------------------------------------
@st.cache_data
def load_data(uploaded_file):
    try:
        df_processed, spot_price, data_timestamp = parse_cboe_csv(uploaded_file)
        if df_processed is None:
            return None, None, None
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

    if not expiry_options_map:
        st.error("Nessuna scadenza valida trovata nel file.")
        st.stop()

    df_expiry_oi         = df_processed.groupby('Expiration Date')['OI'].sum()
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
        gex_metrics      = calculate_gex_metrics(df_selected_expiry, spot_price)
        oi_metrics       = calculate_oi_walls(df_selected_expiry, spot_price)
        vol_metrics      = calculate_volume_profile(df_selected_expiry, spot_price)
        activity_metrics = calculate_activity_ratio(df_selected_expiry, spot_price)
        max_pain_strike, df_payouts = calculate_max_pain(df_selected_expiry)
        pc_ratios        = calculate_pc_ratios(df_selected_expiry)
        expected_move    = calculate_expected_move(df_selected_expiry, spot_price)
        # --- NUOVI CALCOLI ---
        dex_metrics      = calculate_dex_metrics(df_selected_expiry, spot_price)
        vex_metrics      = calculate_vex_metrics(df_selected_expiry, spot_price)

    # =========================================================================
    # PREPARAZIONE EXPORT JSON
    # =========================================================================
    export_data = {
        "metadata": {
            "application":         "Kriterion Quant - SPX Analyzer",
            "export_date":         dt.datetime.now().isoformat(),
            "analyzed_expiry":     selected_expiry_label,
            "spot_price":          spot_price,
            "data_timestamp_file": str(data_timestamp)
        },
        "market_summary": {
            "max_pain":               max_pain_strike,
            "put_call_ratio_oi":      pc_ratios['pc_oi_ratio'],
            "put_call_ratio_vol":     pc_ratios['pc_vol_ratio'],
            "expected_move_value":    expected_move['move'],
            "expected_move_range":    [expected_move['lower_band'], expected_move['upper_band']],
            "implied_vol_atm":        expected_move['iv_atm']
        },
        "gamma_analysis": {
            "total_net_gex":         gex_metrics['total_net_gex'],
            "gamma_switch_point":    gex_metrics['gamma_switch_point'],
            "spot_switch_delta":     gex_metrics['spot_switch_delta'],
            "gex_profile_data":      gex_metrics['df_gex_profile'].to_dict(orient='records')
        },
        "delta_analysis": {
            # DEX totale per la scadenza selezionata (somma algebrica di tutte le opzioni)
            "total_net_dex":         dex_metrics['total_net_dex'],
            # Profilo completo per strike: utile all'LLM per identificare i nodi chiave
            "dex_profile_data":      dex_metrics['df_dex_profile'].to_dict(orient='records')
        },
        "vanna_analysis": {
            # VEX totale per la scadenza: sensitività aggregata a una variazione +1% di vol
            "total_net_vex":         vex_metrics['total_net_vex'],
            # Switch Point: strike dove il regime di hedging dei dealers cambia segno
            "vanna_switch_point":    vex_metrics.get('vanna_switch_point', None),
            # Profilo completo per strike
            "vex_profile_data":      vex_metrics['df_vex_profile'].to_dict(orient='records')
        },
        "levels_support_resistance": {
            "put_wall_strike":       oi_metrics['put_wall_strike'],
            "put_wall_oi":           oi_metrics['put_wall_oi'],
            "call_wall_strike":      oi_metrics['call_wall_strike'],
            "call_wall_oi":          oi_metrics['call_wall_oi'],
            "oi_structure":          oi_metrics['df_oi_profile'].to_dict(orient='records')
        },
        "drift_analysis": {
            "vwas_drift_score":      activity_metrics['drift_score'],
            "drift_bias":            "BULLISH" if activity_metrics['drift_score'] > spot_price else "BEARISH",
            "volume_structure":      vol_metrics['df_vol_profile'].to_dict(orient='records'),
            "activity_ratios":       activity_metrics['df_activity_profile'].to_dict(orient='records')
        }
    }

    json_string = json.dumps(export_data, cls=NumpyEncoder, indent=4)

    # --- 3.4. Architettura Tab (6 tab) ---
    tab_summary, tab_gex, tab_vex_dex, tab_oi_vol, tab_stats, tab_vol_surf = st.tabs([
        '📋 Summary',
        '📊 Gamma (GEX)',
        '🧩 Vanna & Delta (VEX/DEX)',
        '🎯 Support/Res (OI & Vol)',
        '📉 Stats',
        '📈 Vol Surface'
    ])

    # -----------------------------------------------------------------
    # SIDEBAR: Download Button
    # -----------------------------------------------------------------
    with st.sidebar:
        st.divider()
        st.header("📥 Export Dati")
        st.download_button(
            label="Scarica JSON Analisi (LLM Ready)",
            data=json_string,
            file_name=f"kriterion_spx_analysis_{selected_expiry_label.split()[0]}.json",
            mime="application/json",
            help="Scarica un file JSON strutturato con tutti i calcoli (GEX, DEX, VEX, OI, Drift, Max Pain) per la scadenza selezionata."
        )

    # =================================================================
    # TAB 0: SUMMARY DASHBOARD
    # =================================================================
    with tab_summary:
        st.header(f"Executive Summary per {selected_expiry_label}")

        st.subheader("Key Metrics Grid (per la scadenza selezionata)")
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        col1.metric(label="Spot Price", value=f"{spot_price:.2f}")
        col2.metric(
            label="Net GEX (Scadenza)",
            value=f"${gex_metrics['total_net_gex'] / 1_000_000_000:.2f} B",
            delta="SHORT γ" if gex_metrics['total_net_gex'] < 0 else "LONG γ",
            delta_color="inverse"
        )
        col3.metric(
            label="Net VEX (Scadenza)",
            value=f"${vex_metrics['total_net_vex'] / 1_000_000:.2f} M",
            help="Sensitività del Delta dei dealers a una variazione +1% della Volatilità Implicita."
        )
        col4.metric(
            label="🛡️ Put Wall (Supporto)",
            value=f"{oi_metrics['put_wall_strike']:.0f}" if oi_metrics['put_wall_strike'] else "N/A"
        )
        col5.metric(
            label="🛑 Call Wall (Resistenza)",
            value=f"{oi_metrics['call_wall_strike']:.0f}" if oi_metrics['call_wall_strike'] else "N/A"
        )
        col6.metric(
            label="📍 Max Pain",
            value=f"{max_pain_strike:.0f}" if max_pain_strike else "N/A"
        )

        st.divider()
        st.subheader("Charts Dashboard (GEX, OI, Volume)")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("#### Profilo GEX")
            fig_gex = create_gex_profile_chart(
                gex_metrics['df_gex_profile'], spot_price,
                gex_metrics['gamma_switch_point'], selected_expiry_label
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

    # =================================================================
    # TAB 1: GAMMA ANALYSIS
    # =================================================================
    with tab_gex:
        st.header(f"Analisi Gamma (GEX) per {selected_expiry_label}")
        col1, col2, col3 = st.columns(3)
        col1.metric(label="Net GEX", value=f"${gex_metrics['total_net_gex'] / 1_000_000_000:.2f} B")
        col2.metric(
            label="Gamma Switch Point",
            value=f"{gex_metrics['gamma_switch_point']:.2f}" if gex_metrics['gamma_switch_point'] else "N/A"
        )
        col3.metric(
            label="Spot-Switch Delta",
            value=f"{gex_metrics['spot_switch_delta']:.2f}" if gex_metrics['spot_switch_delta'] else "N/A"
        )
        # Riusa la figura GEX già costruita nel tab Summary
        fig_gex_tab = create_gex_profile_chart(
            gex_metrics['df_gex_profile'], spot_price,
            gex_metrics['gamma_switch_point'], selected_expiry_label
        )
        st.plotly_chart(fig_gex_tab, width="stretch", key="gex_tab_chart")

    # =================================================================
    # TAB 2: VANNA & DELTA (VEX/DEX) — NUOVO
    # =================================================================
    with tab_vex_dex:
        st.header(f"Analisi Vanna & Delta (VEX/DEX) per {selected_expiry_label}")

        st.info(
            "**DEX (Delta Exposure):** Sensitività netta del portafoglio opzioni al prezzo del sottostante. "
            "Un DEX positivo implica che i dealers sono net-long delta e devono vendere per hedgiarsi. "
            "Un DEX negativo implica acquisti necessari. "
            "**VEX (Vanna Exposure):** Sensitività del Delta a una variazione dell'1% della Volatilità Implicita (dDelta/dSigma). "
            "Il **Vanna Switch Point** indica lo strike dove il regime di hedging legato alla vol cambia segno."
        )

        # --- KPI Row ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            label="Total Net DEX",
            value=f"${dex_metrics['total_net_dex'] / 1_000_000_000:.3f} B",
            help="Somma algebrica della Delta Exposure nozionale per tutti gli strike della scadenza."
        )
        col2.metric(
            label="Total Net VEX",
            value=f"${vex_metrics['total_net_vex'] / 1_000_000:.2f} M",
            help="Sensitività aggregata a una variazione +1% della IV."
        )
        col3.metric(
            label="Vanna Switch Point",
            value=(
                f"{vex_metrics['vanna_switch_point']:.2f}"
                if vex_metrics['vanna_switch_point'] is not None else "N/A"
            ),
            help="Strike interpolato dove il VEX netto cambia segno (zero crossing)."
        )
        col4.metric(
            label="Spot vs Vanna Switch",
            value=(
                f"{spot_price - vex_metrics['vanna_switch_point']:+.2f}"
                if vex_metrics['vanna_switch_point'] is not None else "N/A"
            ),
            help="Differenza tra Spot e Vanna Switch Point. Positivo = spot sopra il nodo di switch."
        )

        st.divider()

        # --- Grafici DEX e VEX affiancati ---
        col_dex, col_vex = st.columns(2)

        with col_dex:
            st.markdown("#### Profilo DEX (Delta Exposure per Strike)")
            st.caption(
                "Verde = Dealers net-long delta (devono vendere) | "
                "Rosso = Dealers net-short delta (devono comprare)"
            )
            fig_dex = create_dex_profile_chart(
                dex_metrics['df_dex_profile'], spot_price, selected_expiry_label
            )
            st.plotly_chart(fig_dex, width="stretch", key="dex_tab_chart")

        with col_vex:
            st.markdown("#### Profilo VEX (Vanna Exposure per Strike)")
            st.caption(
                "Viola = VEX positivo (vol↓ → dealers comprano) | "
                "Arancione = VEX negativo (vol↓ → dealers vendono)"
            )
            fig_vex = create_vex_profile_chart(
                vex_metrics['df_vex_profile'], spot_price,
                vex_metrics['vanna_switch_point'], selected_expiry_label
            )
            st.plotly_chart(fig_vex, width="stretch", key="vex_tab_chart")

        st.divider()
        st.markdown("##### Nota Metodologica")
        st.markdown(
            "Il **Vanna** è calcolato analiticamente tramite il modello Black-Scholes "
            "(libreria `py_vollib`) usando i parametri: IV da CBOE (colonna IV), "
            "Strike dal CSV, DTE in anni, risk-free rate fisso al 4.5%. "
            "Strike con IV ≤ 0.1% o DTE=0 sono esclusi dal calcolo (Vanna = 0). "
            "Il moltiplicatore **0.01** nel VEX nozionale normalizza la sensitività "
            "a una variazione unitaria dell'1% di volatilità implicita."
        )

    # =================================================================
    # TAB 3: SUPPORT/RESISTANCE (OI & Vol)
    # =================================================================
    with tab_oi_vol:
        st.header(f"Supporti e Resistenze (OI & Volumi) per {selected_expiry_label}")

        st.subheader("Metriche Open Interest (Posizionamento)")
        col1, col2 = st.columns(2)
        col1.metric(
            label="🛡️ Put Wall",
            value=f"{oi_metrics['put_wall_strike']:.0f}" if oi_metrics['put_wall_strike'] else "N/A",
            help=f"OI: {oi_metrics['put_wall_oi']:,.0f}"
        )
        col2.metric(
            label="🛑 Call Wall",
            value=f"{oi_metrics['call_wall_strike']:.0f}" if oi_metrics['call_wall_strike'] else "N/A",
            help=f"OI: {oi_metrics['call_wall_oi']:,.0f}"
        )
        fig_oi_tab = create_oi_profile_chart(oi_metrics['df_oi_profile'], spot_price, selected_expiry_label)
        st.plotly_chart(fig_oi_tab, width="stretch", key="oi_tab_chart")

        st.divider()
        st.subheader("Metriche Volumi (Attività di Giornata)")
        fig_vol_tab = create_volume_profile_chart(vol_metrics['df_vol_profile'], spot_price, selected_expiry_label)
        st.plotly_chart(fig_vol_tab, width="stretch", key="vol_tab_chart")

        st.divider()
        st.subheader("Analisi Drift (Sintesi e Dettaglio)")
        st.info(
            "La 'Sintesi Drift Volumi' calcola il VWAS (Volume Weighted Average Strike) "
            "e lo confronta con lo Spot. Una freccia a destra indica bias rialzista; "
            "una freccia a sinistra indica bias ribassista."
        )
        fig_drift_arrow = create_drift_arrow_chart(
            activity_metrics['drift_score'], spot_price, selected_expiry_label
        )
        st.plotly_chart(fig_drift_arrow, width="stretch", key="drift_arrow_chart")

        st.markdown("##### Dettaglio Rapporto Vol/OI")
        st.info(
            "Un rapporto > 1.0 indica che il volume odierno ha superato l'intero Open "
            "Interest esistente, segnalando un'attività insolita."
        )
        fig_drift_detail = create_activity_ratio_chart(
            activity_metrics['df_activity_profile'], spot_price, selected_expiry_label
        )
        st.plotly_chart(fig_drift_detail, width="stretch", key="drift_detail_chart")

    # =================================================================
    # TAB 4: STATISTICAL MODELS
    # =================================================================
    with tab_stats:
        st.header(f"Modelli Statistici per {selected_expiry_label}")

        st.subheader("Metriche Chiave di Posizionamento e Sentiment")
        col1, col2, col3 = st.columns(3)
        col1.metric(
            label="📍 Max Pain Strike",
            value=f"{max_pain_strike:.0f}" if max_pain_strike else "N/A",
            help="Lo strike che causa la massima perdita per i compratori di opzioni a scadenza."
        )
        col2.metric(
            label="P/C Ratio (Open Interest)",
            value=f"{pc_ratios['pc_oi_ratio']:.3f}",
            help="Sentiment di posizionamento (Put OI / Call OI). > 1 = Bearish"
        )
        col3.metric(
            label="P/C Ratio (Volume)",
            value=f"{pc_ratios['pc_vol_ratio']:.3f}",
            help="Sentiment di attività (Put Vol / Call Vol). > 1 = Bearish"
        )

        st.subheader("Movimento Atteso (Expected Move)")
        em = expected_move
        if em['move']:
            col1, col2, col3 = st.columns(3)
            col1.metric(label="Banda Superiore Attesa", value=f"{em['upper_band']:.2f}")
            col2.metric(label="Banda Inferiore Attesa", value=f"{em['lower_band']:.2f}")
            col3.metric(
                label="Movimento Atteso (+/-)",
                value=f"{em['move']:.2f}",
                help=f"Calcolato con IV ATM: {em['iv_atm']:.2%}"
            )
        else:
            st.warning("Impossibile calcolare l'Expected Move (dati IV ATM mancanti).")

        st.divider()
        st.subheader("Grafico Max Pain (Payout Totale a Scadenza)")
        fig_max_pain = create_max_pain_chart(df_payouts, max_pain_strike, selected_expiry_label)
        st.plotly_chart(fig_max_pain, width="stretch", key="max_pain_chart")

    # =================================================================
    # TAB 5: VOLATILITY SURFACE
    # =================================================================
    with tab_vol_surf:
        st.header("Superficie di Volatilità (Tutte le Scadenze)")
        with st.spinner("Calcolo e interpolazione superficie 3D in corso..."):
            fig_vol_surf = create_volatility_surface_3d(df_processed)
            st.plotly_chart(fig_vol_surf, width="stretch", key="vol_surface_chart")
