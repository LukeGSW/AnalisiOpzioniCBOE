# File: calculations_module.py
#
# [VERSIONE OTTIMIZZATA]
# - calculate_gex_metrics: Aggiunto ordinamento e logica "Closest Flip to Spot".
# - Altre funzioni: Validate e confermate.
# -----------------------------------------------------------------------------

import pandas as pd
import numpy as np

def calculate_gex_metrics(df_selected_expiry, spot_price):
    """
    Calcola le metriche GEX per una singola scadenza.
    Miglioramento: Trova il Gamma Switch Point più vicino al prezzo attuale.
    """
    # Raggruppa per Strike e somma il GEX Signed
    df_gex_strike = df_selected_expiry.groupby('Strike')['GEX_Signed'].sum().reset_index()
    df_gex_strike.rename(columns={'GEX_Signed': 'Net_GEX'}, inplace=True)
    
    # IMPORTANTE: Ordina per Strike per garantire interpolazione corretta
    df_gex_strike = df_gex_strike.sort_values('Strike').reset_index(drop=True)
    
    total_net_gex = df_gex_strike['Net_GEX'].sum()
    gamma_switch_local = None
    spot_delta = None
    
    try:
        if not df_gex_strike.empty and len(df_gex_strike) > 1:
            # Identifica i punti dove il segno cambia (Zero Crossing)
            # signs sarà un array di -1, 0, 1
            signs = np.sign(df_gex_strike['Net_GEX'])
            
            # Trova dove il segno corrente è diverso dal prossimo (e non sono NaN)
            sign_change = (signs != signs.shift(-1)) & (signs.shift(-1).notna())
            
            # Indici dei punti PRIMA del cambio di segno
            flip_indices = df_gex_strike.index[sign_change]
            
            candidates = []
            
            for idx in flip_indices:
                # Prendi i due punti a cavallo dello zero
                row_curr = df_gex_strike.iloc[idx]
                row_next = df_gex_strike.iloc[idx+1]
                
                x0, y0 = row_curr['Strike'], row_curr['Net_GEX']
                x1, y1 = row_next['Strike'], row_next['Net_GEX']
                
                # Interpolazione Lineare per trovare Strike esatto dove GEX = 0
                if y1 - y0 != 0: # Evita divisione per zero
                    zero_cross = x0 - (y0 * (x1 - x0) / (y1 - y0))
                    candidates.append(zero_cross)
            
            if candidates:
                # SELEZIONE INTELLIGENTE:
                # Tra tutti i punti di inversione (può essercene più di uno),
                # scegli quello più vicino allo Spot Price attuale.
                gamma_switch_local = min(candidates, key=lambda x: abs(x - spot_price))
                spot_delta = spot_price - gamma_switch_local
            else:
                # Se non ci sono cambi di segno (tutto positivo o tutto negativo)
                gamma_switch_local = None
                spot_delta = None

    except Exception as e:
        print(f"[Errore Calcolo Switch GEX]: {e}")
        pass 

    return {
        'df_gex_profile': df_gex_strike, 
        'total_net_gex': total_net_gex,
        'gamma_switch_point': gamma_switch_local, 
        'spot_switch_delta': spot_delta
    }

