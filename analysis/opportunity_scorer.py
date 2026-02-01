"""
Algoritmo de scoring de oportunidad
"""
import re
from typing import Dict, List
from datetime import datetime

import sys
sys.path.append('..')
from config.settings import ZSCORE_THRESHOLD, OPPORTUNITY_SCORE_THRESHOLD
from config.keywords import URGENCY_KEYWORDS, SECONDARY_KEYWORDS, KEYWORD_WEIGHTS


def detect_keywords(text: str) -> List[str]:
    """
    Detecta palabras clave de urgencia en el texto
    
    Args:
        text: Texto de descripción
        
    Returns:
        Lista de keywords encontradas
    """
    if not text:
        return []
        
    text_lower = text.lower()
    found = []
    
    # Keywords principales
    for keyword in URGENCY_KEYWORDS:
        if keyword in text_lower:
            found.append(keyword)
            
    # Keywords secundarios
    for keyword in SECONDARY_KEYWORDS:
        if keyword in text_lower:
            found.append(keyword)
            
    return list(set(found))  # Eliminar duplicados


def calculate_keyword_score(keywords: List[str], max_score: int = 20) -> int:
    """
    Calcula score basado en keywords encontradas
    
    Args:
        keywords: Lista de keywords detectadas
        max_score: Puntaje máximo
        
    Returns:
        Score de keywords
    """
    if not keywords:
        return 0
        
    score = 0
    for keyword in keywords:
        weight = KEYWORD_WEIGHTS.get(keyword, KEYWORD_WEIGHTS['default'])
        score += weight
        
    return min(score, max_score)


def calculate_days_online(first_seen: str) -> int:
    """
    Calcula días desde primera publicación
    
    Args:
        first_seen: Fecha ISO de primera detección
        
    Returns:
        Días online
    """
    if not first_seen:
        return 0
        
    try:
        if isinstance(first_seen, str):
            first_date = datetime.fromisoformat(first_seen.replace('Z', '+00:00'))
        else:
            first_date = first_seen
            
        delta = datetime.now() - first_date.replace(tzinfo=None)
        return max(0, delta.days)
    except:
        return 0


def calculate_opportunity_score(property_data: Dict) -> Dict:
    """
    Calcula el score de oportunidad de una propiedad
    
    Factores:
    - Z-Score (40%): Precio por debajo de la media de la zona
    - Delta de precio si es relisting (25%): Reducción respecto a precio anterior
    - Keywords de urgencia (20%): Palabras que indican motivación
    - Antigüedad del aviso (15%): Propiedades estancadas
    
    Args:
        property_data: Diccionario con datos de la propiedad
        
    Returns:
        Propiedad con opportunity_score y detalles añadidos
    """
    result = property_data.copy()
    score = 0
    reasons = []
    
    # 1. Z-Score (40% del peso)
    zscore = property_data.get('zscore', 0)
    if zscore < ZSCORE_THRESHOLD:  # Por defecto -1.5
        score += 40
        reasons.append(f"Z-Score muy bajo ({zscore:.2f})")
    elif zscore < -1.0:
        score += 25
        reasons.append(f"Z-Score bajo ({zscore:.2f})")
    elif zscore < -0.5:
        score += 10
        reasons.append(f"Z-Score moderado ({zscore:.2f})")
        
    # 2. Delta de precio si es relisting (25%)
    if property_data.get('status') == 'relisted':
        delta_pct = property_data.get('price_delta_pct', 0)
        if delta_pct is not None:
            if delta_pct < -15:
                score += 25
                reasons.append(f"Relisting con -15%+ de descuento ({delta_pct:.1f}%)")
            elif delta_pct < -10:
                score += 18
                reasons.append(f"Relisting con -10%+ de descuento ({delta_pct:.1f}%)")
            elif delta_pct < -5:
                score += 10
                reasons.append(f"Relisting con descuento ({delta_pct:.1f}%)")
            elif delta_pct < 0:
                score += 5
                reasons.append(f"Relisting con precio reducido ({delta_pct:.1f}%)")
                
    # 3. Keywords de urgencia (20%)
    keywords = detect_keywords(property_data.get('descripcion', ''))
    keyword_score = calculate_keyword_score(keywords)
    score += keyword_score
    if keywords:
        reasons.append(f"Keywords: {', '.join(keywords[:3])}")
        
    # 4. Antigüedad del aviso (15%)
    days_online = calculate_days_online(property_data.get('first_seen'))
    if days_online > 90:
        score += 15
        reasons.append(f"Online {days_online} días (>90)")
    elif days_online > 60:
        score += 10
        reasons.append(f"Online {days_online} días (>60)")
    elif days_online > 30:
        score += 5
        reasons.append(f"Online {days_online} días (>30)")
        
    # Score final
    final_score = min(score, 100)
    
    result['opportunity_score'] = final_score
    result['opportunity_reasons'] = reasons
    result['keywords_detected'] = ', '.join(keywords)
    result['days_online'] = days_online
    result['is_opportunity'] = final_score >= OPPORTUNITY_SCORE_THRESHOLD
    
    return result


def score_all_properties(properties: List[Dict]) -> List[Dict]:
    """
    Calcula scores para todas las propiedades
    
    Args:
        properties: Lista de propiedades con datos de microzona
        
    Returns:
        Propiedades con opportunity_score
    """
    scored = []
    opportunities = 0
    
    for prop in properties:
        result = calculate_opportunity_score(prop)
        scored.append(result)
        
        if result['is_opportunity']:
            opportunities += 1
            print(f"🎯 Oportunidad detectada (score {result['opportunity_score']}):")
            print(f"   URL: {result.get('url', 'N/A')}")
            print(f"   Precio: ${result.get('precio_usd_mep', 0):,.0f} USD")
            print(f"   Razones: {', '.join(result['opportunity_reasons'])}")
            
    print(f"\n📊 Total oportunidades: {opportunities}/{len(properties)}")
    
    return scored
