"""
Detección de relistings (propiedades que vuelven a publicarse)
"""
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import math


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula distancia en metros entre dos puntos geográficos
    
    Args:
        lat1, lon1: Coordenadas del punto 1
        lat2, lon2: Coordenadas del punto 2
        
    Returns:
        Distancia en metros
    """
    R = 6371000  # Radio de la Tierra en metros
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def simple_text_similarity(text1: str, text2: str) -> float:
    """
    Calcula similitud simple entre dos textos (Jaccard)
    
    Returns:
        Score de 0 a 1
    """
    if not text1 or not text2:
        return 0.0
        
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
        
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0


def is_relisting(
    new_property: Dict,
    historical_properties: List[Dict],
    geo_threshold_meters: float = 50,
    text_similarity_threshold: float = 0.7
) -> Tuple[bool, Optional[Dict], Optional[float]]:
    """
    Detecta si una propiedad nueva es un relisting de una anterior
    
    Args:
        new_property: Propiedad nueva
        historical_properties: Lista de propiedades históricas (delistadas)
        geo_threshold_meters: Distancia máxima para considerar match geográfico
        text_similarity_threshold: Similitud mínima de descripción
        
    Returns:
        Tuple: (es_relisting, propiedad_original, delta_precio_pct)
    """
    for old in historical_properties:
        # Skip si es la misma propiedad exacta
        if new_property.get('id') == old.get('id'):
            continue
            
        # Skip si es de la misma fuente y mismo portal_id
        if (new_property.get('source') == old.get('source') and 
            new_property.get('url') == old.get('url')):
            continue
            
        match_score = 0
        max_score = 0
        
        # 1. Match por dirección normalizada (peso alto)
        max_score += 40
        if new_property.get('direccion_normalizada') and old.get('direccion_normalizada'):
            if new_property['direccion_normalizada'] == old['direccion_normalizada']:
                match_score += 40
            elif simple_text_similarity(
                new_property['direccion_normalizada'],
                old['direccion_normalizada']
            ) > 0.8:
                match_score += 30
                
        # 2. Match geográfico (si tenemos coordenadas)
        max_score += 25
        if all([
            new_property.get('lat'), new_property.get('lng'),
            old.get('lat'), old.get('lng')
        ]):
            distance = haversine_distance(
                new_property['lat'], new_property['lng'],
                old['lat'], old['lng']
            )
            if distance < geo_threshold_meters:
                match_score += 25
            elif distance < geo_threshold_meters * 2:
                match_score += 15
                
        # 3. Match por características físicas
        max_score += 20
        features_match = 0
        
        # M² (tolerancia del 5%)
        if new_property.get('m2_total') and old.get('m2_total'):
            diff_pct = abs(new_property['m2_total'] - old['m2_total']) / old['m2_total']
            if diff_pct < 0.05:
                features_match += 1
                
        # Ambientes (exacto)
        if new_property.get('ambientes') and old.get('ambientes'):
            if new_property['ambientes'] == old['ambientes']:
                features_match += 1
                
        # Piso (exacto)
        if new_property.get('piso') is not None and old.get('piso') is not None:
            if new_property['piso'] == old['piso']:
                features_match += 1
                
        # Barrio (exacto)
        if new_property.get('barrio') and old.get('barrio'):
            if new_property['barrio'].lower() == old['barrio'].lower():
                features_match += 1
                
        if features_match >= 3:
            match_score += 20
        elif features_match >= 2:
            match_score += 10
            
        # 4. Similitud de descripción
        max_score += 15
        if new_property.get('descripcion') and old.get('descripcion'):
            desc_similarity = simple_text_similarity(
                new_property['descripcion'],
                old['descripcion']
            )
            if desc_similarity > text_similarity_threshold:
                match_score += 15
            elif desc_similarity > 0.5:
                match_score += 8
                
        # Calcular score final
        confidence = match_score / max_score if max_score > 0 else 0
        
        # Si la confianza es mayor al 60%, es un relisting
        if confidence >= 0.6:
            # Calcular delta de precio
            delta_pct = None
            if new_property.get('precio_usd_mep') and old.get('precio_usd_mep'):
                old_price = old['precio_usd_mep']
                new_price = new_property['precio_usd_mep']
                if old_price > 0:
                    delta_pct = ((new_price - old_price) / old_price) * 100
                    
            return True, old, delta_pct
            
    return False, None, None


def detect_relistings(
    properties: List[Dict],
    historical: List[Dict]
) -> List[Dict]:
    """
    Procesa lista de propiedades y marca relistings
    
    Args:
        properties: Propiedades nuevas a procesar
        historical: Propiedades históricas (delistadas)
        
    Returns:
        Propiedades con campos de relisting actualizados
    """
    processed = []
    
    for prop in properties:
        is_relist, original, delta_pct = is_relisting(prop, historical)
        
        prop_copy = prop.copy()
        
        if is_relist:
            prop_copy['status'] = 'relisted'
            prop_copy['original_id'] = original.get('id')
            prop_copy['original_price'] = original.get('precio_usd_mep')
            prop_copy['price_delta_pct'] = delta_pct
            
            print(f"[Relisting] Detectado: {prop_copy.get('url', 'N/A')}")
            if delta_pct:
                print(f"  → Delta precio: {delta_pct:.1f}%")
        else:
            prop_copy['status'] = 'active'
            prop_copy['original_id'] = None
            prop_copy['original_price'] = None
            prop_copy['price_delta_pct'] = None
            
        processed.append(prop_copy)
        
    return processed
