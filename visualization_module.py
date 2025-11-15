# File: visualization_module.py
#
# [VERSIONE COMPLETA]
# Contiene TUTTE le funzioni di plotting,
# inclusa l'ultima 'create_drift_arrow_chart'.
# -----------------------------------------------------------------------------

import plotly.graph_objects as go
import numpy as np
import pandas as pd
from scipy.interpolate import griddata

# -----------------------------------------------------------------------------
# 1. TEMA GRAFICO PROFESSIONALE (Sezione 5.3)
# -----------------------------------------------------------------------------
KRITERION_THEME = {
    'paper_bgcolor': '#0e1117',  'plot_bgcolor': '#111827',
    'font_color': '#e5e7eb',     'gridcolor': '#1f2937',
    'zerolinecolor': '#6b7280',  'color_bullish': '#10b981',
    'color_bearish': '#ef4444', 'color_neutral': '#3b82f6',
    'color_accent': '#facc15',
}

def apply_kriterion_theme(fig):
    """Applica il layout standard Kriterion Quant a una figura Plotly."""
    fig.update_layout(
        paper_bgcolor=KRITERION_THEME['paper_bgcolor'],
        plot_bgcolor=KRITERION_THEME['plot_bgcolor'],
        font=dict(color=KRITERION_THEME['font_color'], family='Inter, sans-serif'),
        xaxis=dict(gridcolor=KRITERION_THEME['gridcolor'], zerolinecolor=KRITERION_THEME['zerolinecolor']),
        yaxis=dict(gridcolor=KRITERION_THEME['gridcolor']),
        hovermode="y unified",
        hoverlabel=dict(bgcolor="#1f2937", font_size=12, font_family="Monaco, monospace"),
        annotations=[
            dict(
                text="Kriterion Quant", textangle=0, opacity=0.1,
                font=dict(color=KRITERION_THEME['font_color'], size=40),
                xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False
            )
        ]
    )
    return fig

# -----------------------------------------------------------------------------
# 2. GRAFICO 1: GEX PROFILE (Orizzontale)
# -----------------------------------------------------------------------------
def create_gex_profile_chart(df_gex_profile, spot_price, gamma_switch_point, expiry_label):
    """Crea il Bar Chart GEX (orizzontale, strike su Asse Y)."""
    
    range_lower = spot_price * 0.80
    range_upper = spot_price * 1.20
    df_plot = df_gex_profile[(df_gex_profile['Strike'] >= range_lower) & (df_gex_profile['Strike'] <= range_upper)].copy()
    
    df_plot['Color'] = np.where(df_plot['Net_GEX'] > 0, 
                                KRITERION_THEME['color_bullish'], 
                                KRITERION_THEME['color_bearish'])
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_plot['Net_GEX'], y=df_plot['Strike'],
        orientation='h', marker_color=df_plot['Color'], name="Net GEX",
        hovertemplate="<b>Strike: %{y}</b><br>Net GEX: %{x:,.0f}<extra></extra>"
    ))
    fig.add_hline(y=spot_price, line_width=2, line_dash="dot", line_color=KRITERION_THEME['color_neutral'],
                  annotation_text=f"Spot: {spot_price:.2f}", annotation_position="bottom right")
    if gamma_switch_point:
        fig.add_hline(y=gamma_switch_point, line_width=2, line_dash="dash", line_color=KRITERION_THEME['color_accent'],
                      annotation_text=f"Switch: {gamma_switch_point:.2f}", annotation_position="bottom left")
    
    fig = apply_kriterion_theme(fig)
    fig.update_layout(
        title=f"Profilo GEX (Scadenza: {expiry_label})",
        xaxis_title="Net GEX (Notional $)", yaxis_title="Strike Price",
        height=800, yaxis=dict(autorange="reversed")
    )
    return fig

