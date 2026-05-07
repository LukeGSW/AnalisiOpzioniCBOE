# File: calculations_module.py
#
# [VERSIONE v2 - CON DEX E VEX]
# - FIX GEX: Ordinamento e logica "Flip più vicino".
# - FIX DRIFT (VWAS): Call VWAS per isolare il target speculativo.
# - NUOVO: calculate_dex_metrics (Delta Exposure Aggregata per Strike).
# - NUOVO: calculate_vex_metrics (Vanna Exposure Aggregata per Strike + Switch Point).
# -----------------------------------------------------------------------------

import pandas as pd
import numpy as np


# =============================================================================
# HELPER PRIVATO: Zero Crossing (interpolazione lineare)
# =============================================================================
def _find_nearest_zero_crossing(df_sorted, value_col, spot_price):
    """
    Trova il punto di zero crossing più vicino allo spot (interpolazione lineare).
    Usato sia per GEX Switch che per Vanna Switch.

    Args:
        df_sorted  : DataFrame ordinato per Strike con colonna di valori.
        value_col  : Nome della colonna numerica da analizzare.
        spot_price : Prezzo corrente del sottostante.

    Returns:
        float | None: Strike interpolato dello zero crossing, o None se non trovato.
    """
    try:
        if df_sorted.empty or len(df_sorted) < 2:
            return None

        signs = np.sign(df_sorted[value_col])
        # Identifica dove il segno cambia tra una riga e la successiva
        sign_change = (signs != signs.shift(-1)) & (signs.shift(-1).notna())
        flip_indices = df_sorted.index[sign_change]

        candidates = []
        for idx in flip_indices:
            pos = df_sorted.index.get_loc(idx)
            if pos + 1 >= len(df_sorted):
                continue
            row_curr = df_sorted.iloc[pos]
            row_next = df_sorted.iloc[pos + 1]

            x0, y0 = row_curr['Strike'], row_curr[value_col]
            x1, y1 = row_next['Strike'], row_next[value_col]

            if (y1 - y0) != 0:
                zero_cross = x0 - (y0 * (x1 - x0) / (y1 - y0))
                candidates.append(zero_cross)

        if candidates:
            # Ritorna il flip point più vicino allo spot attuale
            return min(candidates, key=lambda x: abs(x - spot_price))
        return None

    except Exception as e:
        print(f"[_find_nearest_zero_crossing]: {e}")
        return None


# =============================================================================
# 1. GAMMA EXPOSURE (GEX)
# =============================================================================
def calculate_gex_metrics(df_selected_expiry, spot_price):
    """
    Calcola le metriche GEX per una singola scadenza.
    Trova il Gamma Switch Point più vicino al prezzo attuale.
    """
    df_gex_strike = df_selected_expiry.groupby('Strike')['GEX_Signed'].sum().reset_index()
    df_gex_strike.rename(columns={'GEX_Signed': 'Net_GEX'}, inplace=True)
    df_gex_strike = df_gex_strike.sort_values('Strike').reset_index(drop=True)

    total_net_gex      = df_gex_strike['Net_GEX'].sum()
    gamma_switch_local = _find_nearest_zero_crossing(df_gex_strike, 'Net_GEX', spot_price)
    spot_delta         = (spot_price - gamma_switch_local) if gamma_switch_local is not None else None

    return {
        'df_gex_profile':    df_gex_strike,
        'total_net_gex':     total_net_gex,
        'gamma_switch_point': gamma_switch_local,
        'spot_switch_delta': spot_delta
    }


