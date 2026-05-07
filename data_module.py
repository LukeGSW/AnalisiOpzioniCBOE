# File: data_module.py
#
# Modulo per il caricamento, parsing e preprocessing dei dati CBOE.
# [AGGIORNATO v2] Aggiunto calcolo DEX_Notional e VEX_Notional (Vanna via py_vollib).
# -----------------------------------------------------------------------------

import pandas as pd
import numpy as np
import io
import re
import datetime as dt
import streamlit as st

# --- Import py_vollib per il calcolo del Vanna (BS Analitico) ---
# Gestiamo l'import con un flag per evitare crash se la libreria non è installata.
try:
    from py_vollib.black_scholes.greeks.analytical import vanna as _bsm_vanna
    _PYVOLLIB_AVAILABLE = True
except ImportError:
    _PYVOLLIB_AVAILABLE = False


def _compute_vanna_vectorized(type_series, strike_series, dte_years_series, iv_series, spot):
    """
    Calcola il Vanna per ogni riga del DataFrame usando np.vectorize.

    Il Vanna (dDelta/dSigma) rappresenta la sensitività del Delta
    rispetto a una variazione della Volatilità Implicita.

    Parametri BS utilizzati:
    - flag: 'c' (Call) o 'p' (Put)
    - S: Spot Price
    - K: Strike Price
    - t: DTE in anni (floor a 1/365.25 per evitare t=0)
    - r: Risk-free rate fisso (0.045)
    - sigma: IV in formato decimale (es. 0.20 per 20%)
    """
    RISK_FREE_RATE = 0.045
    MIN_DTE        = 1.0 / 365.25
    MIN_IV         = 0.001  # Filtro per strike illiquidi / IV a zero

    def _single_vanna(option_type, K, t, sigma):
        """Calcolo sicuro del Vanna per una singola opzione. Ritorna 0.0 in caso di errore."""
        try:
            flag  = 'c' if option_type == 'Call' else 'p'
            t_safe     = float(t) if float(t) > MIN_DTE else MIN_DTE
            sigma_safe = float(sigma)
            K_float    = float(K)
            S_float    = float(spot)

            if sigma_safe <= MIN_IV or K_float <= 0 or S_float <= 0:
                return 0.0

            result = _bsm_vanna(flag, S_float, K_float, t_safe, RISK_FREE_RATE, sigma_safe)
            # Sanity check sul risultato (può essere NaN o Inf su strike estremi)
            if not np.isfinite(result):
                return 0.0
            return float(result)
        except Exception:
            return 0.0

    # np.vectorize applica la funzione elemento per elemento (più pulito di apply)
    _vec = np.vectorize(_single_vanna, otypes=[float])
    return _vec(
        type_series.values,
        strike_series.values,
        dte_years_series.values,
        iv_series.values
    )