# -----------------------------------------------------------------------------
# 3. GRAFICO 2: OI DISTRIBUTION (Orizzontale)
# -----------------------------------------------------------------------------
def create_oi_profile_chart(df_oi_profile, spot_price, expiry_label):
    """Crea il Grafico OI Bidirezionale (orizzontale, strike su Asse Y)."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_oi_profile['Calls_OI'], y=df_oi_profile['Strike'],
        orientation='h', name="Calls OI (Resistenza)", marker_color=KRITERION_THEME['color_bullish'],
        hovertemplate="<b>Strike: %{y}</b><br>Calls OI: %{x:,.0f}<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        x=df_oi_profile['Puts_OI_Neg'], y=df_oi_profile['Strike'],
        orientation='h', name="Puts OI (Supporto)", marker_color=KRITERION_THEME['color_bearish'],
        customdata=df_oi_profile['Puts_OI'],
        hovertemplate="<b>Strike: %{y}</b><br>Puts OI: %{customdata:,.0f}<extra></extra>"
    ))
    fig.add_hline(y=spot_price, line_width=2, line_dash="dot", line_color=KRITERION_THEME['color_neutral'],
                  annotation_text=f"Spot: {spot_price:.2f}", annotation_position="bottom right")
    
    fig = apply_kriterion_theme(fig)
    fig.update_layout(
        title=f"Distribuzione OI (Scadenza: {expiry_label})",
        xaxis_title="Open Interest (Puts: Negativo, Calls: Positivo)", yaxis_title="Strike Price",
        barmode='relative', height=800, yaxis=dict(autorange="reversed")
    )
    return fig

# -----------------------------------------------------------------------------
# 4. GRAFICO 3: VOLUME DISTRIBUTION (Orizzontale)
# -----------------------------------------------------------------------------
def create_volume_profile_chart(df_vol_profile, spot_price, expiry_label):
    """Crea il Grafico Volumi Bidirezionale (orizzontale, strike su Asse Y)."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_vol_profile['Calls_Vol'], y=df_vol_profile['Strike'],
        orientation='h', name="Calls Volume", marker_color=KRITERION_THEME['color_bullish'],
        hovertemplate="<b>Strike: %{y}</b><br>Calls Vol: %{x:,.0f}<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        x=df_vol_profile['Puts_Vol_Neg'], y=df_vol_profile['Strike'],
        orientation='h', name="Puts Volume", marker_color=KRITERION_THEME['color_bearish'],
        customdata=df_vol_profile['Puts_Vol'],
        hovertemplate="<b>Strike: %{y}</b><br>Puts Vol: %{customdata:,.0f}<extra></extra>"
    ))
    fig.add_hline(y=spot_price, line_width=2, line_dash="dot", line_color=KRITERION_THEME['color_neutral'],
                  annotation_text=f"Spot: {spot_price:.2f}", annotation_position="bottom right")
    
    fig = apply_kriterion_theme(fig)
    fig.update_layout(
        title=f"Distribuzione Volumi (Scadenza: {expiry_label})",
        xaxis_title="Volume (Puts: Negativo, Calls: Positivo)", yaxis_title="Strike Price",
        barmode='relative', height=800, yaxis=dict(autorange="reversed")
    )
    return fig

# -----------------------------------------------------------------------------
# 5. GRAFICO 4: MAX PAIN (Orizzontale)
# -----------------------------------------------------------------------------
def create_max_pain_chart(df_payouts, max_pain_strike, expiry_label):
    """Crea il grafico del Payout Totale (Max Pain) (orizzontale)."""
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_payouts['Total_Payout'], y=df_payouts['Strike'],
        orientation='h', name="Total Payout ($)", marker_color=KRITERION_THEME['color_neutral'],
        hovertemplate="<b>Strike: %{y}</b><br>Total Payout: %{x:,.0f}<extra></extra>"
    ))
    fig.add_hline(y=max_pain_strike, line_width=2, line_dash="dash", line_color=KRITERION_THEME['color_accent'],
                  annotation_text=f"Max Pain: {max_pain_strike:.0f}", annotation_position="bottom left")
    
    fig = apply_kriterion_theme(fig)
    fig.update_layout(
        title=f"Payout Totale a Scadenza (Max Pain) per {expiry_label}",
        xaxis_title="Payout Totale ($)", yaxis_title="Strike Price",
        height=800, yaxis=dict(autorange="reversed")
    )
    return fig

# -----------------------------------------------------------------------------
# 6. GRAFICO 5: VOLATILITY SURFACE 3D
# -----------------------------------------------------------------------------
def create_volatility_surface_3d(df_all_processed):
    """Crea la superficie 3D della Volatilità Implicita (IV)."""
    try:
        df_surf_puts = df_all_processed[(df_all_processed['Type'] == 'Put') & (df_all_processed['Moneyness'] < 1.0)].copy()
        df_surf_calls = df_all_processed[(df_all_processed['Type'] == 'Call') & (df_all_processed['Moneyness'] > 1.0)].copy()
        df_surf = pd.concat([df_surf_puts, df_surf_calls])
        df_surf = df_surf[(df_surf['IV'] > 0.01) & (df_surf['IV'] < 1.50)]
        if len(df_surf) < 20: raise Exception("Dati OTM insufficienti.")
        
        x_grid = np.linspace(df_surf['DTE_Days'].min(), df_surf['DTE_Days'].max(), 50) 
        y_grid = np.linspace(df_surf['Strike'].min(), df_surf['Strike'].max(), 50)
        X_grid, Y_grid = np.meshgrid(x_grid, y_grid)
        Z_grid = griddata(points=(df_surf['DTE_Days'], df_surf['Strike']), values=df_surf['IV'], xi=(X_grid, Y_grid), method='linear')
        
        fig = go.Figure()
        fig.add_trace(go.Surface(
            x=X_grid, y=Y_grid, z=Z_grid,
            colorscale='Viridis', colorbar_title='Implied Volatility',
            name="IV Surface",
            hovertemplate="<b>DTE: %{x:.0f}</b><br>Strike: %{y:.0f}<br>IV: %{z:.2%}<extra></extra>"
        ))
        fig = apply_kriterion_theme(fig)
        fig.update_layout(
            title="Superficie di Volatilità Implicita (IV) - OTM (Tutte le Scadenze)",
            scene=dict(xaxis_title='Days to Expiry (DTE)', yaxis_title='Strike Price', zaxis_title='Implied Volatility (IV)',
                       xaxis=dict(gridcolor=KRITERION_THEME['gridcolor']), yaxis=dict(gridcolor=KRITERION_THEME['gridcolor']),
                       zaxis=dict(gridcolor=KRITERION_THEME['gridcolor']), bgcolor=KRITERION_THEME['paper_bgcolor']),
            scene_camera_eye=dict(x=1.8, y=-1.8, z=0.8), height=900
        )
        return fig
    except Exception as e:
        print(f"[ERRORE in create_volatility_surface_3d]: {e}")
        fig = go.Figure()
        fig = apply_kriterion_theme(fig)
        fig.update_layout(title=f"Errore nella creazione della superficie 3D: {e}", height=900)
        return fig