# =============================================================================
# 2. OPEN INTEREST WALLS
# =============================================================================
def calculate_oi_walls(df_selected_expiry, spot_price):
    """Calcola i Put/Call Walls per una singola scadenza."""
    range_lower = spot_price * 0.75
    range_upper = spot_price * 1.25
    df_oi_relevant = df_selected_expiry[
        (df_selected_expiry['Strike'] >= range_lower) &
        (df_selected_expiry['Strike'] <= range_upper)
    ]

    oi_puts_support  = df_oi_relevant[(df_oi_relevant['Type'] == 'Put')  & (df_oi_relevant['Strike'] <= spot_price)]
    put_wall_strike, max_put_oi = (None, 0)
    if not oi_puts_support.empty:
        idx_max         = oi_puts_support['OI'].idxmax()
        put_wall_strike = oi_puts_support.loc[idx_max]['Strike']
        max_put_oi      = oi_puts_support['OI'].max()

    oi_calls_res     = df_oi_relevant[(df_oi_relevant['Type'] == 'Call') & (df_oi_relevant['Strike'] >= spot_price)]
    call_wall_strike, max_call_oi = (None, 0)
    if not oi_calls_res.empty:
        idx_max          = oi_calls_res['OI'].idxmax()
        call_wall_strike = oi_calls_res.loc[idx_max]['Strike']
        max_call_oi      = oi_calls_res['OI'].max()

    oi_calls_grouped = df_oi_relevant[df_oi_relevant['Type'] == 'Call'].groupby('Strike')['OI'].sum()
    oi_puts_grouped  = df_oi_relevant[df_oi_relevant['Type'] == 'Put'].groupby('Strike')['OI'].sum()
    df_oi_profile = pd.DataFrame({'Calls_OI': oi_calls_grouped, 'Puts_OI': oi_puts_grouped}).fillna(0).reset_index()
    df_oi_profile['Puts_OI_Neg'] = df_oi_profile['Puts_OI'] * -1.0

    return {
        'df_oi_profile':   df_oi_profile,
        'put_wall_strike': put_wall_strike, 'put_wall_oi':  max_put_oi,
        'call_wall_strike': call_wall_strike, 'call_wall_oi': max_call_oi
    }


# =============================================================================
# 3. MAX PAIN
# =============================================================================
def calculate_max_pain(df_selected_expiry):
    """Calcola lo strike Max Pain per la scadenza selezionata."""
    strikes  = sorted(df_selected_expiry['Strike'].unique())
    calls_oi = df_selected_expiry[df_selected_expiry['Type'] == 'Call'].set_index('Strike')['OI']
    puts_oi  = df_selected_expiry[df_selected_expiry['Type'] == 'Put'].set_index('Strike')['OI']
    total_payout_list = []

    for expiry_price in strikes:
        call_intrinsic = (expiry_price - calls_oi.index).to_numpy().clip(min=0)
        call_payout    = (call_intrinsic * calls_oi).sum()
        put_intrinsic  = (puts_oi.index - expiry_price).to_numpy().clip(min=0)
        put_payout     = (put_intrinsic * puts_oi).sum()
        total_payout_list.append({'Strike': expiry_price, 'Total_Payout': call_payout + put_payout})

    if not total_payout_list:
        return None, pd.DataFrame()
    df_payouts      = pd.DataFrame(total_payout_list)
    max_pain_strike = df_payouts.loc[df_payouts['Total_Payout'].idxmin()]['Strike']
    return max_pain_strike, df_payouts


# =============================================================================
# 4. PUT/CALL RATIOS
# =============================================================================
def calculate_pc_ratios(df_selected_expiry):
    """Calcola i Put/Call Ratios per OI e Volume."""
    total_put_oi   = df_selected_expiry[df_selected_expiry['Type'] == 'Put']['OI'].sum()
    total_call_oi  = df_selected_expiry[df_selected_expiry['Type'] == 'Call']['OI'].sum()
    pc_oi_ratio    = total_put_oi / total_call_oi if total_call_oi > 0 else np.nan
    total_put_vol  = df_selected_expiry[df_selected_expiry['Type'] == 'Put']['Vol'].sum()
    total_call_vol = df_selected_expiry[df_selected_expiry['Type'] == 'Call']['Vol'].sum()
    pc_vol_ratio   = total_put_vol / total_call_vol if total_call_vol > 0 else np.nan
    return {'pc_oi_ratio': pc_oi_ratio, 'pc_vol_ratio': pc_vol_ratio}


