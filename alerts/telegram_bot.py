"""
Bot de Telegram para alertas de oportunidades
"""
import asyncio
from typing import Dict, List
from telegram import Bot
from telegram.constants import ParseMode

import sys
sys.path.append('..')
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, OPPORTUNITY_SCORE_THRESHOLD


class TelegramAlerts:
    """Clase para enviar alertas via Telegram"""
    
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.bot = None
        
        if self.token:
            self.bot = Bot(token=self.token)
            
    def is_configured(self) -> bool:
        """Verifica si el bot está configurado"""
        return bool(self.token and self.chat_id)
        
    async def send_message(self, message: str):
        """Envía un mensaje simple"""
        if not self.is_configured():
            print("[Telegram] Bot no configurado. Configura TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID")
            return False
            
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            return True
        except Exception as e:
            print(f"[Telegram] Error enviando mensaje: {e}")
            return False
            
    def format_opportunity_message(self, property_data: Dict) -> str:
        """
        Formatea mensaje de oportunidad para Telegram
        
        Args:
            property_data: Datos de la propiedad
            
        Returns:
            Mensaje formateado HTML
        """
        score = property_data.get('opportunity_score', 0)
        
        # Emoji según score
        if score >= 90:
            emoji = "🔥🔥🔥"
        elif score >= 80:
            emoji = "🔥🔥"
        elif score >= 75:
            emoji = "🔥"
        else:
            emoji = "📍"
            
        # Formatear precio
        price = property_data.get('precio_usd_mep', 0)
        price_str = f"${price:,.0f} USD"
        
        # Razones
        reasons = property_data.get('opportunity_reasons', [])
        reasons_str = "\n".join([f"  • {r}" for r in reasons]) if reasons else "N/A"
        
        # Delta si es relisting
        delta_str = ""
        if property_data.get('status') == 'relisted':
            delta = property_data.get('price_delta_pct', 0)
            if delta:
                delta_str = f"\n📉 <b>Bajó {abs(delta):.1f}%</b> desde última publicación"
                
        message = f"""
{emoji} <b>OPORTUNIDAD DETECTADA</b>
Score: <b>{score}/100</b>

💰 <b>Precio:</b> {price_str}
📐 <b>Superficie:</b> {property_data.get('m2_total', 0)} m²
🏠 <b>Ambientes:</b> {property_data.get('ambientes', 'N/A')}
📍 <b>Ubicación:</b> {property_data.get('barrio', 'Palermo')}
{delta_str}

<b>Razones:</b>
{reasons_str}

🔗 <a href="{property_data.get('url', '#')}">Ver propiedad</a>
        """.strip()
        
        return message
        
    async def send_opportunity_alert(self, property_data: Dict):
        """Envía alerta de una oportunidad"""
        message = self.format_opportunity_message(property_data)
        return await self.send_message(message)
        
    async def send_opportunities_batch(self, properties: List[Dict], min_score: int = None):
        """
        Envía alertas de múltiples oportunidades
        
        Args:
            properties: Lista de propiedades
            min_score: Score mínimo para alertar
        """
        if min_score is None:
            min_score = OPPORTUNITY_SCORE_THRESHOLD
            
        opportunities = [
            p for p in properties
            if p.get('opportunity_score', 0) >= min_score and p.get('status') == 'active'
        ]
        
        if not opportunities:
            print("[Telegram] No hay oportunidades nuevas para alertar")
            return
            
        print(f"[Telegram] Enviando {len(opportunities)} alertas...")
        
        # Ordenar por score
        opportunities.sort(key=lambda x: x.get('opportunity_score', 0), reverse=True)
        
        for prop in opportunities:
            await self.send_opportunity_alert(prop)
            await asyncio.sleep(1)  # Evitar rate limiting
            
        print(f"[Telegram] Enviadas {len(opportunities)} alertas")
        
    async def send_daily_summary(self, stats: Dict):
        """
        Envía resumen diario
        
        Args:
            stats: Estadísticas del día
        """
        message = f"""
📊 <b>RESUMEN DIARIO</b>

🏠 Propiedades activas: {stats.get('total_active', 0)}
🔄 Nuevas hoy: {stats.get('new_today', 0)}
📉 Delistadas: {stats.get('delisted_today', 0)}
🎯 Oportunidades: {stats.get('opportunities', 0)}

💰 Precio promedio: ${stats.get('avg_price', 0):,.0f}
📐 m² promedio: ${stats.get('avg_price_m2', 0):,.0f}/m²
        """.strip()
        
        return await self.send_message(message)


def send_alert_sync(property_data: Dict):
    """Función síncrona para enviar alerta (wrapper)"""
    bot = TelegramAlerts()
    if not bot.is_configured():
        print("[Telegram] Bot no configurado")
        return False
        
    return asyncio.run(bot.send_opportunity_alert(property_data))
