"""
Palabras clave que indican urgencia de venta
"""

# Keywords principales (alta señal de motivación)
URGENCY_KEYWORDS = [
    "urgente",
    "urge",
    "urge vender",
    "sucesión",
    "sucesion",
    "retasado",
    "retasada",
    "rebajado",
    "rebajada",
    "oportunidad",
    "oportunidad única",
    "acepta permuta",
    "permuta",
    "escucha ofertas",
    "escucho ofertas",
    "a tratar",
    "negociable",
    "muy negociable",
    "liquido",
    "liquidación",
    "divorcio",
    "separación",
    "viaje",
    "viajo",
    "mudanza",
    "me mudo",
    "venta rápida",
    "venta rapida",
    "dueño directo",
    "dueño vende",
    "sin intermediarios",
    "bajo tasación",
    "bajo tasacion",
    "por debajo",
    "ganga",
    "regalar",
    "regalo",
]

# Keywords secundarios (señal media)
SECONDARY_KEYWORDS = [
    "excelente precio",
    "muy buen precio",
    "imperdible",
    "no te lo pierdas",
    "última oportunidad",
    "ultima oportunidad",
    "ocasión",
    "ocasion",
    "financiación",
    "financiacion",
    "cuotas",
]

# Pesos para el scoring
KEYWORD_WEIGHTS = {
    "urgente": 5,
    "sucesión": 5,
    "sucesion": 5,
    "retasado": 4,
    "retasada": 4,
    "acepta permuta": 4,
    "divorcio": 4,
    "liquidación": 4,
    "bajo tasación": 4,
    "bajo tasacion": 4,
    "default": 2,
}
