# File: calculations_module.py
#
# [CORRETTO 2]
# 1. Risolto 'TypeError' in 'calculate_max_pain'.
# 2. Sostituito 'clip(lower=0)' (sintassi Pandas)
#    con 'clip(min=0)' (sintassi NumPy).
# -----------------------------------------------------------------------------

import pandas as pd
import numpy as np

def calculate_gex_metrics(df_selected_expiry, spot_price):
    """Calcola le metriche GEX per una *singola* scadenza."""
    
    df_gex_strike = df_selected_expiry.groupby('Strike')['GEX_Signed'].sum().reset_index()
    df_gex_strike.rename(columns={'GEX_Signed': 'Net_GEX'}, inplace=True)
    total_net_gex = df_gex_strike['Net_GEX'].sum()
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
                    gamma_switch_local = x0 - (y0 * (x1 - x0) / (y1 - y0))
                    spot_delta = spot_price - gamma_switch_local
    except Exception as e:
        print(f"[Errore Calcolo Switch GEX]: {e}")
        pass 

    return {
        'df_gex_profile': df_gex_strike, 'total_net_gex': total_net_gex,
        'gamma_switch_point': gamma_switch_local, 'spot_switch_delta': spot_delta
    }

def calculate_oi_walls(df_selected_expiry, spot_price):
    """Calcola i Put/Call Walls per una *singola* scadenza."""
    
    range_lower = spot_price * 0.75
    range_upper = spot_price * 1.25
    df_oi_relevant = df_selected_expiry[
        (df_selected_expiry['Strike'] >= range_lower) & (df_selected_expiry['Strike'] <= range_upper)
    ]

    oi_puts_support = df_oi_relevant[(df_oi_relevant['Type'] == 'Put') & (df_oi_relevant['Strike'] <= spot_price)]
    put_wall_strike, max_put_oi = (None, 0)
    if not oi_puts_support.empty:
        put_wall_strike = oi_puts_support.loc[oi_puts_support['OI'].idxmax()]['Strike']
        max_put_oi = oi_puts_support['OI'].max()

    oi_calls_res = df_oi_relevant[(df_oi_relevant['Type'] == 'Call') & (df_oi_relevant['Strike'] >= spot_price)]
    call_wall_strike, max_call_oi = (None, 0)
    if not oi_calls_res.empty:
        call_wall_strike = oi_calls_res.loc[oi_calls_res['OI'].idxmax()]['Strike']
        max_call_oi = oi_calls_res['OI'].max()
        
    oi_calls_grouped = df_oi_relevant[df_oi_relevant['Type'] == 'Call'].groupby('Strike')['OI'].sum()
    oi_puts_grouped = df_oi_relevant[df_oi_relevant['Type'] == 'Put'].groupby('Strike')['OI'].sum()
    df_oi_profile = pd.DataFrame({'Calls_OI': oi_calls_grouped, 'Puts_OI': oi_puts_grouped}).fillna(0).reset_index()
    df_oi_profile['Puts_OI_Neg'] = df_oi_profile['Puts_OI'] * -1.0

    return {
        'df_oi_profile': df_oi_profile, 'put_wall_strike': put_wall_strike,
        'put_wall_oi': max_put_oi, 'call_wall_strike': call_wall_strike, 'call_wall_oi': max_call_oi
    }

# -----------------------------------------------------------------------------
# FUNZIONI PER TAB STATISTICAL MODELS
# -----------------------------------------------------------------------------

