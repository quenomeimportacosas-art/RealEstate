# Distressed Property Finder 🏠

Sistema automático para detectar oportunidades inmobiliarias en Palermo, CABA.

## ✅ Funcionalidades

- **Scraping automático** de Zonaprop, Argenprop y MercadoLibre
- **Detección de relistings** (propiedades que vuelven a publicarse)
- **Scoring de oportunidades** basado en:
  - Z-Score (precio vs microzona)
  - Bajadas de precio
  - Keywords de urgencia
  - Antigüedad del aviso
- **Dashboard interactivo** con tabla, mapa y gráficos
- **Google Sheets** como base de datos
- **Ejecución automática** cada 6 horas via GitHub Actions

## 🚀 Deploy Gratuito

### Dashboard (Streamlit Cloud)
1. Fork este repo
2. Ve a [share.streamlit.io](https://share.streamlit.io)
3. Conecta tu repo
4. Main file: `dashboard/app.py`
5. Agrega secrets (ver abajo)

### Scraper (GitHub Actions)
1. Ve a Settings > Secrets > Actions
2. Agrega:
   - `GOOGLE_CREDENTIALS`: Contenido JSON del service account
   - `GOOGLE_SHEET_ID`: ID de tu Google Sheet

## 🔐 Secrets para Streamlit Cloud

En Streamlit Cloud, ve a Settings > Secrets y agrega:

```toml
[gcp_service_account]
type = "service_account"
project_id = "tu-proyecto"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."

GOOGLE_SHEET_ID = "tu-sheet-id"
```

## 📊 Uso Local

```bash
pip install -r requirements.txt
playwright install chromium

# Scraping
python main.py --source zonaprop --limit 50

# Dashboard
streamlit run dashboard/app.py
```

## 📁 Estructura

```
├── scrapers/       # Web scraping con Playwright
├── analysis/       # Normalización y scoring
├── data/           # Google Sheets integration
├── alerts/         # Telegram notifications
├── dashboard/      # Streamlit UI
└── main.py         # Orquestador
```
