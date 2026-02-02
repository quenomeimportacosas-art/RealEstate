"""
Configuración general del proyecto
"""
import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "config" / "credentials.json"
LOGS_PATH = PROJECT_ROOT / "logs"

# Google Sheets
GOOGLE_SHEET_ID = "1JEk-j5IcAgx7EbsYzVIOLmPTp5ZRG7LtTE3zif1nNUk"  # Tu Sheet
SHEET_PROPIEDADES = "propiedades"
SHEET_HISTORIAL = "historial_precios"
SHEET_MICROZONES = "microzones"

# Telegram Bot
TELEGRAM_BOT_TOKEN = ""  # <-- Pegar token del bot aquí
TELEGRAM_CHAT_ID = ""    # <-- Pegar chat ID aquí

# Scraping
REQUEST_DELAY_MIN = 3  # segundos
REQUEST_DELAY_MAX = 8  # segundos
MAX_RETRIES = 3
HEADLESS = True  # False para ver el navegador

# Análisis
MICROZONE_RADIUS_METERS = 400
ZSCORE_THRESHOLD = -1.5  # Propiedades con Z < -1.5 son outliers
OPPORTUNITY_SCORE_THRESHOLD = 30  # Score mínimo para alertar (30+ = oportunidad)

# Geocoding
DEFAULT_CITY = "Palermo, Buenos Aires, Argentina"

# Dólar MEP (actualizar manualmente o usar API)
DOLAR_MEP = 1150.0  # Pesos por dólar MEP
