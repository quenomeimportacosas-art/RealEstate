"""
Scraper para Argenprop
"""
from typing import List, Dict, Optional
from .base_scraper import BaseScraper


class ArgenpropScraper(BaseScraper):
    """Scraper específico para Argenprop"""
    
    BASE_URL = "https://www.argenprop.com"
    SEARCH_URL = f"{BASE_URL}/departamento-venta-barrio-palermo"
    
    async def get_listing_urls(self, max_pages: int = 10) -> List[str]:
        """Obtiene URLs de propiedades de Argenprop"""
        urls = []
        
        for page in range(1, max_pages + 1):
            page_url = f"{self.SEARCH_URL}--pagina-{page}" if page > 1 else self.SEARCH_URL
            
            if not await self.safe_navigate(page_url):
                print(f"[Argenprop] No se pudo cargar página {page}")
                break
                
            try:
                # Selector de cards de propiedades
                cards = await self.page.query_selector_all('.listing__item a.card')
                if not cards:
                    cards = await self.page.query_selector_all('a[href*="/departamento"]')
                
                for card in cards:
                    href = await card.get_attribute('href')
                    if href and '/departamento' in href and '-venta-' in href:
                        full_url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
                        if full_url not in urls:
                            urls.append(full_url)
                            
                print(f"[Argenprop] Página {page}: {len(cards)} propiedades encontradas")
                
                if not cards:
                    break
                    
            except Exception as e:
                print(f"[Argenprop] Error en página {page}: {e}")
                break
                
        return urls
    
    async def extract_property_data(self, url: str) -> Optional[Dict]:
        """Extrae datos de una propiedad de Argenprop"""
        if not await self.safe_navigate(url):
            return None
            
        try:
            data = {
                'source': 'argenprop',
                'url': url,
            }
            
            # ID
            portal_id = url.split('--')[-1] if '--' in url else url.split('/')[-1]
            data['id'] = self.generate_property_id('argenprop', portal_id)
            
            # Título
            title_el = await self.page.query_selector('h1.titlebar__title')
            if title_el:
                data['titulo'] = await title_el.inner_text()
            else:
                data['titulo'] = ''
                
            # Precio
            price_el = await self.page.query_selector('.titlebar__price, .price')
            if price_el:
                price_text = await price_el.inner_text()
                data['precio_original'], data['moneda'] = self.clean_price(price_text)
            else:
                data['precio_original'], data['moneda'] = 0.0, 'USD'
                
            # Expensas
            expensas_el = await self.page.query_selector('.titlebar__expenses')
            if expensas_el:
                expensas_text = await expensas_el.inner_text()
                data['expensas'], _ = self.clean_price(expensas_text)
            else:
                data['expensas'] = 0.0
                
            # Features (metros, ambientes, etc)
            data['m2_total'] = 0.0
            data['m2_cubiertos'] = 0.0
            data['ambientes'] = 0
            data['piso'] = None
            
            features = await self.page.query_selector_all('.property-features li, .property-main-features li')
            for feature in features:
                text = await feature.inner_text()
                text_lower = text.lower()
                
                if 'm²' in text or 'm2' in text or 'metro' in text_lower:
                    if 'total' in text_lower:
                        data['m2_total'] = self.clean_area(text)
                    elif 'cub' in text_lower:
                        data['m2_cubiertos'] = self.clean_area(text)
                    elif data['m2_total'] == 0:
                        data['m2_total'] = self.clean_area(text)
                        
                if 'amb' in text_lower:
                    data['ambientes'] = self.normalize_rooms(text)
                    
            if data['m2_total'] == 0 and data['m2_cubiertos'] > 0:
                data['m2_total'] = data['m2_cubiertos']
                
            # Dirección
            address_el = await self.page.query_selector('.titlebar__address, .location-container')
            if address_el:
                data['direccion'] = await address_el.inner_text()
            else:
                data['direccion'] = 'Palermo'
                
            data['barrio'] = self._extract_barrio(data.get('direccion', '') + ' ' + data.get('titulo', ''))
            
            # Coordenadas
            data['lat'] = None
            data['lng'] = None
            
            # Inmobiliaria
            broker_el = await self.page.query_selector('.publisher__name, .real-estate-data')
            if broker_el:
                data['inmobiliaria'] = await broker_el.inner_text()
            else:
                data['inmobiliaria'] = 'Dueño directo'
                
            # Descripción
            desc_el = await self.page.query_selector('.section-description--content, #description')
            if desc_el:
                data['descripcion'] = await desc_el.inner_text()
            else:
                data['descripcion'] = ''
                
            return data
            
        except Exception as e:
            print(f"[Argenprop] Error extrayendo {url}: {e}")
            return None
            
    def _extract_barrio(self, text: str) -> str:
        """Extrae el barrio específico"""
        barrios = ['palermo soho', 'palermo hollywood', 'palermo chico', 'palermo viejo', 'palermo']
        text_lower = text.lower()
        for barrio in barrios:
            if barrio in text_lower:
                return barrio.title()
        return 'Palermo'
