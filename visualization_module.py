# File: visualization_module.py
#
# Modulo per la creazione di grafici Plotly.
# Contiene la logica di visualizzazione delle Celle 7, 8 e 9.
# Come da Sezione 3.3 del documento di progettazione.
# -----------------------------------------------------------------------------

import plotly.graph_objects as go
import numpy as np
import pandas as pd
from scipy.interpolate import griddata

# -----------------------------------------------------------------------------
# 1. TEMA GRAFICO PROFESSIONALE (Sezione 5.3)
# -----------------------------------------------------------------------------
# Definiamo i colori e i layout standard
KRITERION_THEME = {
    'paper_bgcolor': '#0e1117',  # Sfondo esterno
    'plot_bgcolor': '#111827',   # Sfondo grafico
    'font_color': '#e5e7eb',     # Colore testo
    'gridcolor': '#1f2937',      # Colore griglia
    'zerolinecolor': '#6b7280',  # Colore linea zero
    'color_bullish': '#10b981',
    'color_bearish': '#ef4444',
    'color_neutral': '#3b82f6',  # Blu per lo Spot
    'color_accent': '#facc15',   # Giallo per lo Switch
}

def apply_kriterion_theme(fig):
    """Applica il layout standard Kriterion Quant a una figura Plotly."""
    fig.update_layout(
        paper_bgcolor=KRITERION_THEME['paper_bgcolor'],
        plot_bgcolor=KRITERION_THEME['plot_bgcolor'],
        font=dict(color=KRITERION_THEME['font_color'], family='Inter, sans-serif'),
        xaxis=dict(gridcolor=KRITERION_THEME['gridcolor']),
        yaxis=dict(gridcolor=KRITERION_THEME['gridcolor'], zerolinecolor=KRITERION_THEME['zerolinecolor']),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#1f2937", font_size=12, font_family="Monaco, monospace"),
        # Watermark (Sez 5.3)
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
# 2. GRAFICO 1: GEX PROFILE (per Tab 1)
# -----------------------------------------------------------------------------
def create_gex_profile_chart(df_gex_profile, spot_price, gamma_switch_point, expiry_label):
    """
    Crea il Bar Chart GEX per una singola scadenza.
    Logica da Cella 11.
    """
    
    # Filtra per rilevanza (vicino allo spot)
    range_lower = spot_price * 0.80
    range_upper = spot_price * 1.20
    df_plot = df_gex_profile[
        (df_gex_profile['Strike'] >= range_lower) &
        (df_gex_profile['Strike'] <= range_upper)
    ].copy()
    
    # Assegna colori
    df_plot['Color'] = np.where(df_plot['Net_GEX'] > 0, 
                                KRITERION_THEME['color_bullish'], 
                                KRITERION_THEME['color_bearish'])
    
    fig = go.Figure()

    # Barre GEX
    fig.add_trace(go.Bar(
        x=df_plot['Strike'], y=df_plot['Net_GEX'],
        marker_color=df_plot['Color'], name="Net GEX",
        hovertemplate="<b>Strike: %{x}</b><br>Net GEX: %{y:,.0f}<extra></extra>"
    ))

    # Linea Spot
    fig.add_vline(
        x=spot_price, line_width=2, line_dash="dot", 
        line_color=KRITERION_THEME['color_neutral'],
        annotation_text=f"Spot: {spot_price:.2f}",
        annotation_position="top right"
    )

    # Linea Switch (solo se esiste)
    if gamma_switch_point:
        fig.add_vline(
            x=gamma_switch_point, line_width=2, line_dash="dash", 
            line_color=KRITERION_THEME['color_accent'],
            annotation_text=f"Switch: {gamma_switch_point:.2f}",
            annotation_position="top left"
        )
    
    # Applica tema
    fig = apply_kriterion_theme(fig)
    fig.update_layout(
        title=f"Profilo GEX (Scadenza: {expiry_label})",
        xaxis_title="Strike Price",
        yaxis_title="Net GEX (Notional $)"
    )
    
    return fig

# -----------------------------------------------------------------------------
# 3. GRAFICO 2: OI DISTRIBUTION (per Tab 2)
# -----------------------------------------------------------------------------
def create_oi_profile_chart(df_oi_profile, spot_price, expiry_label):
    """
    Crea il Grafico OI Bidirezionale per una singola scadenza.
    Logica da Cella 11.
    """
    fig = go.Figure()

    # Calls (Positive)
    fig.add_trace(go.Bar(
        x=df_oi_profile['Strike'], y=df_oi_profile['Calls_OI'],
        name="Calls OI (Resistenza)", marker_color=KRITERION_THEME['color_bullish'],
        hovertemplate="<b>Strike: %{x}</b><br>Calls OI: %{y:,.0f}<extra></extra>"
    ))
    
    # Puts (Negative)
    fig.add_trace(go.Bar(
        x=df_oi_profile['Strike'], y=df_oi_profile['Puts_OI_Neg'],
        name="Puts OI (Supporto)", marker_color=KRITERION_THEME['color_bearish'],
        customdata=df_oi_profile['Puts_OI'], # Per mostrare valore positivo
        hovertemplate="<b>Strike: %{x}</b><br>Puts OI: %{customdata:,.0f}<extra></extra>"
    ))

    # Linea Spot
    fig.add_vline(
        x=spot_price, line_width=2, line_dash="dot", 
        line_color=KRITERION_THEME['color_neutral'],
        annotation_text=f"Spot: {spot_price:.2f}",
        annotation_position="top right"
    )
    
    # Applica tema
    fig = apply_kriterion_theme(fig)
    fig.update_layout(
        title=f"Distribuzione OI (Scadenza: {expiry_label})",
        xaxis_title="Strike Price",
        yaxis_title="Open Interest (Calls: Positivo, Puts: Negativo)",
        barmode='relative' # Layout bidirezionale
    )
    
    return fig

# -----------------------------------------------------------------------------
# 4. GRAFICO 3: VOLATILITY SURFACE 3D (per Tab 3)
# -----------------------------------------------------------------------------
def create_volatility_surface_3d(df_all_processed):
    """
    Crea la superficie 3D della Volatilità Implicita (IV)
    utilizzando TUTTE le scadenze.
    Logica da Cella 9.
    
    Args:
        df_all_processed (pd.DataFrame): Il DataFrame completo, non filtrato.
    """
    
    try:
        # Prepara i dati (OTM Puts o OTM Calls)
        df_surf = df_all_processed[
            (df_all_processed['Type'] == 'Put') & (df_all_processed['Moneyness'] < 1.0)
        ].copy()
        df_surf = df_surf[(df_surf['IV'] > 0.01) & (df_surf['IV'] < 1.50)]
        
        if len(df_surf) < 10:
             df_surf = df_all_processed[
                (df_all_processed['Type'] == 'Call') & (df_all_processed['Moneyness'] > 1.0)
            ].copy()
             df_surf = df_surf[(df_surf['IV'] > 0.01) & (df_surf['IV'] < 1.50)]

        if len(df_surf) < 10:
             raise Exception("Dati OTM insufficienti per l'interpolazione.")
        
        # Interpolazione (Logica Cella 9)
        x_grid = np.linspace(df_surf['DTE_Days'].min(), df_surf['DTE_Days'].max(), 50) # Griglia più leggera
        y_grid = np.linspace(df_surf['Strike'].min(), df_surf['Strike'].max(), 50)
        X_grid, Y_grid = np.meshgrid(x_grid, y_grid)

        Z_grid = griddata(
            points=(df_surf['DTE_Days'], df_surf['Strike']),
            values=df_surf['IV'],
            xi=(X_grid, Y_grid),
            method='linear' # 'linear' è più veloce e stabile di 'cubic'
        )
        
        fig = go.Figure()
        fig.add_trace(go.Surface(
            x=X_grid, y=Y_grid, z=Z_grid,
            colorscale='Viridis', # Come da Sez 5.2
            colorbar_title='Implied Volatility',
            name="IV Surface",
            hovertemplate="<b>DTE: %{x:.0f}</b><br>Strike: %{y:.0f}<br>IV: %{z:.2%}<extra></extra>"
        ))
        
        # Applica tema (diverso per 3D)
        fig = apply_kriterion_theme(fig)
        fig.update_layout(
            title="Superficie di Volatilità Implicita (IV) - OTM (Tutte le Scadenze)",
            scene=dict(
                xaxis_title='Days to Expiry (DTE)',
                yaxis_title='Strike Price',
                zaxis_title='Implied Volatility (IV)',
                xaxis=dict(gridcolor=KRITERION_THEME['gridcolor']),
                yaxis=dict(gridcolor=KRITERION_THEME['gridcolor']),
                zaxis=dict(gridcolor=KRITERION_THEME['gridcolor']),
                bgcolor=KRITERION_THEME['paper_bgcolor'], # Sfondo scena 3D
            ),
            scene_camera_eye=dict(x=1.8, y=-1.8, z=0.8) # Angolo visuale
        )
        
        return fig

    except Exception as e:
        print(f"[ERRORE in create_volatility_surface_3d]: {e}")
        # Restituisci una figura vuota con un messaggio di errore
        fig = go.Figure()
        fig = apply_kriterion_theme(fig)
        fig.update_layout(title=f"Errore nella creazione della superficie 3D: {e}")
        return fig