# =============================================================================
# 5. EXPECTED MOVE
# =============================================================================
def calculate_expected_move(df_selected_expiry, spot_price):
    """Calcola il movimento atteso basato sulla IV ATM."""
    try:
        atm_strike_index = (df_selected_expiry['Strike'] - spot_price).abs().idxmin()
        atm_strike_val   = df_selected_expiry.loc[atm_strike_index]['Strike']
        df_atm           = df_selected_expiry[df_selected_expiry['Strike'] == atm_strike_val]
        iv_atm           = df_atm['IV'].mean()
        dte_years        = df_atm['DTE_Years'].iloc[0]
        if dte_years <= 0:
            dte_years = 1 / 365.25
        move = spot_price * iv_atm * np.sqrt(dte_years)
        return {'move': move, 'upper_band': spot_price + move, 'lower_band': spot_price - move, 'iv_atm': iv_atm}
    except Exception as e:
        print(f"[Errore Calcolo Expected Move]: {e}")
        return {'move': None, 'upper_band': None, 'lower_band': None, 'iv_atm': None}


# =============================================================================
# 6. VOLUME PROFILE
# =============================================================================
def calculate_volume_profile(df_selected_expiry, spot_price):
    """Prepara il DataFrame per il grafico bidirezionale dei Volumi."""
    range_lower = spot_price * 0.75
    range_upper = spot_price * 1.25
    df_vol_relevant  = df_selected_expiry[
        (df_selected_expiry['Strike'] >= range_lower) &
        (df_selected_expiry['Strike'] <= range_upper)
    ]
    vol_calls_grouped = df_vol_relevant[df_vol_relevant['Type'] == 'Call'].groupby('Strike')['Vol'].sum()
    vol_puts_grouped  = df_vol_relevant[df_vol_relevant['Type'] == 'Put'].groupby('Strike')['Vol'].sum()
    df_vol_profile = pd.DataFrame({'Calls_Vol': vol_calls_grouped, 'Puts_Vol': vol_puts_grouped}).fillna(0).reset_index()
    df_vol_profile['Puts_Vol_Neg'] = df_vol_profile['Puts_Vol'] * -1.0
    return {'df_vol_profile': df_vol_profile}


# =============================================================================
# 7. ACTIVITY RATIO / DRIFT SCORE
# =============================================================================
def calculate_activity_ratio(df_selected_expiry, spot_price):
    """
    Calcola il rapporto Vol/OI e il 'Drift Score' (VWAS).

    Il Drift Score calcola il VWAS (Volume Weighted Average Strike)
    SOLO DELLE CALL per identificare il 'Target Speculativo' eliminando
    il rumore delle Put difensive OTM.
    """
    range_lower = spot_price * 0.75
    range_upper = spot_price * 1.25
    df_relevant = df_selected_expiry[
        (df_selected_expiry['Strike'] >= range_lower) &
        (df_selected_expiry['Strike'] <= range_upper)
    ]

    df_grouped  = df_relevant.groupby(['Strike', 'Type'])[['OI', 'Vol']].sum().unstack(fill_value=0)
    df_profile  = pd.DataFrame(index=df_grouped.index)
    df_profile['Call_OI']  = df_grouped[('OI',  'Call')]
    df_profile['Call_Vol'] = df_grouped[('Vol', 'Call')]
    df_profile['Put_OI']   = df_grouped[('OI',  'Put')]
    df_profile['Put_Vol']  = df_grouped[('Vol', 'Put')]

    df_profile['Call_Activity_Ratio']     = df_profile['Call_Vol'] / (df_profile['Call_OI'] + 1)
    df_profile['Put_Activity_Ratio']      = df_profile['Put_Vol']  / (df_profile['Put_OI']  + 1)
    df_profile['Put_Activity_Ratio_Neg']  = df_profile['Put_Activity_Ratio'] * -1.0

    calls_only     = df_relevant[df_relevant['Type'] == 'Call']
    total_call_vol = calls_only['Vol'].sum()

    if total_call_vol > 0:
        call_vol_by_strike = calls_only.groupby('Strike')['Vol'].sum()
        drift_score = (call_vol_by_strike.index * call_vol_by_strike).sum() / call_vol_by_strike.sum()
    else:
        drift_score = spot_price

    return {
        'df_activity_profile': df_profile.reset_index(),
        'drift_score':         drift_score
    }


