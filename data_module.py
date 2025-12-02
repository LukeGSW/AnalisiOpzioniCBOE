# File: data_module.py
#
# Modulo per il caricamento, parsing e preprocessing dei dati CBOE.
# [AGGIORNATO] Ibrido: Logiche custom utente + Fix lettura Header NDX/SPX.
# -----------------------------------------------------------------------------

import pandas as pd
import numpy as np
import io
import re
import datetime as dt

def parse_cboe_csv(uploaded_file):
    """
    Esegue il parsing del file CSV CBOE caricato.
    Gestisce formati di header variabili (NDX/SPX) e mantiene le logiche
    custom di calcolo (GEX, DTE, Traduzione Mesi).

    Args:
        uploaded_file: L'oggetto file caricato da st.file_uploader()

    Returns:
        Tuple (df_processed, spot_price, data_timestamp)
        o (None, None, None) in caso di fallimento.
    """
    try:
        # --- 1. Lettura Raw e Pulizia Header (FIX NDX) ---
        raw_data = uploaded_file.getvalue()
        try:
            data_str = raw_data.decode('utf-8')
        except UnicodeDecodeError:
            data_str = raw_data.decode('latin-1')
            
        lines = data_str.split('\n')
        
        # Uniamo le prime 15 righe per gestire header spezzati (es. Date in NDX)
        header_block = " ".join([line.strip() for line in lines[:15]])

        # --- 2. Estrazione Spot Price e Timestamp (FIX NDX) ---
        spot_price_extracted = None
        data_timestamp_extracted = "Data non disponibile"

        # A. Cerca "Last:" (Prioritario per NDX dove Bid/Ask sono 0)
        last_match = re.search(r'Last:\s*([\d,]+\.?\d*)', header_block)
        if last_match:
            try:
                spot_price_extracted = float(last_match.group(1).replace(',', ''))
            except:
                pass

        # B. Fallback su Bid/Ask (Tipico per SPX)
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
        
        # Controllo sicurezza Spot Price
        if spot_price_extracted is None or spot_price_extracted == 0:
            # Fallback estremo per evitare crash immediati, verrà gestito dopo se necessario
            pass 

        # C. Estrazione Data (Robustezza migliorata per righe spezzate)
        # Cerca la data dopo "Date:" ignorando i newline grazie a header_block
        date_match = re.search(r'Date:\s*(.*?)(?:,Bid|,Ask|GMT)', header_block)
        if date_match:
            data_timestamp_extracted = date_match.group(1).strip()
        else:
            # Fallback vecchia logica se la regex fallisce
            for line in lines[:10]:
                if "Date:" in line and "alle ore" in line:
                    data_timestamp_extracted = line.split(',Bid:')[0].strip().replace('Date: ', '')
                    break

        # --- 3. Caricamento Dati CSV ---
        # Trova l'inizio dei dati (Expiration Date)
        header_row_index = None
        for i, line in enumerate(lines):
            if line.strip().startswith("Expiration Date"):
                header_row_index = i
                break
        
        if header_row_index is None:
            raise Exception("Impossibile trovare la riga di intestazione 'Expiration Date'.")

        data_io_csv = io.StringIO(data_str)
        df_options_raw = pd.read_csv(
            data_io_csv, 
            skiprows=header_row_index,
            thousands=',' # Gestisce le migliaia direttamente nel parsing
        )
        
        # Pulisci i nomi delle colonne
        df_options_raw.columns = df_options_raw.columns.str.strip()
        df_options_raw.dropna(how='all', inplace=True)
        df_options_raw.reset_index(drop=True, inplace=True)

        # Se lo spot price è ancora nullo, prova a stimarlo (Safety net)
        if spot_price_extracted is None or spot_price_extracted == 0:
             if 'Strike' in df_options_raw.columns:
                 spot_price_extracted = df_options_raw['Strike'].median()
                 print(f"[WARN] Spot price non trovato nell'header. Usata mediana Strike: {spot_price_extracted}")

        # --- 4. Separazione Calls/Puts (Logica Utente Mantenuta) ---
        try:
            strike_col_index = df_options_raw.columns.get_loc("Strike")
        except KeyError:
            # Gestione caso colonne duplicate (CBOE a volte le ha)
            # Se ci sono più colonne 'Strike', prendiamo la prima
            strike_cols = [i for i, c in enumerate(df_options_raw.columns) if c == 'Strike']
            if strike_cols:
                strike_col_index = strike_cols[0]
            else:
                raise Exception("Colonna 'Strike' non trovata.")

        call_cols = list(df_options_raw.columns[:strike_col_index])
        put_cols = list(df_options_raw.columns[strike_col_index+1:])
        
        # Mappa di rinomina
        call_rename_map = {'Expiration Date': 'Expiration Date', 'Calls': 'Symbol', 'Last Sale': 'Last', 'Net': 'Net', 'Bid': 'Bid', 'Ask': 'Ask', 'Volume': 'Vol', 'IV': 'IV', 'Delta': 'Delta', 'Gamma': 'Gamma', 'Open Interest': 'OI', 'Strike': 'Strike'}
        put_rename_map = {'Strike': 'Strike', 'Expiration Date': 'Expiration Date', 'Puts': 'Symbol', 'Last Sale': 'Last', 'Net': 'Net', 'Bid': 'Bid', 'Ask': 'Ask', 'Volume': 'Vol', 'IV': 'IV', 'Delta': 'Delta', 'Gamma': 'Gamma', 'Open Interest': 'OI'}

        # Estrai Calls
        df_calls = df_options_raw[call_cols + ["Strike"]].copy()
        # Rinomina sicura: se una colonna non è nella mappa, lasciala originale
        df_calls.columns = [call_rename_map.get(c.strip(), c.strip()) for c in df_calls.columns]
        df_calls['Type'] = 'Call'

        # Estrai Puts
        df_puts = df_options_raw[["Strike", "Expiration Date"] + put_cols].copy()
        clean_put_cols = [c.replace('.1', '').strip() for c in df_puts.columns]
        df_puts.columns = [put_rename_map.get(c, c) for c in clean_put_cols]
        df_puts['Type'] = 'Put'
        
        # Concatena
        df_options_clean = pd.concat([df_calls, df_puts], ignore_index=True)
        
        # Filtra colonne finali
        cols_to_keep = ['Type', 'Strike', 'Expiration Date', 'Last', 'Bid', 'Ask', 'Vol', 'OI', 'IV', 'Delta', 'Gamma']
        existing_cols_to_keep = [col for col in cols_to_keep if col in df_options_clean.columns]
        df_options_clean = df_options_clean[existing_cols_to_keep]

        # --- 5. Preprocessing e Feature Engineering (Logica Utente Mantenuta) ---
        df_processed = df_options_clean.copy()
        
        # Gestione Tipi Numerici (Cruciale per calcoli successivi)
        numeric_cols = ['Strike', 'Last', 'Bid', 'Ask', 'Vol', 'OI', 'IV', 'Delta', 'Gamma']
        for col in numeric_cols:
            if col in df_processed.columns:
                df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce').fillna(0)

        # Dizionario traduzione mesi (Logica Utente)
        italian_to_english_months = {
            'gennaio': 'January', 'febbraio': 'February', 'marzo': 'March', 
            'aprile': 'April', 'maggio': 'May', 'giugno': 'June', 'luglio': 'July', 
            'agosto': 'August', 'settembre': 'September', 'ottobre': 'October', 
            'novembre': 'November', 'dicembre': 'December'
        }
        
        # Calcola data di analisi (Gestione data italiana)
        try:
            analysis_date_str = data_timestamp_extracted.split(' alle')[0]
            analysis_date_str_en = analysis_date_str.lower()
            for it, en in italian_to_english_months.items():
                analysis_date_str_en = analysis_date_str_en.replace(it, en)
            
            analysis_date = pd.to_datetime(analysis_date_str_en, format='%d %B %Y')
        except:
            # Fallback se il parsing data fallisce: usa oggi
            analysis_date = pd.Timestamp.now().normalize()
        
        # Calcola DTE
        df_processed['Expiration Date'] = pd.to_datetime(df_processed['Expiration Date'], format='%a %b %d %Y', errors='coerce')
        df_processed['DTE_Days'] = (df_processed['Expiration Date'] - analysis_date).dt.days
        df_processed['DTE_Years'] = df_processed['DTE_Days'] / 365.25
        
        # Calcola Moneyness
        if spot_price_extracted and spot_price_extracted > 0:
            df_processed['Moneyness'] = df_processed['Strike'] / spot_price_extracted
        else:
             df_processed['Moneyness'] = 0
        
        # Filtra dati irrilevanti (OI=0 o scadenze passate)
        df_processed = df_processed[df_processed['OI'] > 0].copy()
        df_processed = df_processed[df_processed['DTE_Days'] >= 0].copy()

        # --- 6. Calcolo GEX Iniziale (Logica Utente Mantenuta) ---
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

        print(f"[data_module] Parsing completato. {len(df_processed)} righe processate. Spot: {spot_price_extracted}")
        
        return df_processed, spot_price_extracted, data_timestamp_extracted

    except Exception as e:
        print(f"[ERRORE in data_module.parse_cboe_csv]: {e}")
        # Ritorna None per gestire l'errore nell'interfaccia
        return None, None, None
