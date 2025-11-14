# File: calculations_module.py
#
# Modulo per i calcoli quantitativi.
# Contiene la logica per GEX, OI Walls, e altre metriche.
# Come da Sezione 3.2 del documento di progettazione.
# -----------------------------------------------------------------------------

import pandas as pd
import numpy as np

def calculate_gex_metrics(df_selected_expiry, spot_price):
    """
    Calcola le metriche GEX per una *singola* scadenza.
    
    Args:
        df_selected_expiry (pd.DataFrame): DataFrame già filtrato per una scadenza.
        spot_price (float): Prezzo spot di riferimento.

    Returns:
        dict: Un dizionario contenente le metriche GEX.
    """
    
    # Aggrega GEX per Strike (logica da Cella 13)
    df_gex_strike = df_selected_expiry.groupby('Strike')['GEX_Signed'].sum().reset_index()
    df_gex_strike.rename(columns={'GEX_Signed': 'Net_GEX'}, inplace=True)

    # 1. Calcola GEX Netto Totale
    total_net_gex = df_gex_strike['Net_GEX'].sum()
    
    # 2. Calcola Gamma Switch Point (Logica Cella 13)
    gamma_switch_local = None
    spot_delta = None
    
    try:
        if not df_gex_strike.empty:
            primo_pos_df = df_gex_strike[df_gex_strike['Net_GEX'] > 0]
            ultimo_neg_df = df_gex_strike[df_gex_strike['Net_GEX'] < 0]
            
            if not primo_pos_df.empty and not ultimo_neg_df.empty:
                primo_pos = primo_pos_df.iloc[0]
                ultimo_neg_candidates = ultimo_neg_df[ultimo_neg_df['Strike'] < primo_pos['Strike']]
                
                if not ultimo_neg_candidates.empty:
                    ultimo_neg = ultimo_neg_candidates.iloc[-1]
                    
                    x0, y0 = ultimo_neg['Strike'], ultimo_neg['Net_GEX']
                    x1, y1 = primo_pos['Strike'], primo_pos['Net_GEX']
                    
                    # Interpolazione
                    gamma_switch_local = x0 - (y0 * (x1 - x0) / (y1 - y0))
                    spot_delta = spot_price - gamma_switch_local
                    
    except Exception as e:
        print(f"[Errore Calcolo Switch GEX]: {e}")
        pass # Lascia i valori None

    return {
        'df_gex_profile': df_gex_strike, # Dataframe per il grafico
        'total_net_gex': total_net_gex,
        'gamma_switch_point': gamma_switch_local,
        'spot_switch_delta': spot_delta
    }

def calculate_oi_walls(df_selected_expiry, spot_price):
    """
    Calcola i Put/Call Walls per una *singola* scadenza.
    Usa la logica S/R "rilevante" (vicino allo spot).

    Args:
        df_selected_expiry (pd.DataFrame): DataFrame già filtrato per una scadenza.
        spot_price (float): Prezzo spot di riferimento.

    Returns:
        dict: Un dizionario contenente le metriche OI.
    """
    
    # Filtra per range di rilevanza (Logica Cella 13)
    range_lower = spot_price * 0.75
    range_upper = spot_price * 1.25
    
    df_oi_relevant = df_selected_expiry[
        (df_selected_expiry['Strike'] >= range_lower) &
        (df_selected_expiry['Strike'] <= range_upper)
    ]

    # 1. Calcola Put Wall (Supporto)
    oi_puts_support = df_oi_relevant[
        (df_oi_relevant['Type'] == 'Put') & 
        (df_oi_relevant['Strike'] <= spot_price)
    ]
    put_wall_strike, max_put_oi = (None, 0)
    if not oi_puts_support.empty:
        put_wall_strike = oi_puts_support.loc[oi_puts_support['OI'].idxmax()]['Strike']
        max_put_oi = oi_puts_support['OI'].max()

    # 2. Calcola Call Wall (Resistenza)
    oi_calls_res = df_oi_relevant[
        (df_oi_relevant['Type'] == 'Call') & 
        (df_oi_relevant['Strike'] >= spot_price)
    ]
    call_wall_strike, max_call_oi = (None, 0)
    if not oi_calls_res.empty:
        call_wall_strike = oi_calls_res.loc[oi_calls_res['OI'].idxmax()]['Strike']
        max_call_oi = oi_calls_res['OI'].max()
        
    # 3. Aggrega dati per il grafico bidirezionale
    oi_calls_grouped = df_oi_relevant[df_oi_relevant['Type'] == 'Call'].groupby('Strike')['OI'].sum()
    oi_puts_grouped = df_oi_relevant[df_oi_relevant['Type'] == 'Put'].groupby('Strike')['OI'].sum()
    
    df_oi_profile = pd.DataFrame({
        'Calls_OI': oi_calls_grouped, 
        'Puts_OI': oi_puts_grouped
    }).fillna(0).reset_index()
    
    df_oi_profile['Puts_OI_Neg'] = df_oi_profile['Puts_OI'] * -1.0

    return {
        'df_oi_profile': df_oi_profile, # Dataframe per il grafico
        'put_wall_strike': put_wall_strike,
        'put_wall_oi': max_put_oi,
        'call_wall_strike': call_wall_strike,
        'call_wall_oi': max_call_oi
    }
