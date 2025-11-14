# File: data_module.py
#
# Modulo per il caricamento, parsing e preprocessing dei dati CBOE.
# [CORRETTO] Risolto SyntaxError nel dizionario 'italian_to_english_months'.
# -----------------------------------------------------------------------------

import pandas as pd
import numpy as np
import io
import re
import datetime as dt

def parse_cboe_csv(uploaded_file):
    """
    Esegue il parsing del file CSV CBOE caricato.
    Estrae metadati, pulisce i dati, separa Calls/Puts
    e calcola feature ingegnerizzate (DTE, Moneyness).

    Args:
        uploaded_file: L'oggetto file caricato da st.file_uploader()

    Returns:
        Tuple (df_processed, spot_price, data_timestamp)
        o (None, None, None) in caso di fallimento.
    """
    try:
        # --- 1. Estrazione Metadati e Parsing (Logica Cella 3) ---
        raw_data = uploaded_file.getvalue()
        data_str = raw_data.decode('utf-8')
        lines = data_str.split('\n')

        spot_price_extracted = None
        data_timestamp_extracted = None
        header_row_index = None

        # Estrai Bid/Ask per Spot Price e Timestamp
        for i, line in enumerate(lines[:10]):
            if "Bid:" in line and "Ask:" in line:
                data_timestamp_extracted = line.split(',Bid:')[0].strip().replace('Date: ', '')
                bid_match = re.search(r'Bid:\s*([\d,]+\.?\d*)', line)
                bid = float(bid_match.group(1).replace(',', '')) if bid_match else None
                ask_match = re.search(r'Ask:\s*([\d,]+\.?\d*)', line)
                ask = float(ask_match.group(1).replace(',', '')) if ask_match else None
                if bid and ask:
                    spot_price_extracted = (bid + ask) / 2
            
            # Trova la riga di intestazione
            if "Strike" in line and "Open Interest" in line and "Calls" in line:
                header_row_index = i
        
        if header_row_index is None or spot_price_extracted is None:
            raise Exception("Formato file non valido. Impossibile trovare Header o Spot Price (Bid/Ask).")

        # Carica il CSV usando skiprows (Logica Cella 3 Corretta)
        data_io_csv = io.StringIO(data_str)
        df_options_raw = pd.read_csv(
            data_io_csv, 
            skiprows=header_row_index,
            thousands=','
        )
        
        # Pulisci i nomi delle colonne
        df_options_raw.columns = df_options_raw.columns.str.strip()
        df_options_raw.dropna(how='all', inplace=True)
        df_options_raw.reset_index(drop=True, inplace=True)

        # --- 2. Separazione Calls/Puts (Logica Cella 3 Corretta) ---
        strike_col_index = df_options_raw.columns.get_loc("Strike")
        call_cols = list(df_options_raw.columns[:strike_col_index])
        put_cols = list(df_options_raw.columns[strike_col_index+1:])
        
        # Mappa di rinomina (come da Cella 3)
        call_rename_map = {'Expiration Date': 'Expiration Date', 'Calls': 'Symbol', 'Last Sale': 'Last', 'Net': 'Net', 'Bid': 'Bid', 'Ask': 'Ask', 'Volume': 'Vol', 'IV': 'IV', 'Delta': 'Delta', 'Gamma': 'Gamma', 'Open Interest': 'OI', 'Strike': 'Strike'}
        put_rename_map = {'Strike': 'Strike', 'Expiration Date': 'Expiration Date', 'Puts': 'Symbol', 'Last Sale': 'Last', 'Net': 'Net', 'Bid': 'Bid', 'Ask': 'Ask', 'Volume': 'Vol', 'IV': 'IV', 'Delta': 'Delta', 'Gamma': 'Gamma', 'Open Interest': 'OI'}

        # Estrai Calls
        df_calls = df_options_raw[call_cols + ["Strike"]].copy()
        df_calls.columns = [call_rename_map[c.strip()] for c in df_calls.columns]
        df_calls['Type'] = 'Call'

        # Estrai Puts
        df_puts = df_options_raw[["Strike", "Expiration Date"] + put_cols].copy()
        clean_put_cols = [c.replace('.1', '').strip() for c in df_puts.columns]
        df_puts.columns = [put_rename_map[c] for c in clean_put_cols]
        df_puts['Type'] = 'Put'
        
        # Concatena
        df_options_clean = pd.concat([df_calls, df_puts], ignore_index=True)
        
        # Filtra colonne finali
        cols_to_keep = ['Type', 'Strike', 'Expiration Date', 'Last', 'Bid', 'Ask', 'Vol', 'OI', 'IV', 'Delta', 'Gamma']
        existing_cols_to_keep = [col for col in cols_to_keep if col in df_options_clean.columns]
        df_options_clean = df_options_clean[existing_cols_to_keep]

        # --- 3. Preprocessing e Feature Engineering (Logica Cella 4) ---
        df_processed = df_options_clean.copy()
        
        # --- [INIZIO CORREZIONE] ---
        # Dizionario traduzione (robusto, Cella 4 Corretta)
        italian_to_english_months = {
            'gennaio': 'January', 'febbraio': 'February', 'marzo': 'March', 
            'aprile': 'April', # Rimossa la 'p'
            'maggio': 'May', 'giugno': 'June', 'luglio': 'July', 
            'agosto': 'August', 'settembre': 'September', 'ottobre': 'October', 
            'novembre': 'November', 'dicembre': 'December'
        }
        # --- [FINE CORREZIONE] ---
        
        # Calcola data di analisi
        analysis_date_str = data_timestamp_extracted.split(' alle')[0]
        analysis_date_str_en = analysis_date_str.lower()
        for it, en in italian_to_english_months.items():
            analysis_date_str_en = analysis_date_str_en.replace(it, en)
        
        analysis_date = pd.to_datetime(analysis_date_str_en, format='%d %B %Y')
        
        # Calcola DTE
        df_processed['Expiration Date'] = pd.to_datetime(df_processed['Expiration Date'], format='%a %b %d %Y')
        df_processed['DTE_Days'] = (df_processed['Expiration Date'] - analysis_date).dt.days
        df_processed['DTE_Years'] = df_processed['DTE_Days'] / 365.25
        
        # Calcola Moneyness
        df_processed['Moneyness'] = df_processed['Strike'] / spot_price_extracted
        
        # Filtra dati irrilevanti (OI=0 o scadenze passate)
        df_processed = df_processed[df_processed['OI'] > 0].copy()
        df_processed = df_processed[df_processed['DTE_Days'] >= 0].copy()

        # --- 4. Calcolo GEX Iniziale (Logica Cella 5) ---
        CONTRACT_MULTIPLIER = 100.0
        SPOT = spot_price_extracted
        
        df_processed['GEX_Notional'] = df_processed['Gamma'] * \
                                         df_processed['OI'] * \
                                         CONTRACT_MULTIPLIER * \
                                         (SPOT / 100.0) * \
                                         SPOT
        
        df_processed['GEX_Signed'] = np.where(
            df_processed['Type'] == 'Call',
            df_processed['GEX_Notional'],      
            df_processed['GEX_Notional'] * -1.0 
        )

        print(f"[data_module] Parsing completato. {len(df_processed)} righe processate.")
        
        return df_processed, spot_price_extracted, data_timestamp_extracted

    except Exception as e:
        print(f"[ERRORE in data_module.parse_cboe_csv]: {e}")
        return None, None, None
