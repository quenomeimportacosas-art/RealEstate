"""
Scraper para Zonaprop - Extrae datos desde lista de resultados
Zonaprop carga precios con JS, así que extraemos desde las cards de lista
"""
import re
import asyncio
from typing import List, Dict, Optional
from .base_scraper import BaseScraper


class ZonapropScraper(BaseScraper):
    """Scraper específico para Zonaprop - extrae desde lista"""
    
    BASE_URL = "https://www.zonaprop.com.ar"
    SEARCH_URL = f"{BASE_URL}/departamentos-venta-palermo.html"
    
    async def get_listing_urls(self, max_pages: int = 10) -> List[str]:
        """Obtiene URLs (solo para compatibilidad)"""
        return []  # No usado - usamos scrape_from_list
    
    async def extract_property_data(self, url: str) -> Optional[Dict]:
        """No usado - extraemos desde lista"""
        return None
    
    async def scrape(self, limit: int = 100) -> List[Dict]:
        """
        Scraping desde lista de resultados (más rápido y confiable)
        """
        print(f"[{self.__class__.__name__}] Iniciando scraping...")
        
        properties_extracted = 0
        page = 1
        
        while properties_extracted < limit:
            page_url = f"{self.SEARCH_URL}?pagina={page}" if page > 1 else self.SEARCH_URL
            
            if not await self.safe_navigate(page_url):
                print(f"[Zonaprop] No se pudo cargar página {page}")
                break
            
            # Esperar a que carguen las cards
            try:
                await self.page.wait_for_selector('[data-qa="posting-card"], [data-posting-type]', timeout=15000)
                await asyncio.sleep(2)  # Esperar a que cargue JS
            except:
                print(f"[Zonaprop] Timeout esperando cards")
                break
            
            # Extraer todas las cards de la página
            cards = await self.page.query_selector_all('[data-posting-type], [data-qa="posting-card"]')
            
            if not cards:
                print(f"[Zonaprop] No se encontraron cards en página {page}")
                break
            
            print(f"[Zonaprop] Página {page}: {len(cards)} cards encontradas")
            
            for card in cards:
                if properties_extracted >= limit:
                    break
                    
                try:
                    data = await self._extract_from_card(card)
                    if data and data.get('precio_original', 0) > 0:
                        from datetime import datetime
                        data['first_seen'] = datetime.now().isoformat()
                        data['last_seen'] = datetime.now().isoformat()
                        data['status'] = 'active'
                        self.results.append(data)
                        properties_extracted += 1
                        print(f"[Zonaprop] Extraído: ${data['precio_original']:,.0f} {data['moneda']}, {data['m2_total']}m², {data['ambientes']} amb")
                except Exception as e:
                    print(f"[Zonaprop] Error en card: {e}")
                    continue
            
            # Siguiente página
            page += 1
            if page > 10:  # Máximo 10 páginas
                break
            
            await asyncio.sleep(2)
        
        print(f"[{self.__class__.__name__}] Scraping completado: {len(self.results)} propiedades extraídas")
        return self.results
    
    async def _extract_from_card(self, card) -> Optional[Dict]:
        """Extrae datos de una card de la lista"""
        try:
            data = {'source': 'zonaprop'}
            
            # URL y ID
            link = await card.query_selector('a[href*="/propiedades/"]')
            if link:
                href = await link.get_attribute('href')
                url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
                data['url'] = url
                # ID del portal
                portal_id = url.split('/')[-1].split('.')[0].split('-')[-1]
                data['id'] = self.generate_property_id('zonaprop', portal_id)
            else:
                return None
            
            # HTML completo de la card para debug
            card_html = await card.inner_html()
            card_text = await card.inner_text()
            
            # === PRECIO ===
            # Intentar selectores primero
            price_selectors = [
                '[data-qa="POSTING_CARD_PRICE"]',
                '[class*="price"]',
                'span[class*="Price"]',
            ]
            
            price_text = ''
            for selector in price_selectors:
                el = await card.query_selector(selector)
                if el:
                    price_text = await el.inner_text()
                    if price_text and ('U$S' in price_text or 'USD' in price_text or '$' in price_text):
                        break
            
            # Si no, buscar en el HTML con regex
            if not price_text or not any(c.isdigit() for c in price_text):
                # Buscar patrón de precio
                patterns = [
                    r'U\$[Ss]?\s*([\d.]+)',
                    r'USD\s*([\d.]+)',
                    r'\$\s*([\d.]+)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, card_html)
                    if match:
                        price_text = f"USD {match.group(1)}"
                        break
            
            data['precio_original'], data['moneda'] = self.clean_price(price_text)
            
            # === CARACTERÍSTICAS (m², ambientes) ===
            data['m2_total'] = 0.0
            data['m2_cubiertos'] = 0.0
            data['ambientes'] = 0
            data['piso'] = None
            
            # Buscar m² en el texto
            m2_match = re.search(r'(\d+)\s*m²', card_text, re.IGNORECASE)
            if m2_match:
                data['m2_total'] = float(m2_match.group(1))
            
            # Buscar ambientes
            amb_match = re.search(r'(\d+)\s*amb', card_text, re.IGNORECASE)
            if amb_match:
                data['ambientes'] = int(amb_match.group(1))
            elif 'monoambiente' in card_text.lower() or 'mono' in card_text.lower():
                data['ambientes'] = 1
            
            # === TÍTULO ===
            title_el = await card.query_selector('a[href*="/propiedades/"] h2, [data-qa="POSTING_CARD_TITLE"]')
            if title_el:
                data['titulo'] = await title_el.inner_text()
            else:
                # Extraer primera línea significativa
                lines = [l.strip() for l in card_text.split('\n') if l.strip() and len(l.strip()) > 10]
                data['titulo'] = lines[0] if lines else 'Sin título'
            
            # === UBICACIÓN ===
            location_el = await card.query_selector('[data-qa="POSTING_CARD_LOCATION"], [class*="location"]')
            if location_el:
                data['direccion'] = await location_el.inner_text()
            else:
                data['direccion'] = 'Palermo'
            
            # Barrio
            data['barrio'] = self._extract_barrio(data.get('direccion', '') + ' ' + data.get('titulo', ''))
            
            # === EXPENSAS ===
            expensas_match = re.search(r'(\d+)\s*(?:expensas|exp)', card_text, re.IGNORECASE)
            if expensas_match:
                data['expensas'] = float(expensas_match.group(1))
            else:
                data['expensas'] = 0.0
            
            # Campos adicionales
            data['lat'] = None
            data['lng'] = None
            data['inmobiliaria'] = 'Zonaprop'
            data['descripcion'] = ''
            
            return data
            
        except Exception as e:
            print(f"[Zonaprop] Error extrayendo card: {e}")
            return None
    
    def _extract_barrio(self, text: str) -> str:
        """Extrae el barrio específico del texto"""
        barrios = [
            'palermo soho',
            'palermo hollywood',
            'palermo chico',
            'palermo viejo',
            'palermo nuevo',
            'palermo botanico',
            'palermo',
        ]
        
        text_lower = text.lower()
        for barrio in barrios:
            if barrio in text_lower:
                return barrio.title()
                
        return 'Palermo'
