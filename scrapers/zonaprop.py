"""
Scraper para Zonaprop
"""
from typing import List, Dict, Optional
from .base_scraper import BaseScraper


class ZonapropScraper(BaseScraper):
    """Scraper específico para Zonaprop"""
    
    BASE_URL = "https://www.zonaprop.com.ar"
    SEARCH_URL = f"{BASE_URL}/departamentos-venta-palermo.html"
    
    async def get_listing_urls(self, max_pages: int = 10) -> List[str]:
        """Obtiene URLs de propiedades de Zonaprop"""
        urls = []
        
        for page in range(1, max_pages + 1):
            page_url = f"{self.SEARCH_URL}?pagina={page}" if page > 1 else self.SEARCH_URL
            
            if not await self.safe_navigate(page_url):
                print(f"[Zonaprop] No se pudo cargar página {page}")
                break
            
            # Esperar a que carguen las cards
            try:
                await self.page.wait_for_selector('[data-qa="posting-card"], .posting-card, [data-posting-type]', timeout=10000)
            except:
                print(f"[Zonaprop] Timeout esperando cards en página {page}")
                
            # Extraer links de propiedades - múltiples selectores para robustez
            try:
                # Selectores actualizados para Zonaprop 2026
                selectors = [
                    'a[data-qa="posting-card-link"]',
                    '[data-qa="posting-card"] a',
                    'div[data-posting-type] a[href*="/propiedades/"]',
                    '.posting-card a[href*="/propiedades/"]',
                    'a[href*="/propiedades/"][class*="posting"]',
                ]
                
                links = []
                for selector in selectors:
                    found = await self.page.query_selector_all(selector)
                    if found:
                        links = found
                        print(f"[Zonaprop] Selector exitoso: {selector}")
                        break
                
                # Si no funcionaron los selectores específicos, buscar todos los links a propiedades
                if not links:
                    all_links = await self.page.query_selector_all('a[href*="/propiedades/"]')
                    links = all_links
                    
                for link in links:
                    href = await link.get_attribute('href')
                    if href and '/propiedades/' in href:
                        full_url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
                        if full_url not in urls:
                            urls.append(full_url)
                            
                print(f"[Zonaprop] Página {page}: {len(links)} links, {len(urls)} URLs únicas")
                
                # Si no hay propiedades, terminamos
                if not links:
                    break
                    
            except Exception as e:
                print(f"[Zonaprop] Error en página {page}: {e}")
                break
                
        return urls
    
    async def extract_property_data(self, url: str) -> Optional[Dict]:
        """Extrae datos de una propiedad de Zonaprop"""
        if not await self.safe_navigate(url):
            return None
            
        try:
            data = {
                'source': 'zonaprop',
                'url': url,
            }
            
            # ID del portal (extraer de URL)
            portal_id = url.split('/')[-1].split('.')[0].split('-')[-1]
            data['id'] = self.generate_property_id('zonaprop', portal_id)
            
            # Título
            title_el = await self.page.query_selector('h1, .title-property')
            if title_el:
                data['titulo'] = await title_el.inner_text()
            else:
                data['titulo'] = ''
                
            # Precio
            price_el = await self.page.query_selector('.price-value, [data-qa="POSTING_PRICE"]')
            if price_el:
                price_text = await price_el.inner_text()
                data['precio_original'], data['moneda'] = self.clean_price(price_text)
            else:
                data['precio_original'], data['moneda'] = 0.0, 'USD'
                
            # Expensas
            expensas_el = await self.page.query_selector('.expenses, [data-qa="expensas"]')
            if expensas_el:
                expensas_text = await expensas_el.inner_text()
                data['expensas'], _ = self.clean_price(expensas_text)
            else:
                data['expensas'] = 0.0
                
            # Metros y ambientes
            features = await self.page.query_selector_all('.detail-feature, .property-features li')
            data['m2_total'] = 0.0
            data['m2_cubiertos'] = 0.0
            data['ambientes'] = 0
            data['piso'] = None
            
            for feature in features:
                text = await feature.inner_text()
                text_lower = text.lower()
                
                if 'm²' in text or 'm2' in text:
                    if 'total' in text_lower:
                        data['m2_total'] = self.clean_area(text)
                    elif 'cubierto' in text_lower or 'cub' in text_lower:
                        data['m2_cubiertos'] = self.clean_area(text)
                    elif data['m2_total'] == 0:
                        data['m2_total'] = self.clean_area(text)
                        
                if 'amb' in text_lower:
                    data['ambientes'] = self.normalize_rooms(text)
                    
                if 'piso' in text_lower:
                    import re
                    piso_match = re.search(r'(\d+)', text)
                    if piso_match:
                        data['piso'] = int(piso_match.group(1))
                        
            # Si solo tenemos cubiertos, usar como total
            if data['m2_total'] == 0 and data['m2_cubiertos'] > 0:
                data['m2_total'] = data['m2_cubiertos']
                
            # Dirección
            address_el = await self.page.query_selector('.address, .title-location')
            if address_el:
                data['direccion'] = await address_el.inner_text()
            else:
                data['direccion'] = 'Palermo'
                
            # Barrio (extraer de dirección o título)
            data['barrio'] = self._extract_barrio(data.get('direccion', '') + ' ' + data.get('titulo', ''))
            
            # Coordenadas (intentar extraer del mapa)
            data['lat'] = None
            data['lng'] = None
            try:
                # Buscar en scripts o atributos del mapa
                map_el = await self.page.query_selector('[data-lat], .map-container')
                if map_el:
                    lat = await map_el.get_attribute('data-lat')
                    lng = await map_el.get_attribute('data-lng')
                    if lat and lng:
                        data['lat'] = float(lat)
                        data['lng'] = float(lng)
            except:
                pass
                
            # Inmobiliaria
            broker_el = await self.page.query_selector('.publisher-name, .real-estate-name')
            if broker_el:
                data['inmobiliaria'] = await broker_el.inner_text()
            else:
                data['inmobiliaria'] = 'Dueño directo'
                
            # Descripción
            desc_el = await self.page.query_selector('.description-content, #description')
            if desc_el:
                data['descripcion'] = await desc_el.inner_text()
            else:
                data['descripcion'] = ''
                
            return data
            
        except Exception as e:
            print(f"[Zonaprop] Error extrayendo {url}: {e}")
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
