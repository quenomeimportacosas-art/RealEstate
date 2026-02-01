"""
Dashboard de oportunidades inmobiliarias con Streamlit
"""
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

# Agregar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.sheets_db import GoogleSheetsDB
from config.settings import OPPORTUNITY_SCORE_THRESHOLD


# Configuración de página
st.set_page_config(
    page_title="🏠 Distressed Property Finder",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS
st.markdown("""
<style>
    .opportunity-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        border-left: 4px solid #e94560;
    }
    .metric-card {
        background: #0f3460;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
    }
    .high-score { color: #00ff88; }
    .medium-score { color: #ffd700; }
    .low-score { color: #ff6b6b; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_data():
    """Carga datos de Google Sheets"""
    try:
        db = GoogleSheetsDB()
        if db.connect():
            return db.to_dataframe()
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
    return pd.DataFrame()


def main():
    st.title("🏠 Distressed Property Finder - Palermo")
    st.markdown("### Sistema de detección de oportunidades inmobiliarias")
    
    # Sidebar - Filtros
    st.sidebar.header("🔍 Filtros")
    
    # Cargar datos
    df = load_data()
    
    if df.empty:
        st.warning("⚠️ No hay datos disponibles. Configura Google Sheets y ejecuta el scraper primero.")
        st.info("""
        ### Pasos para configurar:
        1. Crea un proyecto en Google Cloud Console
        2. Habilita Google Sheets API y Google Drive API
        3. Crea un Service Account y descarga el JSON
        4. Guarda el JSON en `config/credentials.json`
        5. Crea un Google Sheet y compártelo con el email del Service Account
        6. Copia el ID del Sheet en `config/settings.py`
        7. Ejecuta: `python main.py --source zonaprop --limit 50`
        """)
        return
        
    # Asegurar tipos
    numeric_cols = ['precio_usd_mep', 'm2_total', 'ambientes', 'opportunity_score', 'zscore']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    # Filtros
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        min_score = st.slider("Score mínimo", 0, 100, OPPORTUNITY_SCORE_THRESHOLD)
    with col2:
        max_price = st.number_input("Precio máximo USD", value=500000, step=50000)
        
    min_m2 = st.sidebar.slider("m² mínimo", 0, 200, 30)
    
    barrios = ['Todos'] + sorted(df['barrio'].dropna().unique().tolist())
    selected_barrio = st.sidebar.selectbox("Barrio", barrios)
    
    show_only_opportunities = st.sidebar.checkbox("Solo oportunidades", value=True)
    
    # Aplicar filtros
    filtered = df.copy()
    
    if 'opportunity_score' in filtered.columns:
        filtered = filtered[filtered['opportunity_score'] >= min_score]
    if 'precio_usd_mep' in filtered.columns:
        filtered = filtered[filtered['precio_usd_mep'] <= max_price]
    if 'm2_total' in filtered.columns:
        filtered = filtered[filtered['m2_total'] >= min_m2]
    if selected_barrio != 'Todos':
        filtered = filtered[filtered['barrio'] == selected_barrio]
    if show_only_opportunities and 'is_opportunity' in filtered.columns:
        filtered = filtered[filtered['is_opportunity'] == True]
        
    # Métricas principales
    st.markdown("---")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("🏠 Propiedades", len(filtered))
    with col2:
        opp_count = len(filtered[filtered.get('is_opportunity', False) == True]) if 'is_opportunity' in filtered.columns else 0
        st.metric("🎯 Oportunidades", opp_count)
    with col3:
        avg_price = filtered['precio_usd_mep'].mean() if 'precio_usd_mep' in filtered.columns else 0
        st.metric("💰 Precio promedio", f"${avg_price:,.0f}")
    with col4:
        avg_m2 = filtered['m2_total'].mean() if 'm2_total' in filtered.columns else 0
        st.metric("📐 m² promedio", f"{avg_m2:.0f}")
    with col5:
        if 'precio_usd_mep' in filtered.columns and 'm2_total' in filtered.columns:
            avg_m2_price = (filtered['precio_usd_mep'] / filtered['m2_total']).mean()
        else:
            avg_m2_price = 0
        st.metric("📊 USD/m²", f"${avg_m2_price:,.0f}")
        
    # Tabs principales
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Tabla", "🗺️ Mapa", "📊 Análisis", "🔥 Top Oportunidades"])
    
    with tab1:
        st.subheader("Propiedades filtradas")
        
        # Ordenar por score
        if 'opportunity_score' in filtered.columns:
            filtered = filtered.sort_values('opportunity_score', ascending=False)
            
        # Mostrar tabla
        display_cols = ['titulo', 'precio_usd_mep', 'm2_total', 'ambientes', 'barrio', 
                       'opportunity_score', 'zscore', 'keywords_detected', 'url']
        display_cols = [c for c in display_cols if c in filtered.columns]
        
        st.dataframe(
            filtered[display_cols],
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("Link"),
                "precio_usd_mep": st.column_config.NumberColumn("Precio USD", format="$%.0f"),
                "opportunity_score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
            }
        )
        
    with tab2:
        st.subheader("Mapa de propiedades")
        
        # Filtrar propiedades con coordenadas
        map_df = filtered.dropna(subset=['lat', 'lng'])
        
        if map_df.empty:
            st.info("No hay propiedades con coordenadas para mostrar en el mapa")
        else:
            # Crear mapa centrado en Palermo
            m = folium.Map(
                location=[-34.5797, -58.4295],  # Palermo
                zoom_start=14,
                tiles='CartoDB dark_matter'
            )
            
            # Agregar markers
            for _, row in map_df.iterrows():
                score = row.get('opportunity_score', 0)
                
                # Color según score
                if score >= 80:
                    color = 'red'
                    icon = 'fire'
                elif score >= 60:
                    color = 'orange'
                    icon = 'home'
                else:
                    color = 'blue'
                    icon = 'home'
                    
                popup_html = f"""
                <b>${row.get('precio_usd_mep', 0):,.0f} USD</b><br>
                {row.get('m2_total', 0)} m² | {row.get('ambientes', 0)} amb<br>
                Score: {score}<br>
                <a href="{row.get('url', '#')}" target="_blank">Ver propiedad</a>
                """
                
                folium.Marker(
                    [row['lat'], row['lng']],
                    popup=folium.Popup(popup_html, max_width=300),
                    icon=folium.Icon(color=color, icon=icon)
                ).add_to(m)
                
            st_folium(m, width=None, height=500)
            
    with tab3:
        st.subheader("Análisis de mercado")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Distribución de precios
            if 'precio_usd_mep' in filtered.columns:
                fig = px.histogram(
                    filtered, 
                    x='precio_usd_mep',
                    nbins=30,
                    title="Distribución de precios"
                )
                fig.update_layout(template='plotly_dark')
                st.plotly_chart(fig, use_container_width=True)
                
        with col2:
            # Precio vs m²
            if all(col in filtered.columns for col in ['m2_total', 'precio_usd_mep']):
                fig = px.scatter(
                    filtered,
                    x='m2_total',
                    y='precio_usd_mep',
                    color='opportunity_score' if 'opportunity_score' in filtered.columns else None,
                    title="Precio vs Superficie",
                    hover_data=['titulo', 'barrio']
                )
                fig.update_layout(template='plotly_dark')
                st.plotly_chart(fig, use_container_width=True)
                
        # Precio por barrio
        if 'barrio' in filtered.columns and 'precio_usd_mep' in filtered.columns:
            barrio_stats = filtered.groupby('barrio').agg({
                'precio_usd_mep': 'mean',
                'url': 'count'
            }).reset_index()
            barrio_stats.columns = ['Barrio', 'Precio promedio', 'Cantidad']
            
            fig = px.bar(
                barrio_stats,
                x='Barrio',
                y='Precio promedio',
                color='Cantidad',
                title="Precio promedio por barrio"
            )
            fig.update_layout(template='plotly_dark')
            st.plotly_chart(fig, use_container_width=True)
            
    with tab4:
        st.subheader("🔥 Top 10 Oportunidades")
        
        if 'opportunity_score' in filtered.columns:
            top_10 = filtered.nlargest(10, 'opportunity_score')
            
            for _, row in top_10.iterrows():
                score = row.get('opportunity_score', 0)
                
                # Card de oportunidad
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.markdown(f"### {row.get('titulo', 'Sin título')[:50]}...")
                        st.markdown(f"📍 {row.get('barrio', 'Palermo')} | {row.get('direccion', '')[:30]}")
                        
                    with col2:
                        st.metric("💰 Precio", f"${row.get('precio_usd_mep', 0):,.0f}")
                        st.metric("📐 Superficie", f"{row.get('m2_total', 0)} m²")
                        
                    with col3:
                        score_color = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"
                        st.metric(f"{score_color} Score", f"{score}/100")
                        
                        if row.get('zscore'):
                            st.metric("📊 Z-Score", f"{row.get('zscore', 0):.2f}")
                            
                    # Keywords
                    keywords = row.get('keywords_detected', '')
                    if keywords:
                        st.markdown(f"🏷️ **Keywords:** {keywords}")
                        
                    # Link
                    st.markdown(f"[🔗 Ver propiedad]({row.get('url', '#')})")
                    st.markdown("---")
        else:
            st.info("Ejecuta el análisis para ver oportunidades")
            
    # Footer
    st.markdown("---")
    st.markdown("Desarrollado para detectar oportunidades inmobiliarias en Palermo, CABA")


if __name__ == "__main__":
    main()