def parse_cboe_csv(uploaded_file):
    """
    Esegue il parsing del file CSV CBOE caricato.
    Include logiche di fallback e messaggi di errore visibili per il debug.
    [v2] Aggiunge DEX_Notional (Delta) e VEX_Notional (Vanna) al DataFrame finale.
    """
    step = "Inizio"
    try:
        # --- 1. Lettura Raw e Pulizia Header ---
        step = "Lettura File"
        raw_data = uploaded_file.getvalue()
        try:
            data_str = raw_data.decode('utf-8')
        except UnicodeDecodeError:
            data_str = raw_data.decode('latin-1')

        lines = data_str.split('\n')
        header_block = " ".join([line.strip() for line in lines[:15]])

        # --- 2. Estrazione Spot Price ---
        step = "Estrazione Spot Price"
        spot_price_extracted = None

        last_match = re.search(r'Last:\s*([\d,]+\.?\d*)', header_block)
        if last_match:
            try:
                spot_price_extracted = float(last_match.group(1).replace(',', ''))
            except Exception:
                pass

        if spot_price_extracted is None or spot_price_extracted == 0:
            bid_match = re.search(r'Bid:\s*([\d,]+\.?\d*)', header_block)
            ask_match = re.search(r'Ask:\s*([\d,]+\.?\d*)', header_block)
            if bid_match and ask_match:
                try:
                    bid = float(bid_match.group(1).replace(',', ''))
                    ask = float(ask_match.group(1).replace(',', ''))
                    if ask > 0:
                        spot_price_extracted = (bid + ask) / 2
                except Exception:
                    pass

        # --- 3. Estrazione Timestamp ---
        step = "Estrazione Data"
        data_timestamp_extracted = "Data non disponibile"
        analysis_date = pd.Timestamp.now().normalize()

        try:
            date_match = re.search(r'Date:\s*(.*?)(?:,Bid|,Ask|GMT)', header_block)
            if date_match:
                data_timestamp_extracted = date_match.group(1).strip()

            if data_timestamp_extracted != "Data non disponibile":
                date_text = data_timestamp_extracted.split(' alle')[0]
                italian_to_english_months = {
                    'gennaio': 'January', 'febbraio': 'February', 'marzo': 'March',
                    'aprile': 'April', 'maggio': 'May', 'giugno': 'June', 'luglio': 'July',
                    'agosto': 'August', 'settembre': 'September', 'ottobre': 'October',
                    'novembre': 'November', 'dicembre': 'December'
                }
                date_text_en = date_text.lower()
                for it, en in italian_to_english_months.items():
                    date_text_en = date_text_en.replace(it, en)
                analysis_date = pd.to_datetime(date_text_en, format='%d %B %Y')

        except Exception as e:
            st.warning(f"Attenzione: Impossibile leggere la data dal file ('{data_timestamp_extracted}'). Uso data odierna per i calcoli DTE. Errore: {e}")
            analysis_date = pd.Timestamp.now().normalize()

        # --- 4. Caricamento CSV ---
        step = "Ricerca Header CSV"
        header_row_index = None
        for i, line in enumerate(lines):
            if line.strip().startswith("Expiration Date"):
                header_row_index = i
                break

        if header_row_index is None:
            st.error("Errore: Impossibile trovare la riga 'Expiration Date' nel file.")
            return None, None, None

        step = "Parsing CSV Pandas"
        data_io_csv = io.StringIO(data_str)
        df_options_raw = pd.read_csv(
            data_io_csv,
            skiprows=header_row_index,
            thousands=','
        )

        df_options_raw.columns = df_options_raw.columns.str.strip()
        df_options_raw.dropna(how='all', inplace=True)
        df_options_raw.reset_index(drop=True, inplace=True)

        if spot_price_extracted is None or spot_price_extracted == 0:
            if 'Strike' in df_options_raw.columns:
                median_strike = pd.to_numeric(df_options_raw['Strike'], errors='coerce').median()
                spot_price_extracted = median_strike
                st.warning(f"Attenzione: Spot Price non trovato nell'header. Stimato dai dati: {spot_price_extracted}")

        # --- 5. Separazione Calls/Puts ---
        step = "Separazione Call/Put"
        strike_cols = [i for i, c in enumerate(df_options_raw.columns) if c == 'Strike']
        if not strike_cols:
            st.error("Errore: Colonna 'Strike' non trovata nel CSV.")
            return None, None, None
        strike_col_index = strike_cols[0]

        call_cols = list(df_options_raw.columns[:strike_col_index])
        put_cols  = list(df_options_raw.columns[strike_col_index + 1:])

        call_rename_map = {
            'Expiration Date': 'Expiration Date', 'Calls': 'Symbol', 'Last Sale': 'Last',
            'Net': 'Net', 'Bid': 'Bid', 'Ask': 'Ask', 'Volume': 'Vol', 'IV': 'IV',
            'Delta': 'Delta', 'Gamma': 'Gamma', 'Open Interest': 'OI', 'Strike': 'Strike'
        }
        put_rename_map = {
            'Strike': 'Strike', 'Expiration Date': 'Expiration Date', 'Puts': 'Symbol',
            'Last Sale': 'Last', 'Net': 'Net', 'Bid': 'Bid', 'Ask': 'Ask', 'Volume': 'Vol',
            'IV': 'IV', 'Delta': 'Delta', 'Gamma': 'Gamma', 'Open Interest': 'OI'
        }

        df_calls = df_options_raw[call_cols + ["Strike"]].copy()
        df_calls.columns = [call_rename_map.get(c.strip(), c.strip()) for c in df_calls.columns]
        df_calls['Type'] = 'Call'

        df_puts = df_options_raw[["Strike", "Expiration Date"] + put_cols].copy()
        clean_put_cols = [c.replace('.1', '').strip() for c in df_puts.columns]
        df_puts.columns = [put_rename_map.get(c, c) for c in clean_put_cols]
        df_puts['Type'] = 'Put'

        df_options_clean = pd.concat([df_calls, df_puts], ignore_index=True)

        # --- 6. Preprocessing e Conversione Numerica ---
        step = "Conversione Numerica"
        numeric_cols = ['Strike', 'Last', 'Bid', 'Ask', 'Vol', 'OI', 'IV', 'Delta', 'Gamma']
        for col in numeric_cols:
            if col in df_options_clean.columns:
                df_options_clean[col] = pd.to_numeric(df_options_clean[col], errors='coerce').fillna(0)

        df_processed = df_options_clean.copy()

        # DTE
        df_processed['Expiration Date'] = pd.to_datetime(
            df_processed['Expiration Date'], format='%a %b %d %Y', errors='coerce'
        )
        df_processed['DTE_Days']  = (df_processed['Expiration Date'] - analysis_date).dt.days
        df_processed['DTE_Years'] = df_processed['DTE_Days'] / 365.25

        # Moneyness
        if spot_price_extracted and spot_price_extracted > 0:
            df_processed['Moneyness'] = df_processed['Strike'] / spot_price_extracted
        else:
            df_processed['Moneyness'] = 0

        # --- 7. Calcolo GEX ---
        step = "Calcolo GEX"
        CONTRACT_MULTIPLIER = 100.0
        SPOT = spot_price_extracted

        if SPOT and SPOT > 0:
            df_processed['GEX_Notional'] = (
                df_processed['Gamma'] *
                df_processed['OI'] *
                CONTRACT_MULTIPLIER *
                (SPOT / 100.0) *
                SPOT
            )
            df_processed['GEX_Signed'] = np.where(
                df_processed['Type'] == 'Call',
                df_processed['GEX_Notional'],
                df_processed['GEX_Notional'] * -1.0
            )
        else:
            df_processed['GEX_Notional'] = 0.0
            df_processed['GEX_Signed']   = 0.0

        # --- 8. Calcolo DEX (Delta Exposure Nozionale) ---
        # Formula: DEX_Notional = Delta * OI * 100 * Spot
        # Il Delta dal CSV CBOE è già con segno corretto:
        #   Calls: positivo (0 → +1)
        #   Puts:  negativo (-1 → 0)
        step = "Calcolo DEX"
        if SPOT and SPOT > 0:
            df_processed['DEX_Notional'] = (
                df_processed['Delta'] *
                df_processed['OI'] *
                CONTRACT_MULTIPLIER *
                SPOT
            )
        else:
            df_processed['DEX_Notional'] = 0.0

        # --- 9. Calcolo Vanna e VEX (Vanna Exposure Nozionale) ---
        # Formula Vanna: dDelta/dSigma (Black-Scholes Analitico via py_vollib)
        # Formula VEX:   Vanna * OI * 100 * Spot * 0.01
        #   (il moltiplicatore 0.01 rappresenta la sensitività a una variazione
        #    dell'1% della Volatilità Implicita)
        step = "Calcolo VEX (Vanna)"
        if SPOT and SPOT > 0 and _PYVOLLIB_AVAILABLE:
            try:
                vanna_values = _compute_vanna_vectorized(
                    df_processed['Type'],
                    df_processed['Strike'],
                    df_processed['DTE_Years'],
                    df_processed['IV'],
                    SPOT
                )
                df_processed['Vanna']        = vanna_values
                df_processed['VEX_Notional'] = (
                    df_processed['Vanna'] *
                    df_processed['OI'] *
                    CONTRACT_MULTIPLIER *
                    SPOT *
                    0.01
                )
            except Exception as e:
                # Fallback: VEX a zero se py_vollib fallisce globalmente
                st.warning(f"Calcolo VEX parzialmente fallito: {e}. VEX impostato a 0.")
                df_processed['Vanna']        = 0.0
                df_processed['VEX_Notional'] = 0.0
        else:
            if not _PYVOLLIB_AVAILABLE:
                st.warning("py_vollib non disponibile. Installa 'py_vollib>=1.0.1' per abilitare l'analisi VEX.")
            df_processed['Vanna']        = 0.0
            df_processed['VEX_Notional'] = 0.0

        # --- 10. Filtri Finali ---
        original_len = len(df_processed)
        df_processed = df_processed[df_processed['OI'] > 0].copy()

        if df_processed.empty and original_len > 0:
            st.warning("Attenzione: Il filtraggio 'OI > 0' ha rimosso tutte le righe.")

        print(f"[data_module] Parsing OK. Spot: {spot_price_extracted}, Data: {analysis_date}, "
              f"Vanna calcolata: {_PYVOLLIB_AVAILABLE}")

        return df_processed, spot_price_extracted, data_timestamp_extracted

    except Exception as e:
        st.error(f"Errore critico durante il parsing ({step}): {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None, None, None
