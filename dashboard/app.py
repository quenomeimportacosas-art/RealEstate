"""
Dashboard de oportunidades inmobiliarias con Streamlit
Soporta ejecución local y en Streamlit Cloud
"""
import streamlit as st
import pandas as pd
import os
import json

# Configuración de página - DEBE SER LO PRIMERO
st.set_page_config(
    page_title="🏠 Distressed Property Finder",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)


def get_credentials_from_streamlit():
    """Obtiene credenciales desde Streamlit secrets"""
    try:
        if hasattr(st, 'secrets'):
            # Verificar si hay secrets configurados
            if 'GOOGLE_CREDENTIALS' in st.secrets:
                return dict(st.secrets['GOOGLE_CREDENTIALS']), st.secrets.get('GOOGLE_SHEET_ID', '')
            elif 'gcp_service_account' in st.secrets:
                return dict(st.secrets['gcp_service_account']), st.secrets.get('GOOGLE_SHEET_ID', '')
    except Exception as e:
        st.warning(f"No se pudieron cargar secrets: {e}")
    return None, None


def load_data():
    """Carga datos de Google Sheets"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    try:
        # Intentar obtener credenciales de Streamlit Cloud
        creds_dict, sheet_id = get_credentials_from_streamlit()
        
        if creds_dict:
            # Modo Streamlit Cloud
            os.environ['GOOGLE_CREDENTIALS'] = json.dumps(creds_dict)
            if sheet_id:
                os.environ['GOOGLE_SHEET_ID'] = sheet_id
                
        from data.sheets_db import GoogleSheetsDB
        
        db = GoogleSheetsDB()
        if db.connect():
            return db.to_dataframe()
            
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        
    return pd.DataFrame()


def show_config_instructions():
    """Muestra instrucciones de configuración"""
    st.warning("⚠️ No hay datos disponibles o faltan credenciales")
    
    with st.expander("📋 Instrucciones de configuración", expanded=True):
        st.markdown("""
        ### Para Streamlit Cloud:
        
        1. Ve a **Settings** → **Secrets**
        2. Agrega este contenido (reemplazando con tus datos):
        
        ```toml
        GOOGLE_SHEET_ID = "tu-sheet-id"
        
        [GOOGLE_CREDENTIALS]
        type = "service_account"
        project_id = "tu-proyecto"
        private_key_id = "xxx"
        private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
        client_email = "xxx@xxx.iam.gserviceaccount.com"
        client_id = "123456789"
        auth_uri = "https://accounts.google.com/o/oauth2/auth"
        token_uri = "https://oauth2.googleapis.com/token"
        ```
        
        ### Para ejecución local:
        
        1. Guarda `credentials.json` en `config/`
        2. Configura `GOOGLE_SHEET_ID` en `config/settings.py`
        3. Ejecuta: `python main.py --source zonaprop --limit 50`
        """)


def main():
    st.title("🏠 Distressed Property Finder - Palermo")
    st.markdown("### Sistema de detección de oportunidades inmobiliarias")
    
    # Cargar datos
    df = load_data()
    
    if df.empty:
        show_config_instructions()
        return
        
    # Sidebar - Filtros
    st.sidebar.header("🔍 Filtros")
    
    # Asegurar tipos
    numeric_cols = ['precio_usd_mep', 'm2_total', 'ambientes', 'opportunity_score', 'zscore']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    # Filtros
    min_score = st.sidebar.slider("Score mínimo", 0, 100, 0)
    max_price = st.sidebar.number_input("Precio máximo USD", value=500000, step=50000)
    min_m2 = st.sidebar.slider("m² mínimo", 0, 200, 0)
    
    if 'barrio' in df.columns:
        barrios = ['Todos'] + sorted(df['barrio'].dropna().unique().tolist())
        selected_barrio = st.sidebar.selectbox("Barrio", barrios)
    else:
        selected_barrio = 'Todos'
    
    # Aplicar filtros
    filtered = df.copy()
    
    if 'opportunity_score' in filtered.columns:
        filtered = filtered[filtered['opportunity_score'] >= min_score]
    if 'precio_usd_mep' in filtered.columns:
        filtered = filtered[filtered['precio_usd_mep'] <= max_price]
    if 'm2_total' in filtered.columns:
        filtered = filtered[filtered['m2_total'] >= min_m2]
    if selected_barrio != 'Todos' and 'barrio' in filtered.columns:
        filtered = filtered[filtered['barrio'] == selected_barrio]
        
    # Métricas principales
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🏠 Propiedades", len(filtered))
    with col2:
        avg_price = filtered['precio_usd_mep'].mean() if 'precio_usd_mep' in filtered.columns else 0
        st.metric("💰 Precio promedio", f"${avg_price:,.0f}" if pd.notna(avg_price) else "$0")
    with col3:
        avg_m2 = filtered['m2_total'].mean() if 'm2_total' in filtered.columns else 0
        st.metric("📐 m² promedio", f"{avg_m2:.0f}" if pd.notna(avg_m2) else "0")
    with col4:
        if 'opportunity_score' in filtered.columns:
            opp_count = len(filtered[filtered['opportunity_score'] >= 60])
        else:
            opp_count = 0
        st.metric("🎯 Oportunidades", opp_count)
        
    # Tabs principales
    tab1, tab2, tab3 = st.tabs(["📋 Tabla", "📊 Análisis", "🔥 Top Oportunidades"])
    
    with tab1:
        st.subheader("Propiedades")
        
        # Ordenar por score si existe
        if 'opportunity_score' in filtered.columns:
            filtered = filtered.sort_values('opportunity_score', ascending=False)
            
        # Columnas a mostrar
        display_cols = ['titulo', 'precio_usd_mep', 'm2_total', 'ambientes', 'barrio', 
                       'opportunity_score', 'url']
        display_cols = [c for c in display_cols if c in filtered.columns]
        
        if display_cols:
            st.dataframe(
                filtered[display_cols],
                use_container_width=True,
                column_config={
                    "url": st.column_config.LinkColumn("Link"),
                    "precio_usd_mep": st.column_config.NumberColumn("Precio USD", format="$%.0f"),
                }
            )
        else:
            st.dataframe(filtered)
        
    with tab2:
        st.subheader("Análisis de mercado")
        
        if 'precio_usd_mep' in filtered.columns and len(filtered) > 0:
            import plotly.express as px
            
            fig = px.histogram(
                filtered, 
                x='precio_usd_mep',
                nbins=20,
                title="Distribución de precios"
            )
            fig.update_layout(template='plotly_dark')
            st.plotly_chart(fig, use_container_width=True)
            
            if 'm2_total' in filtered.columns:
                fig = px.scatter(
                    filtered,
                    x='m2_total',
                    y='precio_usd_mep',
                    color='opportunity_score' if 'opportunity_score' in filtered.columns else None,
                    title="Precio vs Superficie"
                )
                fig.update_layout(template='plotly_dark')
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos suficientes para mostrar análisis")
            
    with tab3:
        st.subheader("🔥 Top Oportunidades")
        
        if 'opportunity_score' in filtered.columns and len(filtered) > 0:
            top_5 = filtered.nlargest(5, 'opportunity_score')
            
            for _, row in top_5.iterrows():
                score = row.get('opportunity_score', 0)
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    titulo = str(row.get('titulo', 'Sin título'))[:60]
                    st.markdown(f"**{titulo}**")
                    precio = row.get('precio_usd_mep', 0)
                    m2 = row.get('m2_total', 0)
                    st.write(f"💰 ${precio:,.0f} | 📐 {m2} m²")
                    
                with col2:
                    score_emoji = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"
                    st.metric(f"{score_emoji} Score", f"{score:.0f}")
                    
                url = row.get('url', '')
                if url:
                    st.markdown(f"[🔗 Ver propiedad]({url})")
                st.markdown("---")
        else:
            st.info("Ejecuta el scraper para ver oportunidades")
            
    # Footer
    st.markdown("---")
    st.caption("Distressed Property Finder - Palermo, CABA")


if __name__ == "__main__":
    main()
