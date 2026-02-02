"""
Algoritmo de scoring de oportunidad - Mejorado
Usa precio/m² relativo al promedio del barrio para detectar oportunidades
"""
import re
from typing import Dict, List
from datetime import datetime

import sys
sys.path.append('..')
from config.settings import ZSCORE_THRESHOLD, OPPORTUNITY_SCORE_THRESHOLD
from config.keywords import URGENCY_KEYWORDS, SECONDARY_KEYWORDS, KEYWORD_WEIGHTS


# Precios promedio de mercado por m² en USD (Palermo 2026)
# Fuente: valores de referencia aproximados
MARKET_PRICES_M2 = {
    'palermo soho': 3200,
    'palermo hollywood': 3100,
    'palermo chico': 4000,
    'palermo viejo': 3000,
    'palermo nuevo': 2800,
    'palermo botanico': 2900,
    'palermo': 3100,  # Promedio general
}


def detect_keywords(text: str) -> List[str]:
    """Detecta palabras clave de urgencia en el texto"""
    if not text:
        return []
        
    text_lower = text.lower()
    found = []
    
    for keyword in URGENCY_KEYWORDS:
        if keyword in text_lower:
            found.append(keyword)
            
    for keyword in SECONDARY_KEYWORDS:
        if keyword in text_lower:
            found.append(keyword)
            
    return list(set(found))


def calculate_keyword_score(keywords: List[str], max_score: int = 15) -> int:
    """Calcula score basado en keywords"""
    if not keywords:
        return 0
        
    score = 0
    for keyword in keywords:
        weight = KEYWORD_WEIGHTS.get(keyword, KEYWORD_WEIGHTS.get('default', 5))
        score += weight
        
    return min(score, max_score)


def calculate_days_online(first_seen: str) -> int:
    """Calcula días desde primera publicación"""
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


def calculate_price_score(property_data: Dict) -> tuple:
    """
    Calcula score basado en precio/m² relativo al mercado
    
    Returns:
        (score, descuento_pct, razon)
    """
    precio = property_data.get('precio_usd_mep', 0)
    m2 = property_data.get('m2_total', 0)
    barrio = property_data.get('barrio', 'Palermo').lower()
    
    if precio <= 0 or m2 <= 0:
        return 0, 0, None
    
    precio_m2 = precio / m2
    
    # Obtener precio de referencia del barrio
    precio_mercado = MARKET_PRICES_M2.get(barrio, MARKET_PRICES_M2['palermo'])
    
    # Calcular descuento respecto al mercado
    descuento_pct = ((precio_mercado - precio_m2) / precio_mercado) * 100
    
    # Score basado en descuento
    score = 0
    razon = None
    
    if descuento_pct >= 30:
        score = 50  # Oportunidad excepcional
        razon = f"🔥 -30%+ vs mercado (${precio_m2:,.0f}/m² vs ${precio_mercado:,.0f}/m²)"
    elif descuento_pct >= 20:
        score = 40
        razon = f"⭐ -20%+ vs mercado (${precio_m2:,.0f}/m² vs ${precio_mercado:,.0f}/m²)"
    elif descuento_pct >= 15:
        score = 30
        razon = f"✓ -15%+ vs mercado (${precio_m2:,.0f}/m² vs ${precio_mercado:,.0f}/m²)"
    elif descuento_pct >= 10:
        score = 20
        razon = f"-10%+ vs mercado (${precio_m2:,.0f}/m² vs ${precio_mercado:,.0f}/m²)"
    elif descuento_pct >= 5:
        score = 10
        razon = f"Ligero descuento vs mercado"
        
    return score, descuento_pct, razon


def calculate_opportunity_score(property_data: Dict) -> Dict:
    """
    Calcula el score de oportunidad de una propiedad
    
    Factores:
    - Precio/m² vs mercado (50%): Descuento respecto a precio promedio del barrio
    - Z-Score histórico (15%): Precio por debajo de la media de propiedades similares
    - Keywords de urgencia (15%): Palabras que indican motivación
    - Antigüedad del aviso (10%): Propiedades estancadas pueden negociarse
    - Relisting con descuento (10%): Reducción respecto a precio anterior
    
    Returns:
        Propiedad con opportunity_score y detalles añadidos
    """
    result = property_data.copy()
    score = 0
    reasons = []
    
    # 1. Precio/m² vs mercado (50%)
    price_score, descuento_pct, price_reason = calculate_price_score(property_data)
    score += price_score
    if price_reason:
        reasons.append(price_reason)
    
    # Guardar descuento para referencia
    result['market_discount_pct'] = descuento_pct
    
    # 2. Z-Score histórico (15%)
    zscore = property_data.get('zscore', 0)
    if zscore < ZSCORE_THRESHOLD:  # Por defecto -1.5
        score += 15
        reasons.append(f"Z-Score muy bajo ({zscore:.2f})")
    elif zscore < -1.0:
        score += 10
        reasons.append(f"Z-Score bajo ({zscore:.2f})")
    elif zscore < -0.5:
        score += 5
        
    # 3. Keywords de urgencia (15%)
    keywords = detect_keywords(
        property_data.get('descripcion', '') + ' ' + 
        property_data.get('titulo', '')
    )
    keyword_score = calculate_keyword_score(keywords)
    score += keyword_score
    if keywords:
        reasons.append(f"Keywords: {', '.join(keywords[:3])}")
        
    # 4. Antigüedad del aviso (10%)
    days_online = calculate_days_online(property_data.get('first_seen'))
    if days_online > 90:
        score += 10
        reasons.append(f"Online {days_online} días")
    elif days_online > 60:
        score += 7
    elif days_online > 30:
        score += 4
        
    # 5. Relisting con descuento (10%)
    if property_data.get('status') == 'relisted':
        delta_pct = property_data.get('price_delta_pct', 0)
        if delta_pct and delta_pct < -10:
            score += 10
            reasons.append(f"Relisting -{abs(delta_pct):.0f}%")
        elif delta_pct and delta_pct < -5:
            score += 5
        
    # Score final
    final_score = min(score, 100)
    
    result['opportunity_score'] = final_score
    result['opportunity_reasons'] = reasons
    result['keywords_detected'] = ', '.join(keywords)
    result['days_online'] = days_online
    result['is_opportunity'] = final_score >= OPPORTUNITY_SCORE_THRESHOLD
    
    return result


def score_all_properties(properties: List[Dict]) -> List[Dict]:
    """Calcula scores para todas las propiedades"""
    scored = []
    opportunities = 0
    
    for prop in properties:
        result = calculate_opportunity_score(prop)
        scored.append(result)
        
        if result['is_opportunity']:
            opportunities += 1
            print(f"🎯 Oportunidad (score {result['opportunity_score']}): "
                  f"${result.get('precio_usd_mep', 0):,.0f} - {result.get('m2_total', 0)}m² - "
                  f"{result.get('barrio', 'Palermo')}")
            for reason in result['opportunity_reasons']:
                print(f"   → {reason}")
            
    print(f"\n📊 Total oportunidades: {opportunities}/{len(properties)}")
    
    return scored
