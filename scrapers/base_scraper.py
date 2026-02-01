"""
Base Scraper con anti-detection y manejo de errores
"""
import asyncio
import random
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser
from playwright_stealth import Stealth
from fake_useragent import UserAgent

import sys
sys.path.append('..')
from config.settings import (
    REQUEST_DELAY_MIN, 
    REQUEST_DELAY_MAX, 
    MAX_RETRIES,
    HEADLESS
)


class BaseScraper(ABC):
    """Clase base para todos los scrapers de portales inmobiliarios"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.results: List[Dict] = []
        
    async def __aenter__(self):
        await self.init_browser()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_browser()
        
    async def init_browser(self):
        """Inicializa Playwright con stealth mode"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=HEADLESS,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        context = await self.browser.new_context(
            user_agent=self.ua.random,
            viewport={'width': 1920, 'height': 1080},
            locale='es-AR',
            timezone_id='America/Argentina/Buenos_Aires',
        )
        self.page = await context.new_page()
        # Aplicar stealth
        stealth = Stealth()
        await stealth.apply_stealth_async(self.page)
        
    async def close_browser(self):
        """Cierra el navegador"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def random_delay(self):
        """Delay aleatorio para parecer humano"""
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        await asyncio.sleep(delay)
        
    async def safe_navigate(self, url: str, retries: int = MAX_RETRIES) -> bool:
        """Navega a una URL con reintentos"""
        for attempt in range(retries):
            try:
                await self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
                await self.random_delay()
                return True
            except Exception as e:
                print(f"[Attempt {attempt + 1}/{retries}] Error navegando a {url}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))  # Backoff exponencial
        return False
    
    def generate_property_id(self, source: str, portal_id: str) -> str:
        """Genera un ID único para la propiedad"""
        raw = f"{source}_{portal_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    
    def clean_price(self, price_text: str) -> tuple[float, str]:
        """
        Limpia el texto del precio y extrae valor + moneda
        Returns: (precio_float, moneda)
        """
        import re
        
        price_text = price_text.upper().strip()
        
        # Detectar moneda
        if 'USD' in price_text or 'U$S' in price_text or 'US$' in price_text:
            currency = 'USD'
        else:
            currency = 'ARS'
            
        # Extraer número
        numbers = re.findall(r'[\d.,]+', price_text)
        if not numbers:
            return 0.0, currency
            
        price_str = numbers[0].replace('.', '').replace(',', '.')
        try:
            price = float(price_str)
        except ValueError:
            price = 0.0
            
        return price, currency
    
    def normalize_rooms(self, rooms_text: str) -> int:
        """Normaliza texto de ambientes a número"""
        import re
        
        rooms_text = rooms_text.lower().strip()
        
        # Patrones comunes
        patterns = [
            r'(\d+)\s*amb',
            r'(\d+)\s*ambiente',
            r'monoambiente',
            r'mono',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, rooms_text)
            if match:
                if 'mono' in pattern:
                    return 1
                return int(match.group(1))
                
        # Texto a número
        text_to_num = {
            'un': 1, 'uno': 1, 'una': 1,
            'dos': 2,
            'tres': 3,
            'cuatro': 4,
            'cinco': 5,
            'seis': 6,
        }
        
        for word, num in text_to_num.items():
            if word in rooms_text:
                return num
                
        return 0
    
    def clean_area(self, area_text: str) -> float:
        """Extrae metros cuadrados del texto"""
        import re
        
        # Buscar número antes de m², m2, mts, metros
        match = re.search(r'([\d.,]+)\s*(?:m²|m2|mts|metros)', area_text.lower())
        if match:
            area_str = match.group(1).replace('.', '').replace(',', '.')
            try:
                return float(area_str)
            except ValueError:
                pass
        return 0.0
    
    @abstractmethod
    async def get_listing_urls(self, max_pages: int = 10) -> List[str]:
        """Obtiene URLs de propiedades listadas"""
        pass
    
    @abstractmethod
    async def extract_property_data(self, url: str) -> Optional[Dict]:
        """Extrae datos de una propiedad individual"""
        pass
    
    async def scrape(self, limit: int = 100) -> List[Dict]:
        """
        Ejecuta el scraping completo
        Args:
            limit: Número máximo de propiedades a extraer
        Returns:
            Lista de diccionarios con datos de propiedades
        """
        print(f"[{self.__class__.__name__}] Iniciando scraping...")
        
        # Obtener URLs
        urls = await self.get_listing_urls()
        urls = urls[:limit]
        print(f"[{self.__class__.__name__}] Encontradas {len(urls)} propiedades")
        
        # Extraer datos de cada propiedad
        for i, url in enumerate(urls, 1):
            print(f"[{self.__class__.__name__}] Procesando {i}/{len(urls)}: {url[:50]}...")
            
            data = await self.extract_property_data(url)
            if data:
                data['first_seen'] = datetime.now().isoformat()
                data['last_seen'] = datetime.now().isoformat()
                data['status'] = 'active'
                self.results.append(data)
                
            await self.random_delay()
            
        print(f"[{self.__class__.__name__}] Scraping completado: {len(self.results)} propiedades extraídas")
        return self.results
