"""
Orquestador principal del Distressed Property Finder
"""
import asyncio
import argparse
from datetime import datetime
from typing import List, Dict

# Scrapers
from scrapers.zonaprop import ZonapropScraper
from scrapers.argenprop import ArgenpropScraper
from scrapers.mercadolibre import MercadoLibreScraper

# Analysis
from analysis.normalizer import normalize_property, get_dolar_mep
from analysis.relisting_detector import detect_relistings
from analysis.microzone_calculator import calculate_all_microzones
from analysis.opportunity_scorer import score_all_properties

# Data & Alerts
from data.sheets_db import GoogleSheetsDB
from alerts.telegram_bot import TelegramAlerts

from config.settings import OPPORTUNITY_SCORE_THRESHOLD


SCRAPERS = {
    'zonaprop': ZonapropScraper,
    'argenprop': ArgenpropScraper,
    'mercadolibre': MercadoLibreScraper,
}


async def run_scraper(source: str, limit: int = 100) -> List[Dict]:
    """
    Ejecuta un scraper específico
    
    Args:
        source: Nombre del portal (zonaprop, argenprop, mercadolibre)
        limit: Máximo de propiedades a extraer
        
    Returns:
        Lista de propiedades extraídas
    """
    if source not in SCRAPERS:
        print(f"[Error] Fuente desconocida: {source}")
        print(f"Fuentes disponibles: {', '.join(SCRAPERS.keys())}")
        return []
        
    scraper_class = SCRAPERS[source]
    
    async with scraper_class() as scraper:
        properties = await scraper.scrape(limit=limit)
        
    return properties


async def run_all_scrapers(limit: int = 50) -> List[Dict]:
    """Ejecuta todos los scrapers"""
    all_properties = []
    
    for source in SCRAPERS.keys():
        print(f"\n{'='*50}")
        print(f"Ejecutando scraper: {source}")
        print('='*50)
        
        properties = await run_scraper(source, limit=limit)
        all_properties.extend(properties)
        
        # Delay entre scrapers
        await asyncio.sleep(5)
        
    return all_properties


def process_properties(
    properties: List[Dict],
    historical: List[Dict] = None,
    dolar_mep: float = None
) -> List[Dict]:
    """
    Procesa propiedades: normalización, relisting, microzones, scoring
    
    Args:
        properties: Propiedades crudas del scraping
        historical: Propiedades históricas para detección de relisting
        dolar_mep: Cotización del dólar MEP
        
    Returns:
        Propiedades procesadas con scores
    """
    if not properties:
        return []
        
    print(f"\n🔄 Procesando {len(properties)} propiedades...")
    
    # 1. Obtener dólar MEP
    if dolar_mep is None:
        dolar_mep = get_dolar_mep()
        print(f"💵 Dólar MEP: ${dolar_mep:,.0f}")
        
    # 2. Normalizar
    print("📐 Normalizando datos...")
    normalized = [normalize_property(p, dolar_mep) for p in properties]
    
    # 3. Detectar relistings
    if historical:
        print(f"🔍 Detectando relistings contra {len(historical)} propiedades históricas...")
        normalized = detect_relistings(normalized, historical)
    else:
        print("⚠️ Sin datos históricos para detectar relistings")
        
    # 4. Calcular microzones
    print("📍 Calculando estadísticas por microzona...")
    with_microzones = calculate_all_microzones(normalized)
    
    # 5. Scoring
    print("🎯 Calculando scores de oportunidad...")
    scored = score_all_properties(with_microzones)
    
    return scored


async def main_async(args):
    """Función principal async"""
    print("\n" + "="*60)
    print("🏠 DISTRESSED PROPERTY FINDER - PALERMO")
    print("="*60)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Conectar a Google Sheets
    print("\n📊 Conectando a Google Sheets...")
    db = GoogleSheetsDB()
    
    if not db.connect():
        print("❌ No se pudo conectar a Google Sheets")
        print("   Verifica que credentials.json existe y el Sheet ID está configurado")
        return
        
    # Obtener datos históricos
    try:
        historical = db.get_historical_properties()
        print(f"📚 Cargadas {len(historical)} propiedades históricas")
    except:
        historical = []
        
    # Ejecutar scrapers
    if args.source == 'all':
        properties = await run_all_scrapers(limit=args.limit)
    else:
        properties = await run_scraper(args.source, limit=args.limit)
        
    if not properties:
        print("❌ No se obtuvieron propiedades")
        return
        
    # Procesar
    processed = process_properties(properties, historical)
    
    # Guardar en Google Sheets
    print(f"\n💾 Guardando {len(processed)} propiedades en Google Sheets...")
    db.upsert_properties(processed)
    
    # Detectar propiedades delistadas
    existing_ids = {p['id'] for p in db.get_all_properties()}
    scraped_ids = {p['id'] for p in processed}
    delisted_ids = existing_ids - scraped_ids
    
    if delisted_ids:
        print(f"📤 Marcando {len(delisted_ids)} propiedades como delistadas")
        db.mark_delisted(list(delisted_ids))
        
    # Enviar alertas
    opportunities = [p for p in processed if p.get('opportunity_score', 0) >= OPPORTUNITY_SCORE_THRESHOLD]
    
    if opportunities and args.notify:
        print(f"\n📲 Enviando {len(opportunities)} alertas por Telegram...")
        telegram = TelegramAlerts()
        if telegram.is_configured():
            await telegram.send_opportunities_batch(opportunities)
        else:
            print("⚠️ Telegram no configurado. Define TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID")
            
    # Resumen
    print("\n" + "="*60)
    print("📊 RESUMEN")
    print("="*60)
    print(f"✅ Propiedades extraídas: {len(properties)}")
    print(f"✅ Propiedades procesadas: {len(processed)}")
    print(f"🎯 Oportunidades detectadas: {len(opportunities)}")
    
    if opportunities:
        avg_score = sum(p['opportunity_score'] for p in opportunities) / len(opportunities)
        print(f"📈 Score promedio de oportunidades: {avg_score:.1f}")
        
        print("\n🔥 Top 5 oportunidades:")
        top_5 = sorted(opportunities, key=lambda x: x['opportunity_score'], reverse=True)[:5]
        for i, prop in enumerate(top_5, 1):
            print(f"  {i}. Score {prop['opportunity_score']}: ${prop.get('precio_usd_mep', 0):,.0f} - {prop.get('url', 'N/A')[:50]}")
            
    print("\n✨ Proceso completado!")
    print(f"🖥️ Ejecuta: streamlit run dashboard/app.py")


def main():
    """Entry point"""
    parser = argparse.ArgumentParser(description='Distressed Property Finder')
    parser.add_argument(
        '--source', 
        type=str, 
        default='zonaprop',
        choices=['zonaprop', 'argenprop', 'mercadolibre', 'all'],
        help='Fuente de scraping'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Límite de propiedades a extraer'
    )
    parser.add_argument(
        '--notify',
        action='store_true',
        help='Enviar alertas por Telegram'
    )
    
    args = parser.parse_args()
    
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
