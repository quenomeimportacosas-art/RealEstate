"""
Scraper para Mercado Libre Inmuebles
"""
from typing import List, Dict, Optional
from .base_scraper import BaseScraper


class MercadoLibreScraper(BaseScraper):
    """Scraper específico para Mercado Libre Inmuebles"""
    
    BASE_URL = "https://inmuebles.mercadolibre.com.ar"
    SEARCH_URL = f"{BASE_URL}/departamentos/venta/capital-federal/palermo/"
    
    async def get_listing_urls(self, max_pages: int = 10) -> List[str]:
        """Obtiene URLs de propiedades de ML Inmuebles"""
        urls = []
        offset = 0
        
        for page in range(1, max_pages + 1):
            page_url = f"{self.SEARCH_URL}_Desde_{offset + 1}" if page > 1 else self.SEARCH_URL
            
            if not await self.safe_navigate(page_url):
                print(f"[MercadoLibre] No se pudo cargar página {page}")
                break
                
            try:
                # Selectores de ML
                items = await self.page.query_selector_all('.ui-search-layout__item a.ui-search-link')
                if not items:
                    items = await self.page.query_selector_all('a[href*="MLA"]')
                
                for item in items:
                    href = await item.get_attribute('href')
                    if href and 'MLA' in href:
                        # Limpiar URL de tracking parameters
                        clean_url = href.split('?')[0] if '?' in href else href
                        if clean_url not in urls:
                            urls.append(clean_url)
                            
                print(f"[MercadoLibre] Página {page}: {len(items)} propiedades encontradas")
                
                if not items:
                    break
                    
                offset += 48  # ML muestra 48 por página
                
            except Exception as e:
                print(f"[MercadoLibre] Error en página {page}: {e}")
                break
                
        return urls
    
    async def extract_property_data(self, url: str) -> Optional[Dict]:
        """Extrae datos de una propiedad de ML"""
        if not await self.safe_navigate(url):
            return None
            
        try:
            data = {
                'source': 'mercadolibre',
                'url': url,
            }
            
            # ID (MLA-XXXXXXX)
            import re
            mla_match = re.search(r'MLA-?(\d+)', url)
            portal_id = mla_match.group(1) if mla_match else url.split('/')[-1]
            data['id'] = self.generate_property_id('mercadolibre', portal_id)
            
            # Título
            title_el = await self.page.query_selector('h1.ui-pdp-title')
            if title_el:
                data['titulo'] = await title_el.inner_text()
            else:
                data['titulo'] = ''
                
            # Precio
            price_el = await self.page.query_selector('.andes-money-amount__fraction')
            currency_el = await self.page.query_selector('.andes-money-amount__currency-symbol')
            
            if price_el:
                price_text = await price_el.inner_text()
                currency_text = await currency_el.inner_text() if currency_el else 'USD'
                
                # Limpiar precio
                price_clean = price_text.replace('.', '').replace(',', '.')
                try:
                    data['precio_original'] = float(price_clean)
                except:
                    data['precio_original'] = 0.0
                    
                data['moneda'] = 'USD' if 'U$S' in currency_text or 'USD' in currency_text else 'ARS'
            else:
                data['precio_original'], data['moneda'] = 0.0, 'USD'
                
            data['expensas'] = 0.0  # ML no siempre muestra expensas separadas
            
            # Features
            data['m2_total'] = 0.0
            data['m2_cubiertos'] = 0.0
            data['ambientes'] = 0
            data['piso'] = None
            
            # Tabla de atributos de ML
            rows = await self.page.query_selector_all('.andes-table__row, .ui-pdp-specs__table tr')
            for row in rows:
                text = await row.inner_text()
                text_lower = text.lower()
                
                if 'superficie total' in text_lower or 'metros' in text_lower:
                    data['m2_total'] = self.clean_area(text)
                elif 'superficie cubierta' in text_lower:
                    data['m2_cubiertos'] = self.clean_area(text)
                elif 'ambientes' in text_lower or 'dormitorios' in text_lower:
                    data['ambientes'] = self.normalize_rooms(text)
                    
            if data['m2_total'] == 0 and data['m2_cubiertos'] > 0:
                data['m2_total'] = data['m2_cubiertos']
                
            # Ubicación
            location_el = await self.page.query_selector('.ui-pdp-media__title, .ui-vip-location')
            if location_el:
                data['direccion'] = await location_el.inner_text()
            else:
                data['direccion'] = 'Palermo'
                
            data['barrio'] = self._extract_barrio(data.get('direccion', '') + ' ' + data.get('titulo', ''))
            
            data['lat'] = None
            data['lng'] = None
            
            # Vendedor
            seller_el = await self.page.query_selector('.ui-pdp-seller__header__title')
            if seller_el:
                data['inmobiliaria'] = await seller_el.inner_text()
            else:
                data['inmobiliaria'] = 'Particular'
                
            # Descripción
            desc_el = await self.page.query_selector('.ui-pdp-description__content')
            if desc_el:
                data['descripcion'] = await desc_el.inner_text()
            else:
                data['descripcion'] = ''
                
            return data
            
        except Exception as e:
            print(f"[MercadoLibre] Error extrayendo {url}: {e}")
            return None
            
    def _extract_barrio(self, text: str) -> str:
        """Extrae el barrio específico"""
        barrios = ['palermo soho', 'palermo hollywood', 'palermo chico', 'palermo viejo', 'palermo']
        text_lower = text.lower()
        for barrio in barrios:
            if barrio in text_lower:
                return barrio.title()
        return 'Palermo'
