"""
Cálculo de estadísticas por microzona
"""
from typing import Dict, List, Tuple
import math

import sys
sys.path.append('..')
from config.settings import MICROZONE_RADIUS_METERS


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en metros entre dos puntos"""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_properties_in_radius(
    center_lat: float,
    center_lng: float,
    properties: List[Dict],
    radius_meters: float = MICROZONE_RADIUS_METERS
) -> List[Dict]:
    """
    Obtiene propiedades dentro de un radio específico
    
    Args:
        center_lat, center_lng: Centro de la zona
        properties: Lista de propiedades
        radius_meters: Radio en metros
        
    Returns:
        Lista de propiedades dentro del radio
    """
    nearby = []
    
    for prop in properties:
        lat = prop.get('lat')
        lng = prop.get('lng')
        
        if lat is None or lng is None:
            continue
            
        distance = haversine_distance(center_lat, center_lng, lat, lng)
        
        if distance <= radius_meters:
            nearby.append(prop)
            
    return nearby


def calculate_microzone_stats(
    properties: List[Dict],
    price_field: str = 'precio_usd_mep'
) -> Dict:
    """
    Calcula estadísticas de una microzona
    
    Args:
        properties: Propiedades en la zona
        price_field: Campo de precio a usar
        
    Returns:
        Dict con mean, std, median, min, max, count
    """
    if not properties:
        return {
            'mean': 0.0,
            'std': 0.0,
            'median': 0.0,
            'min': 0.0,
            'max': 0.0,
            'count': 0,
            'mean_m2': 0.0,
        }
        
    # Filtrar propiedades con precio válido
    prices = [p[price_field] for p in properties if p.get(price_field, 0) > 0]
    prices_m2 = [p['precio_m2'] for p in properties if p.get('precio_m2', 0) > 0]
    
    if not prices:
        return {
            'mean': 0.0,
            'std': 0.0,
            'median': 0.0,
            'min': 0.0,
            'max': 0.0,
            'count': 0,
            'mean_m2': 0.0,
        }
        
    # Cálculos
    n = len(prices)
    mean = sum(prices) / n
    
    # Desviación estándar
    variance = sum((p - mean) ** 2 for p in prices) / n
    std = math.sqrt(variance) if variance > 0 else 0.0
    
    # Mediana
    sorted_prices = sorted(prices)
    if n % 2 == 0:
        median = (sorted_prices[n//2 - 1] + sorted_prices[n//2]) / 2
    else:
        median = sorted_prices[n//2]
        
    # Precio por m² promedio
    mean_m2 = sum(prices_m2) / len(prices_m2) if prices_m2 else 0.0
        
    return {
        'mean': mean,
        'std': std,
        'median': median,
        'min': min(prices),
        'max': max(prices),
        'count': n,
        'mean_m2': mean_m2,
    }


def calculate_zscore(value: float, mean: float, std: float) -> float:
    """
    Calcula Z-Score de un valor
    
    Args:
        value: Valor a evaluar
        mean: Media de la distribución
        std: Desviación estándar
        
    Returns:
        Z-Score (negativo = por debajo de la media)
    """
    if std == 0:
        return 0.0
    return (value - mean) / std


def calculate_all_microzones(
    properties: List[Dict],
    radius_meters: float = MICROZONE_RADIUS_METERS
) -> List[Dict]:
    """
    Calcula estadísticas de microzona para cada propiedad
    
    Args:
        properties: Lista de propiedades
        radius_meters: Radio de la microzona
        
    Returns:
        Propiedades con estadísticas de microzona añadidas
    """
    results = []
    
    for prop in properties:
        prop_copy = prop.copy()
        
        lat = prop.get('lat')
        lng = prop.get('lng')
        
        if lat is None or lng is None:
            # Sin coordenadas, intentar usar estadísticas globales del barrio
            same_barrio = [p for p in properties if p.get('barrio') == prop.get('barrio')]
            stats = calculate_microzone_stats(same_barrio)
        else:
            # Calcular microzona
            nearby = get_properties_in_radius(lat, lng, properties, radius_meters)
            stats = calculate_microzone_stats(nearby)
            
        # Agregar estadísticas
        prop_copy['microzone_mean'] = stats['mean']
        prop_copy['microzone_std'] = stats['std']
        prop_copy['microzone_median'] = stats['median']
        prop_copy['microzone_count'] = stats['count']
        prop_copy['microzone_mean_m2'] = stats['mean_m2']
        
        # Calcular Z-Score
        if prop.get('precio_usd_mep', 0) > 0 and stats['std'] > 0:
            prop_copy['zscore'] = calculate_zscore(
                prop['precio_usd_mep'],
                stats['mean'],
                stats['std']
            )
            prop_copy['zscore_m2'] = calculate_zscore(
                prop.get('precio_m2', 0),
                stats['mean_m2'],
                stats['std'] / prop.get('m2_total', 1) if prop.get('m2_total') else 1
            )
        else:
            prop_copy['zscore'] = 0.0
            prop_copy['zscore_m2'] = 0.0
            
        results.append(prop_copy)
        
    return results
