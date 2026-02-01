"""
Pipeline de normalización de datos
"""
import re
from typing import Dict, Optional
import requests
from datetime import datetime

import sys
sys.path.append('..')
from config.settings import DOLAR_MEP


def get_dolar_mep() -> float:
    """
    Obtiene cotización actual del dólar MEP desde Bluelytics
    Si falla, usa el valor por defecto de settings
    """
    try:
        response = requests.get('https://api.bluelytics.com.ar/v2/latest', timeout=5)
        if response.status_code == 200:
            data = response.json()
            # MEP está en el campo 'blue' aproximadamente
            mep = data.get('blue', {}).get('value_sell', DOLAR_MEP)
            return float(mep)
    except Exception as e:
        print(f"[Normalizer] Error obteniendo dólar MEP: {e}")
    return DOLAR_MEP


def normalize_price_to_usd(price: float, currency: str, dolar_mep: float = None) -> float:
    """
    Convierte precio a USD MEP
    
    Args:
        price: Precio original
        currency: 'USD' o 'ARS'
        dolar_mep: Cotización del dólar MEP (si None, usa la de settings)
        
    Returns:
        Precio en USD MEP
    """
    if dolar_mep is None:
        dolar_mep = DOLAR_MEP
        
    if currency == 'USD':
        return price
    elif currency == 'ARS':
        return price / dolar_mep if dolar_mep > 0 else 0.0
    else:
        return price


def normalize_rooms(text: str) -> int:
    """
    Normaliza texto de ambientes a número entero
    
    Ejemplos:
        "2 amb" -> 2
        "Dos ambientes" -> 2
        "Monoambiente" -> 1
    """
    if not text:
        return 0
        
    text = text.lower().strip()
    
    # Monoambiente
    if 'mono' in text:
        return 1
        
    # Número directo
    match = re.search(r'(\d+)\s*(?:amb|ambiente|dormitorio|habitacion)', text)
    if match:
        return int(match.group(1))
        
    # Texto a número
    text_to_num = {
        'un ': 1, 'uno': 1, 'una': 1,
        'dos': 2,
        'tres': 3,
        'cuatro': 4,
        'cinco': 5,
        'seis': 6,
        'siete': 7,
    }
    
    for word, num in text_to_num.items():
        if word in text:
            return num
            
    return 0


def normalize_area(text: str) -> float:
    """
    Extrae metros cuadrados del texto
    
    Ejemplos:
        "45 m²" -> 45.0
        "45,5 metros cuadrados" -> 45.5
    """
    if not text:
        return 0.0
        
    # Buscar número antes de m², m2, mts, metros
    match = re.search(r'([\d.,]+)\s*(?:m²|m2|mts|metros)', text.lower())
    if match:
        area_str = match.group(1).replace('.', '').replace(',', '.')
        try:
            return float(area_str)
        except ValueError:
            pass
            
    # Intentar solo número
    match = re.search(r'([\d.,]+)', text)
    if match:
        area_str = match.group(1).replace('.', '').replace(',', '.')
        try:
            return float(area_str)
        except ValueError:
            pass
            
    return 0.0


def normalize_address(address: str) -> str:
    """
    Normaliza dirección para comparación
    
    - Minúsculas
    - Sin acentos
    - Abreviaturas expandidas
    """
    if not address:
        return ''
        
    import unicodedata
    
    # Minúsculas
    normalized = address.lower().strip()
    
    # Remover acentos
    normalized = unicodedata.normalize('NFD', normalized)
    normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    
    # Expandir abreviaturas
    replacements = {
        'av.': 'avenida',
        'av ': 'avenida ',
        'calle ': '',
        'esq.': 'esquina',
        'piso ': 'piso ',
        'dto.': 'departamento',
        'dpto.': 'departamento',
        'depto.': 'departamento',
    }
    
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
        
    # Remover caracteres especiales
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    
    return normalized.strip()


def normalize_property(data: Dict, dolar_mep: float = None) -> Dict:
    """
    Aplica todas las normalizaciones a una propiedad
    
    Args:
        data: Diccionario con datos crudos de la propiedad
        dolar_mep: Cotización del dólar MEP
        
    Returns:
        Diccionario con datos normalizados
    """
    normalized = data.copy()
    
    # Precio en USD MEP
    if 'precio_original' in data and 'moneda' in data:
        normalized['precio_usd_mep'] = normalize_price_to_usd(
            data['precio_original'],
            data['moneda'],
            dolar_mep
        )
    else:
        normalized['precio_usd_mep'] = 0.0
        
    # Ambientes (si viene como texto)
    if isinstance(data.get('ambientes'), str):
        normalized['ambientes'] = normalize_rooms(data['ambientes'])
        
    # Metros (si vienen como texto)
    if isinstance(data.get('m2_total'), str):
        normalized['m2_total'] = normalize_area(data['m2_total'])
    if isinstance(data.get('m2_cubiertos'), str):
        normalized['m2_cubiertos'] = normalize_area(data['m2_cubiertos'])
        
    # Si no hay m² total pero sí cubiertos, estimar
    if normalized.get('m2_total', 0) == 0 and normalized.get('m2_cubiertos', 0) > 0:
        normalized['m2_total'] = normalized['m2_cubiertos'] * 1.15
        
    # Dirección normalizada (para matching)
    normalized['direccion_normalizada'] = normalize_address(data.get('direccion', ''))
    
    # Precio por m²
    if normalized.get('m2_total', 0) > 0 and normalized.get('precio_usd_mep', 0) > 0:
        normalized['precio_m2'] = normalized['precio_usd_mep'] / normalized['m2_total']
    else:
        normalized['precio_m2'] = 0.0
        
    return normalized