def calculate_oi_walls(df_selected_expiry, spot_price):
    """Calcola i Put/Call Walls per una singola scadenza."""
    
    range_lower = spot_price * 0.75
    range_upper = spot_price * 1.25
    df_oi_relevant = df_selected_expiry[
        (df_selected_expiry['Strike'] >= range_lower) & (df_selected_expiry['Strike'] <= range_upper)
    ]

    oi_puts_support = df_oi_relevant[(df_oi_relevant['Type'] == 'Put') & (df_oi_relevant['Strike'] <= spot_price)]
    put_wall_strike, max_put_oi = (None, 0)
    if not oi_puts_support.empty:
        # Trova lo strike con max OI tra le Put sotto il prezzo
        idx_max = oi_puts_support['OI'].idxmax()
        put_wall_strike = oi_puts_support.loc[idx_max]['Strike']
        max_put_oi = oi_puts_support['OI'].max()

    oi_calls_res = df_oi_relevant[(df_oi_relevant['Type'] == 'Call') & (df_oi_relevant['Strike'] >= spot_price)]
    call_wall_strike, max_call_oi = (None, 0)
    if not oi_calls_res.empty:
        # Trova lo strike con max OI tra le Call sopra il prezzo
        idx_max = oi_calls_res['OI'].idxmax()
        call_wall_strike = oi_calls_res.loc[idx_max]['Strike']
        max_call_oi = oi_calls_res['OI'].max()
        
    oi_calls_grouped = df_oi_relevant[df_oi_relevant['Type'] == 'Call'].groupby('Strike')['OI'].sum()
    oi_puts_grouped = df_oi_relevant[df_oi_relevant['Type'] == 'Put'].groupby('Strike')['OI'].sum()
    df_oi_profile = pd.DataFrame({'Calls_OI': oi_calls_grouped, 'Puts_OI': oi_puts_grouped}).fillna(0).reset_index()
    df_oi_profile['Puts_OI_Neg'] = df_oi_profile['Puts_OI'] * -1.0

    return {
        'df_oi_profile': df_oi_profile, 'put_wall_strike': put_wall_strike,
        'put_wall_oi': max_put_oi, 'call_wall_strike': call_wall_strike, 'call_wall_oi': max_call_oi
    }

def calculate_max_pain(df_selected_expiry):
    """Calcola lo strike Max Pain per la scadenza selezionata."""
    
    strikes = sorted(df_selected_expiry['Strike'].unique())
    calls_oi = df_selected_expiry[df_selected_expiry['Type'] == 'Call'].set_index('Strike')['OI']
    puts_oi = df_selected_expiry[df_selected_expiry['Type'] == 'Put'].set_index('Strike')['OI']
    total_payout_list = []
    
    # Ottimizzazione: vettorizzazione possibile ma il loop è abbastanza veloce per singola scadenza
    for expiry_price in strikes:
        call_intrinsic = (expiry_price - calls_oi.index).to_numpy().clip(min=0)
        call_payout = (call_intrinsic * calls_oi).sum()
        put_intrinsic = (puts_oi.index - expiry_price).to_numpy().clip(min=0)
        put_payout = (put_intrinsic * puts_oi).sum()
        total_payout_list.append({'Strike': expiry_price, 'Total_Payout': call_payout + put_payout})

    if not total_payout_list: return None, pd.DataFrame()
    df_payouts = pd.DataFrame(total_payout_list)
    max_pain_strike = df_payouts.loc[df_payouts['Total_Payout'].idxmin()]['Strike']
    return max_pain_strike, df_payouts

def calculate_pc_ratios(df_selected_expiry):
    """Calcola i Put/Call Ratios per OI e Volume."""
    total_put_oi = df_selected_expiry[df_selected_expiry['Type'] == 'Put']['OI'].sum()
    total_call_oi = df_selected_expiry[df_selected_expiry['Type'] == 'Call']['OI'].sum()
    pc_oi_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else np.nan
    total_put_vol = df_selected_expiry[df_selected_expiry['Type'] == 'Put']['Vol'].sum()
    total_call_vol = df_selected_expiry[df_selected_expiry['Type'] == 'Call']['Vol'].sum()
    pc_vol_ratio = total_put_vol / total_call_vol if total_call_vol > 0 else np.nan
    return {'pc_oi_ratio': pc_oi_ratio, 'pc_vol_ratio': pc_vol_ratio}

