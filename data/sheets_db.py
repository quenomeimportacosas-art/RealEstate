"""
Integración con Google Sheets usando gspread
"""
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

import sys
sys.path.append('..')
from config.settings import (
    CREDENTIALS_PATH,
    GOOGLE_SHEET_ID,
    SHEET_PROPIEDADES,
    SHEET_HISTORIAL,
    SHEET_MICROZONES,
)


# Scopes necesarios
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]


class GoogleSheetsDB:
    """Clase para manejar base de datos en Google Sheets"""
    
    def __init__(self, credentials_path: str = None, sheet_id: str = None):
        self.credentials_path = credentials_path or str(CREDENTIALS_PATH)
        # Permitir override desde env var
        self.sheet_id = os.environ.get('GOOGLE_SHEET_ID') or sheet_id or GOOGLE_SHEET_ID
        self.client = None
        self.spreadsheet = None
        
    def connect(self):
        """Conecta a Google Sheets - soporta credenciales desde archivo o env var"""
        try:
            # Intentar primero desde variable de entorno (para cloud/CI)
            creds_json = os.environ.get('GOOGLE_CREDENTIALS')
            
            if creds_json:
                # Credenciales desde env var (JSON string)
                creds_dict = json.loads(creds_json)
                creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
                print("[GoogleSheets] Usando credenciales desde variable de entorno")
            else:
                # Credenciales desde archivo (local)
                creds = Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=SCOPES
                )
                print("[GoogleSheets] Usando credenciales desde archivo")
                
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.sheet_id)
            print(f"[GoogleSheets] Conectado a: {self.spreadsheet.title}")
            return True
        except Exception as e:
            print(f"[GoogleSheets] Error conectando: {e}")
            return False
            
    def _get_or_create_sheet(self, sheet_name: str, headers: List[str] = None) -> gspread.Worksheet:
        """Obtiene o crea una hoja"""
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=sheet_name,
                rows=1000,
                cols=len(headers) if headers else 26
            )
            if headers:
                worksheet.update('A1', [headers])
                
        return worksheet
        
    def get_all_properties(self) -> List[Dict]:
        """Obtiene todas las propiedades de la hoja"""
        worksheet = self._get_or_create_sheet(SHEET_PROPIEDADES, self._get_headers())
        records = worksheet.get_all_records()
        return records
        
    def get_historical_properties(self) -> List[Dict]:
        """Obtiene propiedades delistadas del historial"""
        worksheet = self._get_or_create_sheet(SHEET_HISTORIAL, self._get_headers())
        records = worksheet.get_all_records()
        return [r for r in records if r.get('status') == 'delisted']
        
    def _get_headers(self) -> List[str]:
        """Headers de la hoja de propiedades"""
        return [
            'id', 'source', 'url', 'titulo', 'precio_original', 'moneda',
            'precio_usd_mep', 'expensas', 'm2_total', 'm2_cubiertos',
            'ambientes', 'piso', 'direccion', 'barrio', 'lat', 'lng',
            'inmobiliaria', 'descripcion', 'first_seen', 'last_seen',
            'status', 'opportunity_score', 'keywords_detected', 'zscore',
            'microzone_mean', 'microzone_count', 'days_online', 'is_opportunity',
            'original_id', 'price_delta_pct'
        ]
        
    def upsert_properties(self, properties: List[Dict]):
        """
        Inserta o actualiza propiedades
        
        Args:
            properties: Lista de propiedades a guardar
        """
        if not properties:
            return
            
        headers = self._get_headers()
        worksheet = self._get_or_create_sheet(SHEET_PROPIEDADES, headers)
        
        # Obtener IDs existentes
        existing = worksheet.get_all_records()
        existing_ids = {r['id']: i+2 for i, r in enumerate(existing)}  # +2 por header y 1-index
        
        # Función para convertir número de columna a letra Excel (1=A, 27=AA, etc)
        def col_to_letter(col):
            result = ""
            while col > 0:
                col, remainder = divmod(col - 1, 26)
                result = chr(65 + remainder) + result
            return result
        
        last_col = col_to_letter(len(headers))  # Ej: 29 columnas = "AC"
        
        updates = []
        new_rows = []
        
        for prop in properties:
            row_data = [prop.get(h, '') for h in headers]
            
            if prop.get('id') in existing_ids:
                # Actualizar fila existente
                row_num = existing_ids[prop['id']]
                updates.append({
                    'range': f'A{row_num}:{last_col}{row_num}',
                    'values': [row_data]
                })
            else:
                # Nueva fila
                new_rows.append(row_data)
                
        # Aplicar actualizaciones
        if updates:
            worksheet.batch_update(updates)
            print(f"[GoogleSheets] Actualizadas {len(updates)} propiedades")
            
        # Agregar nuevas filas
        if new_rows:
            worksheet.append_rows(new_rows)
            print(f"[GoogleSheets] Agregadas {len(new_rows)} propiedades nuevas")
            
    def mark_delisted(self, property_ids: List[str]):
        """
        Marca propiedades como delistadas
        
        Args:
            property_ids: IDs de propiedades a marcar
        """
        if not property_ids:
            return
            
        worksheet = self._get_or_create_sheet(SHEET_PROPIEDADES)
        records = worksheet.get_all_records()
        
        # Encontrar columna de status
        headers = worksheet.row_values(1)
        status_col = headers.index('status') + 1 if 'status' in headers else None
        
        if not status_col:
            return
            
        updates = []
        for i, record in enumerate(records):
            if record.get('id') in property_ids:
                updates.append({
                    'range': f'{chr(64 + status_col)}{i+2}',
                    'values': [['delisted']]
                })
                
        if updates:
            worksheet.batch_update(updates)
            print(f"[GoogleSheets] Marcadas {len(updates)} propiedades como delisted")
            
            # Copiar al historial
            hist_worksheet = self._get_or_create_sheet(SHEET_HISTORIAL, self._get_headers())
            delisted = [r for r in records if r.get('id') in property_ids]
            if delisted:
                hist_worksheet.append_rows([
                    [r.get(h, '') for h in self._get_headers()]
                    for r in delisted
                ])
                
    def get_opportunities(self, min_score: int = 75) -> List[Dict]:
        """Obtiene propiedades con score >= min_score"""
        properties = self.get_all_properties()
        return [
            p for p in properties
            if p.get('opportunity_score', 0) >= min_score and p.get('status') == 'active'
        ]
        
    def to_dataframe(self) -> pd.DataFrame:
        """Convierte propiedades a DataFrame de pandas"""
        properties = self.get_all_properties()
        return pd.DataFrame(properties)
        
    def save_microzones(self, stats: List[Dict]):
        """Guarda estadísticas de microzones"""
        if not stats:
            return
            
        headers = ['barrio', 'mean_price', 'median_price', 'std', 'count', 'mean_m2', 'updated_at']
        worksheet = self._get_or_create_sheet(SHEET_MICROZONES, headers)
        
        # Limpiar y escribir
        worksheet.clear()
        worksheet.update('A1', [headers])
        
        rows = [
            [s.get(h, '') for h in headers]
            for s in stats
        ]
        if rows:
            worksheet.append_rows(rows)
            print(f"[GoogleSheets] Guardadas {len(rows)} estadísticas de microzones")