# =============================================================================
# 8. DELTA EXPOSURE (DEX) — NUOVO
# =============================================================================
def calculate_dex_metrics(df_selected_expiry, spot_price):
    """
    Calcola la Delta Exposure (DEX) aggregata per Strike.

    La DEX Nozionale rappresenta la sensitività netta del book di opzioni
    a una variazione del Prezzo del Sottostante. Un DEX netto positivo
    indica che i dealers hanno bisogno di vendere il sottostante per
    rimanere delta-hedged; un DEX netto negativo indica acquisti necessari.

    Formula applicata in data_module.py:
        DEX_Notional = Delta * OI * 100 * Spot

    Returns:
        dict con:
        - df_dex_profile   : DataFrame [Strike, Net_DEX] ordinato per Strike
        - total_net_dex    : Somma algebrica di tutto il DEX per la scadenza
    """
    # Aggrega DEX_Notional per Strike (somma calls + puts)
    df_dex_strike = df_selected_expiry.groupby('Strike')['DEX_Notional'].sum().reset_index()
    df_dex_strike.rename(columns={'DEX_Notional': 'Net_DEX'}, inplace=True)
    df_dex_strike = df_dex_strike.sort_values('Strike').reset_index(drop=True)

    total_net_dex = df_dex_strike['Net_DEX'].sum()

    return {
        'df_dex_profile': df_dex_strike,
        'total_net_dex':  total_net_dex
    }


# =============================================================================
# 9. VANNA EXPOSURE (VEX) — NUOVO
# =============================================================================
def calculate_vex_metrics(df_selected_expiry, spot_price):
    """
    Calcola la Vanna Exposure (VEX) aggregata per Strike.

    La VEX Nozionale rappresenta la sensitività del Delta dei dealers
    rispetto a una variazione dell'1% della Volatilità Implicita.

    Interpretazione operativa:
    - VEX netto positivo a un certo strike: se la volatilità SCENDE,
      i dealers devono COMPRARE il sottostante in quel nodo (effetto
      supporto dei prezzi in regime di vol compressa).
    - VEX netto negativo: se la volatilità SCENDE, i dealers devono
      VENDERE (effetto pressione ribassista in certi nodi).

    Formula applicata in data_module.py:
        VEX_Notional = Vanna_BS * OI * 100 * Spot * 0.01

    Il "Vanna Switch Point" è lo strike dove il profilo VEX netto
    attraversa lo zero (calcolato via interpolazione lineare, stessa
    logica del Gamma Switch Point).

    Returns:
        dict con:
        - df_vex_profile    : DataFrame [Strike, Net_VEX] ordinato per Strike
        - total_net_vex     : Somma algebrica del VEX per la scadenza
        - vanna_switch_point: Strike interpolato dello zero crossing (o None)
    """
    # Aggrega VEX_Notional per Strike (somma calls + puts)
    df_vex_strike = df_selected_expiry.groupby('Strike')['VEX_Notional'].sum().reset_index()
    df_vex_strike.rename(columns={'VEX_Notional': 'Net_VEX'}, inplace=True)
    df_vex_strike = df_vex_strike.sort_values('Strike').reset_index(drop=True)

    total_net_vex = df_vex_strike['Net_VEX'].sum()

    # Vanna Switch Point: zero crossing più vicino allo spot (stessa logica del GEX)
    vanna_switch_point = _find_nearest_zero_crossing(df_vex_strike, 'Net_VEX', spot_price)

    return {
        'df_vex_profile':    df_vex_strike,
        'total_net_vex':     total_net_vex,
        'vanna_switch_point': vanna_switch_point
    }
