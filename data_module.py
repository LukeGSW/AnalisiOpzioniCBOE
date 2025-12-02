# File: data_module.py
#
# Modulo per il caricamento, parsing e preprocessing dei dati CBOE.
# [AGGIORNATO] Versione con DEBUG: Mostra gli errori a video e usa fallback per la data.
# -----------------------------------------------------------------------------

import pandas as pd
import numpy as np
import io
import re
import datetime as dt
import streamlit as st  # Aggiunto per mostrare errori direttamente nell'app

def parse_cboe_csv(uploaded_file):
    """
    Esegue il parsing del file CSV CBOE caricato.
    Include logiche di fallback e messaggi di errore visibili per il debug.
    """
    # Inizializziamo variabili chiave per il debug
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
        
        # Uniamo le prime 15 righe per gestire header spezzati
        header_block = " ".join([line.strip() for line in lines[:15]])

        # --- 2. Estrazione Spot Price ---
        step = "Estrazione Spot Price"
        spot_price_extracted = None
        
        # A. Cerca "Last:" (NDX)
        last_match = re.search(r'Last:\s*([\d,]+\.?\d*)', header_block)
        if last_match:
            try:
                spot_price_extracted = float(last_match.group(1).replace(',', ''))
            except:
                pass

        # B. Fallback su Bid/Ask (SPX)
        if spot_price_extracted is None or spot_price_extracted == 0:
            bid_match = re.search(r'Bid:\s*([\d,]+\.?\d*)', header_block)
            ask_match = re.search(r'Ask:\s*([\d,]+\.?\d*)', header_block)
            if bid_match and ask_match:
                try:
                    bid = float(bid_match.group(1).replace(',', ''))
                    ask = float(ask_match.group(1).replace(',', ''))
                    if ask > 0:
                        spot_price_extracted = (bid + ask) / 2
                except:
                    pass

        # --- 3. Estrazione Timestamp (Con Fallback Sicuro) ---
        step = "Estrazione Data"
        data_timestamp_extracted = "Data non disponibile"
        analysis_date = pd.Timestamp.now().normalize() # Valore di default: Oggi

        try:
            # Tenta di estrarre la stringa della data
            date_match = re.search(r'Date:\s*(.*?)(?:,Bid|,Ask|GMT)', header_block)
            if date_match:
                data_timestamp_extracted = date_match.group(1).strip()
            
            # Parsing della data italiana
            if data_timestamp_extracted != "Data non disponibile":
                # Pulisce la stringa (rimuove parte oraria se presente con 'alle')
                date_text = data_timestamp_extracted.split(' alle')[0]
                
                # Mappa mesi
                italian_to_english_months = {
                    'gennaio': 'January', 'febbraio': 'February', 'marzo': 'March', 
                    'aprile': 'April', 'maggio': 'May', 'giugno': 'June', 'luglio': 'July', 
                    'agosto': 'August', 'settembre': 'September', 'ottobre': 'October', 
                    'novembre': 'November', 'dicembre': 'December'
                }
                
                date_text_en = date_text.lower()
                for it, en in italian_to_english_months.items():
                    date_text_en = date_text_en.replace(it, en)
                
                # Prova il parsing
                analysis_date = pd.to_datetime(date_text_en, format='%d %B %Y')

        except Exception as e:
            # Se la data fallisce, NON bloccare tutto. Usa oggi e avvisa.
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

        # Fallback Spot Price se ancora nullo (es. NDX senza Last)
        if spot_price_extracted is None or spot_price_extracted == 0:
             if 'Strike' in df_options_raw.columns:
                 # Usa la mediana degli strike come approssimazione grezza per evitare crash
                 median_strike = pd.to_numeric(df_options_raw['Strike'], errors='coerce').median()
                 spot_price_extracted = median_strike
                 st.warning(f"Attenzione: Spot Price non trovato nell'header (Last/Bid/Ask a 0). Stimato dai dati: {spot_price_extracted}")

        # --- 5. Separazione Calls/Puts ---
        step = "Separazione Call/Put"
        # Gestione duplicati colonna Strike
        strike_cols = [i for i, c in enumerate(df_options_raw.columns) if c == 'Strike']
        if not strike_cols:
             st.error("Errore: Colonna 'Strike' non trovata nel CSV.")
             return None, None, None
        strike_col_index = strike_cols[0]

        call_cols = list(df_options_raw.columns[:strike_col_index])
        put_cols = list(df_options_raw.columns[strike_col_index+1:])
        
        # Mappa colonne
        call_rename_map = {'Expiration Date': 'Expiration Date', 'Calls': 'Symbol', 'Last Sale': 'Last', 'Net': 'Net', 'Bid': 'Bid', 'Ask': 'Ask', 'Volume': 'Vol', 'IV': 'IV', 'Delta': 'Delta', 'Gamma': 'Gamma', 'Open Interest': 'OI', 'Strike': 'Strike'}
        put_rename_map = {'Strike': 'Strike', 'Expiration Date': 'Expiration Date', 'Puts': 'Symbol', 'Last Sale': 'Last', 'Net': 'Net', 'Bid': 'Bid', 'Ask': 'Ask', 'Volume': 'Vol', 'IV': 'IV', 'Delta': 'Delta', 'Gamma': 'Gamma', 'Open Interest': 'OI'}

        # Process Calls
        df_calls = df_options_raw[call_cols + ["Strike"]].copy()
        df_calls.columns = [call_rename_map.get(c.strip(), c.strip()) for c in df_calls.columns]
        df_calls['Type'] = 'Call'

        # Process Puts
        df_puts = df_options_raw[["Strike", "Expiration Date"] + put_cols].copy()
        clean_put_cols = [c.replace('.1', '').strip() for c in df_puts.columns]
        df_puts.columns = [put_rename_map.get(c, c) for c in clean_put_cols]
        df_puts['Type'] = 'Put'
        
        df_options_clean = pd.concat([df_calls, df_puts], ignore_index=True)
        
        # --- 6. Preprocessing e Numeri ---
        step = "Conversione Numerica"
        numeric_cols = ['Strike', 'Last', 'Bid', 'Ask', 'Vol', 'OI', 'IV', 'Delta', 'Gamma']
        for col in numeric_cols:
            if col in df_options_clean.columns:
                df_options_clean[col] = pd.to_numeric(df_options_clean[col], errors='coerce').fillna(0)

        df_processed = df_options_clean.copy()

        # DTE
        df_processed['Expiration Date'] = pd.to_datetime(df_processed['Expiration Date'], format='%a %b %d %Y', errors='coerce')
        df_processed['DTE_Days'] = (df_processed['Expiration Date'] - analysis_date).dt.days
        df_processed['DTE_Years'] = df_processed['DTE_Days'] / 365.25
        
        # Moneyness
        if spot_price_extracted and spot_price_extracted > 0:
            df_processed['Moneyness'] = df_processed['Strike'] / spot_price_extracted
        else:
            df_processed['Moneyness'] = 0

        # GEX
        step = "Calcolo GEX"
        CONTRACT_MULTIPLIER = 100.0
        SPOT = spot_price_extracted
        
        if SPOT and SPOT > 0:
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
        else:
            df_processed['GEX_Notional'] = 0
            df_processed['GEX_Signed'] = 0

        # Filtri finali (tolleranti)
        original_len = len(df_processed)
        df_processed = df_processed[df_processed['OI'] > 0].copy()
        
        if df_processed.empty and original_len > 0:
            st.warning("Attenzione: Il filtraggio 'OI > 0' ha rimosso tutte le righe. Verifica che la colonna 'Open Interest' sia popolata nel CSV.")

        # Stampa di successo (solo in console o debug)
        print(f"[data_module] Parsing OK. Spot: {spot_price_extracted}, Data: {analysis_date}")
        
        return df_processed, spot_price_extracted, data_timestamp_extracted

    except Exception as e:
        # QUESTO È IL PUNTO CHIAVE: Mostra l'errore all'utente
        st.error(f"Errore critico durante il parsing ({step}): {str(e)}")
        import traceback
        st.code(traceback.format_exc()) # Mostra il dettaglio tecnico
        return None, None, None