def calculate_expected_move(df_selected_expiry, spot_price):
    """Calcola il movimento atteso (Expected Move) basato sulla IV ATM."""
    try:
        # Trova lo strike più vicino allo spot
        atm_strike_index = (df_selected_expiry['Strike'] - spot_price).abs().idxmin()
        atm_strike_val = df_selected_expiry.loc[atm_strike_index]['Strike']
        
        # Filtra per strike ATM
        df_atm = df_selected_expiry[df_selected_expiry['Strike'] == atm_strike_val]
        
        # Media IV se ci sono più opzioni (es. call/put) allo stesso strike
        iv_atm = df_atm['IV'].mean()
        dte_years = df_atm['DTE_Years'].iloc[0]
        
        if dte_years <= 0: dte_years = 1 / 365.25 # Evita radice di zero
        
        move = spot_price * iv_atm * np.sqrt(dte_years)
        return {'move': move, 'upper_band': spot_price + move, 'lower_band': spot_price - move, 'iv_atm': iv_atm}
    except Exception as e:
        print(f"[Errore Calcolo Expected Move]: {e}")
        return {'move': None, 'upper_band': None, 'lower_band': None, 'iv_atm': None}

def calculate_volume_profile(df_selected_expiry, spot_price):
    """Prepara il DataFrame per il grafico bidirezionale dei Volumi."""
    range_lower = spot_price * 0.75
    range_upper = spot_price * 1.25
    df_vol_relevant = df_selected_expiry[
        (df_selected_expiry['Strike'] >= range_lower) & (df_selected_expiry['Strike'] <= range_upper)
    ]
    vol_calls_grouped = df_vol_relevant[df_vol_relevant['Type'] == 'Call'].groupby('Strike')['Vol'].sum()
    vol_puts_grouped = df_vol_relevant[df_vol_relevant['Type'] == 'Put'].groupby('Strike')['Vol'].sum()
    df_vol_profile = pd.DataFrame({'Calls_Vol': vol_calls_grouped, 'Puts_Vol': vol_puts_grouped}).fillna(0).reset_index()
    df_vol_profile['Puts_Vol_Neg'] = df_vol_profile['Puts_Vol'] * -1.0
    return {'df_vol_profile': df_vol_profile}

def calculate_activity_ratio(df_selected_expiry, spot_price):
    """
    Calcola il rapporto Vol/OI e un Drift Score.
    Drift Score = VWAS (Volume Weighted Average Strike) - Spot Price.
    """
    range_lower = spot_price * 0.75
    range_upper = spot_price * 1.25
    df_relevant = df_selected_expiry[
        (df_selected_expiry['Strike'] >= range_lower) &
        (df_selected_expiry['Strike'] <= range_upper)
    ]
    
    df_grouped = df_relevant.groupby(['Strike', 'Type'])[['OI', 'Vol']].sum().unstack(fill_value=0)
    
    df_profile = pd.DataFrame(index=df_grouped.index)
    df_profile['Call_OI'] = df_grouped[('OI', 'Call')]
    df_profile['Call_Vol'] = df_grouped[('Vol', 'Call')]
    df_profile['Put_OI'] = df_grouped[('OI', 'Put')]
    df_profile['Put_Vol'] = df_grouped[('Vol', 'Put')]
    
    # Activity Ratio: Volume / (OI + 1) per evitare divisione per zero
    df_profile['Call_Activity_Ratio'] = df_profile['Call_Vol'] / (df_profile['Call_OI'] + 1)
    df_profile['Put_Activity_Ratio'] = df_profile['Put_Vol'] / (df_profile['Put_OI'] + 1)
    
    df_profile['Put_Activity_Ratio_Neg'] = df_profile['Put_Activity_Ratio'] * -1.0
    
    # --- CALCOLO DRIFT SCORE (VWAS) ---
    drift_score = 0
    total_relevant_volume = df_relevant['Vol'].sum()

    if total_relevant_volume > 0:
        # Calcolo VWAS Globale (Call + Put)
        # Formula: Somma(Strike * Volume) / Somma(Volume)
        
        # Facciamo una groupby solo per Strike per sommare Call+Put vol allo stesso strike
        vol_by_strike = df_relevant.groupby('Strike')['Vol'].sum()
        
        vwas = (vol_by_strike.index * vol_by_strike).sum() / vol_by_strike.sum()
        drift_score = vwas # Restituiamo il valore assoluto del VWAS
        
    else:
        drift_score = spot_price 
            
    return {
        'df_activity_profile': df_profile.reset_index(),
        'drift_score': drift_score
    }