# -----------------------------------------------------------------------------
# 7. GRAFICO 6: ACTIVITY RATIO (Drift Dettagliato)
# -----------------------------------------------------------------------------
def create_activity_ratio_chart(df_activity_profile, spot_price, expiry_label):
    """Crea il Grafico del Rapporto Vol/OI (Drift) (orizzontale)."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_activity_profile['Call_Activity_Ratio'],
        y=df_activity_profile['Strike'],
        orientation='h', name="Call Activity (Vol/OI)", marker_color=KRITERION_THEME['color_bullish'],
        customdata=df_activity_profile['Call_Vol'],
        hovertemplate="<b>Strike: %{y}</b><br>Rapporto Attività: %{x:.2f}<br>Volume: %{customdata:,.0f}<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        x=df_activity_profile['Put_Activity_Ratio_Neg'],
        y=df_activity_profile['Strike'],
        orientation='h', name="Put Activity (Vol/OI)", marker_color=KRITERION_THEME['color_bearish'],
        customdata=df_activity_profile['Put_Activity_Ratio'],
        hovertemplate="<b>Strike: %{y}</b><br>Rapporto Attività: %{customdata:.2f}<extra></extra>"
    ))
    fig.add_hline(y=spot_price, line_width=2, line_dash="dot", line_color=KRITERION_THEME['color_neutral'],
                  annotation_text=f"Spot: {spot_price:.2f}", annotation_position="bottom right")
    
    fig = apply_kriterion_theme(fig)
    fig.update_layout(
        title=f"Analisi Drift (Rapporto Vol/OI) per {expiry_label}",
        xaxis_title="Rapporto Attività (Volume / (OI+1))",
        yaxis_title="Strike Price", barmode='relative', height=800,
        yaxis=dict(autorange="reversed")
    )
    return fig

# -----------------------------------------------------------------------------
# 8. GRAFICO 7: DRIFT ARROW (Sintesi)
# -----------------------------------------------------------------------------
def create_drift_arrow_chart(drift_score, spot_price, expiry_label):
    """
    Crea un grafico a freccia che sintetizza la direzione del drift dei volumi.
    """
    fig = go.Figure()

    # Determina colore e direzione
    if drift_score > spot_price:
        color = KRITERION_THEME['color_bullish']
        text = f"Drift Rialzista: {drift_score:.2f}"
    elif drift_score < spot_price:
        color = KRITERION_THEME['color_bearish']
        text = f"Drift Ribassista: {drift_score:.2f}"
    else:
        color = KRITERION_THEME['color_neutral']
        text = f"Drift Neutrale: {drift_score:.2f}"

    # Calcola il range del grafico per centrare lo spot
    min_val = min(spot_price, drift_score)
    max_val = max(spot_price, drift_score)
    padding = (max_val - min_val) * 1.5 # Aggiungi padding
    if padding == 0: padding = spot_price * 0.01 # Padding minimo se sono uguali
    
    x_range = [min_val - padding, max_val + padding]

    # Aggiungi la freccia (usando Scatter)
    fig.add_trace(go.Scatter(
        x=[spot_price, drift_score],
        y=[0, 0], # Linea orizzontale
        mode='lines+markers',
        marker=dict(
            symbol='arrow-right' if drift_score >= spot_price else 'arrow-left',
            size=15, 
            color=color, 
            angleref="previous" # Fa puntare la freccia correttamente
        ),
        line=dict(width=4, color=color),
        name="Drift Direzionale",
        hovertemplate=f"Drift Score: {drift_score:.2f}<extra></extra>"
    ))

    # Linea Spot
    fig.add_vline(
        x=spot_price, line_width=2, line_dash="dot", 
        line_color=KRITERION_THEME['color_neutral'],
        annotation_text=f"Spot: {spot_price:.2f}",
        annotation_position="top"
    )
    
    fig = apply_kriterion_theme(fig)
    fig.update_layout(
        title=f"Sintesi Drift Volumi (VWAS) vs Spot ({expiry_label})",
        xaxis_title="Strike Price",
        yaxis_visible=False, # Nasconde asse y
        showlegend=False,
        height=200, # Grafico piccolo per sintesi
        xaxis=dict(range=x_range) # Range dinamico
    )
    return fig