def calculate_max_pain(df_selected_expiry):
    """
    Calcola lo strike "Max Pain" per la scadenza selezionata.
    (Come da Sezione 4.1 del documento di progetto)
    """
    
    strikes = sorted(df_selected_expiry['Strike'].unique())
    
    calls_oi = df_selected_expiry[df_selected_expiry['Type'] == 'Call'].set_index('Strike')['OI']
    puts_oi = df_selected_expiry[df_selected_expiry['Type'] == 'Put'].set_index('Strike')['OI']
    
    total_payout_list = []
    
    for expiry_price in strikes:
        
        # --- [INIZIO CORREZIONE] ---
        # Payout per le Calls (compratori)
        call_intrinsic = (expiry_price - calls_oi.index).to_numpy().clip(min=0)
        call_payout = (call_intrinsic * calls_oi).sum()
        
        # Payout per le Puts (compratori)
        put_intrinsic = (puts_oi.index - expiry_price).to_numpy().clip(min=0)
        put_payout = (put_intrinsic * puts_oi).sum()
        # --- [FINE CORREZIONE] ---
        
        total_payout_list.append({
            'Strike': expiry_price,
            'Total_Payout': call_payout + put_payout
        })

    if not total_payout_list:
        return None, pd.DataFrame() # Nessun dato

    df_payouts = pd.DataFrame(total_payout_list)
    max_pain_strike = df_payouts.loc[df_payouts['Total_Payout'].idxmin()]['Strike']
    
    return max_pain_strike, df_payouts


def calculate_pc_ratios(df_selected_expiry):
    """
    Calcola i Put/Call Ratios per OI e Volume.
    """
    total_put_oi = df_selected_expiry[df_selected_expiry['Type'] == 'Put']['OI'].sum()
    total_call_oi = df_selected_expiry[df_selected_expiry['Type'] == 'Call']['OI'].sum()
    pc_oi_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else np.nan
    
    total_put_vol = df_selected_expiry[df_selected_expiry['Type'] == 'Put']['Vol'].sum()
    total_call_vol = df_selected_expiry[df_selected_expiry['Type'] == 'Call']['Vol'].sum()
    pc_vol_ratio = total_put_vol / total_call_vol if total_call_vol > 0 else np.nan
    
    return {'pc_oi_ratio': pc_oi_ratio, 'pc_vol_ratio': pc_vol_ratio}

def calculate_expected_move(df_selected_expiry, spot_price):
    """
    Calcola il movimento atteso (Expected Move) basato sulla IV ATM.
    """
    try:
        atm_strike_index = (df_selected_expiry['Strike'] - spot_price).abs().idxmin()
        atm_strike_val = df_selected_expiry.loc[atm_strike_index]['Strike']
        df_atm = df_selected_expiry[df_selected_expiry['Strike'] == atm_strike_val]
        iv_atm = df_atm['IV'].mean()
        dte_years = df_atm['DTE_Years'].iloc[0]
        
        if dte_years <= 0: dte_years = 1 / 365.25 
        move = spot_price * iv_atm * np.sqrt(dte_years)
        
        return {'move': move, 'upper_band': spot_price + move, 'lower_band': spot_price - move, 'iv_atm': iv_atm}
    except Exception as e:
        print(f"[Errore Calcolo Expected Move]: {e}")
        return {'move': None, 'upper_band': None, 'lower_band': None, 'iv_atm': None}

def calculate_volume_profile(df_selected_expiry, spot_price):
    """
    Prepara il DataFrame per il grafico bidirezionale dei Volumi.
    """
    range_lower = spot_price * 0.75
    range_upper = spot_price * 1.25
    df_vol_relevant = df_selected_expiry[
        (df_selected_expiry['Strike'] >= range_lower) &
        (df_selected_expiry['Strike'] <= range_upper)
    ]
    
    vol_calls_grouped = df_vol_relevant[df_vol_relevant['Type'] == 'Call'].groupby('Strike')['Vol'].sum()
    vol_puts_grouped = df_vol_relevant[df_vol_relevant['Type'] == 'Put'].groupby('Strike')['Vol'].sum()
    df_vol_profile = pd.DataFrame({'Calls_Vol': vol_calls_grouped, 'Puts_Vol': vol_puts_grouped}).fillna(0).reset_index()
    df_vol_profile['Puts_Vol_Neg'] = df_vol_profile['Puts_Vol'] * -1.0

    return {
        'df_vol_profile': df_vol_profile
    }
