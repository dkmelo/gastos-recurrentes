import json
import os
from datetime import datetime
from typing import Optional, List, Dict
from dotenv import load_dotenv

# Cargar .env de la raíz del proyecto
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
load_dotenv(env_path)

MOCK_DB_PATH = os.path.join(os.path.dirname(__file__), "sheets_mock.json")

INITIAL_MOCK_DATA = {
    "contracts": [
        {
            "ID Contrato": "CON-101",
            "NIT": "123456789-0",
            "Monto": 100.0,
            "Fecha Inicio": "2026-01-01",
            "Fecha Fin": "2026-12-31",
            "Razon Social": "Internet S.A.",
            "Concepto": "Plan Fibra",
            "Estado": "Activo"
        },
        {
            "ID Contrato": "CON-102",
            "NIT": "987654321-1",
            "Monto": 500.0,
            "Fecha Inicio": "2025-06-01",
            "Fecha Fin": "2026-06-20", # Expiró hace 5 días (margen pospago < 30 días)
            "Razon Social": "Hosting Solutions",
            "Concepto": "Cloud VPS",
            "Estado": "Activo"
        },
        {
            "ID Contrato": "CON-103",
            "NIT": "555555555-5",
            "Monto": 50.0,
            "Fecha Inicio": "2026-01-01",
            "Fecha Fin": "2026-05-15", # Expiró hace más de 30 días (auto-rechazo si fecha factura es de hoy)
            "Razon Social": "Mail Services",
            "Concepto": "Email Marketing",
            "Estado": "Activo"
        },
        {
            "ID Contrato": "CON-104",
            "NIT": "222222222-2",
            "Monto": 200.0,
            "Fecha Inicio": "2026-01-01",
            "Fecha Fin": "2026-07-05", # Próximo a vencer (10 días)
            "Razon Social": "Dev Tools",
            "Concepto": "Licencias IDE",
            "Estado": "Activo"
        },
        {
            "ID Contrato": "CON-105",
            "NIT": "333333333-3",
            "Monto": 1000.0,
            "Fecha Inicio": "2025-01-01",
            "Fecha Fin": "2025-12-31",
            "Razon Social": "SaaS Premium",
            "Concepto": "Enterprise CRM",
            "Estado": "Inactivo" # Inactivo (debe omitirse de búsquedas)
        }
    ],
    "history": []
}


def _load_db() -> Dict:
    if not os.path.exists(MOCK_DB_PATH):
        _save_db(INITIAL_MOCK_DATA)
        return INITIAL_MOCK_DATA
    try:
        with open(MOCK_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return INITIAL_MOCK_DATA


def _save_db(data: Dict):
    os.makedirs(os.path.dirname(MOCK_DB_PATH), exist_ok=True)
    with open(MOCK_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# --- Soporte para Google Sheets API Real ---

def is_using_real_sheets() -> bool:
    return os.getenv("USE_REAL_SHEETS", "False").lower() in ("true", "1", "yes")


def _get_sheets_service():
    from googleapiclient.discovery import build
    import google.auth
    from google.oauth2 import service_account

    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path and os.path.exists(cred_path):
        credentials = service_account.Credentials.from_service_account_file(
            cred_path,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
    else:
        credentials, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
    return build("sheets", "v4", credentials=credentials)


def _get_spreadsheet_id() -> str:
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    if not spreadsheet_id:
        raise ValueError("SPREADSHEET_ID debe estar configurado en el archivo .env para usar Sheets Real.")
    return spreadsheet_id


# --- API Unificada ---

def get_all_contracts() -> List[Dict]:
    """
    Retorna todos los contratos.
    """
    if is_using_real_sheets():
        try:
            service = _get_sheets_service()
            spreadsheet_id = _get_spreadsheet_id()
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range="Contratos!A2:H"
            ).execute()
            rows = result.get("values", [])
            contracts = []
            for r in rows:
                if len(r) < 8:
                    # Rellenar columnas vacías si la fila es corta
                    r += [""] * (8 - len(r))
                contracts.append({
                    "ID Contrato": r[0],
                    "NIT": r[1],
                    "Monto": float(r[2]) if r[2] else 0.0,
                    "Fecha Inicio": r[3],
                    "Fecha Fin": r[4],
                    "Razon Social": r[5],
                    "Concepto": r[6],
                    "Estado": r[7]
                })
            return contracts
        except Exception as e:
            print(f"[Sheets Error] Error leyendo contratos de Google Sheets real: {e}. Usando mock local.")
    
    # Fallback a Mock local
    db = _load_db()
    return db.get("contracts", [])


def get_contract(id_contrato: str) -> Optional[Dict]:
    """
    Busca un contrato por su ID único.
    Omitirá cualquier registro que tenga un Estado como 'Inactivo'.
    """
    contracts = get_all_contracts()
    for contract in contracts:
        if contract.get("ID Contrato") == id_contrato:
            if contract.get("Estado") != "Inactivo":
                return contract
    return None


def update_contract_monto(id_contrato: str, nuevo_monto: float) -> bool:
    """
    Actualiza el monto de referencia de un contrato.
    """
    if is_using_real_sheets():
        try:
            service = _get_sheets_service()
            spreadsheet_id = _get_spreadsheet_id()
            # Buscar el row_index
            contracts = get_all_contracts()
            row_num = None
            for idx, contract in enumerate(contracts):
                if contract.get("ID Contrato") == id_contrato:
                    row_num = idx + 2 # 1-based, +1 por el header
                    break
            if row_num:
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"Contratos!C{row_num}",
                    valueInputOption="RAW",
                    body={"values": [[nuevo_monto]]}
                ).execute()
                return True
            return False
        except Exception as e:
            print(f"[Sheets Error] Error actualizando monto en Sheets: {e}")
            return False

    db = _load_db()
    for contract in db.get("contracts", []):
        if contract.get("ID Contrato") == id_contrato:
            contract["Monto"] = nuevo_monto
            _save_db(db)
            return True
    return False


def update_contract_fecha_fin(id_contrato: str, nueva_fecha_fin: str) -> bool:
    """
    Actualiza la fecha de finalización (renovación) de un contrato.
    """
    if is_using_real_sheets():
        try:
            service = _get_sheets_service()
            spreadsheet_id = _get_spreadsheet_id()
            contracts = get_all_contracts()
            row_num = None
            for idx, contract in enumerate(contracts):
                if contract.get("ID Contrato") == id_contrato:
                    row_num = idx + 2
                    break
            if row_num:
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"Contratos!E{row_num}",
                    valueInputOption="RAW",
                    body={"values": [[nueva_fecha_fin]]}
                ).execute()
                return True
            return False
        except Exception as e:
            print(f"[Sheets Error] Error actualizando Fecha Fin en Sheets: {e}")
            return False

    db = _load_db()
    for contract in db.get("contracts", []):
        if contract.get("ID Contrato") == id_contrato:
            contract["Fecha Fin"] = nueva_fecha_fin
            _save_db(db)
            return True
    return False


def inactivate_contract(id_contrato: str) -> bool:
    """
    Marca un contrato como Inactivo.
    """
    if is_using_real_sheets():
        try:
            service = _get_sheets_service()
            spreadsheet_id = _get_spreadsheet_id()
            contracts = get_all_contracts()
            row_num = None
            for idx, contract in enumerate(contracts):
                if contract.get("ID Contrato") == id_contrato:
                    row_num = idx + 2
                    break
            if row_num:
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"Contratos!H{row_num}",
                    valueInputOption="RAW",
                    body={"values": [["Inactivo"]]}
                ).execute()
                return True
            return False
        except Exception as e:
            print(f"[Sheets Error] Error inactivando contrato en Sheets: {e}")
            return False

    db = _load_db()
    for contract in db.get("contracts", []):
        if contract.get("ID Contrato") == id_contrato:
            contract["Estado"] = "Inactivo"
            _save_db(db)
            return True
    return False


def add_approval_history(
    id_contrato: str,
    nit: str,
    valor: float,
    fecha_factura: str,
    estado_aprobacion: str,
    metadata: Optional[Dict] = None
) -> None:
    """
    Registra un evento de aprobación/rechazo en el historial.
    """
    now_str = datetime.now().isoformat()
    meta_str = json.dumps(metadata or {}, ensure_ascii=False)

    if is_using_real_sheets():
        try:
            service = _get_sheets_service()
            spreadsheet_id = _get_spreadsheet_id()
            row = [now_str, id_contrato, nit, valor, fecha_factura, estado_aprobacion, meta_str]
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range="Historial de Aprobaciones!A:G",
                valueInputOption="RAW",
                body={"values": [row]}
            ).execute()
            return
        except Exception as e:
            print(f"[Sheets Error] Error registrando historial en Sheets: {e}")

    # Guardado Mock local
    db = _load_db()
    event = {
        "Fecha Evento": now_str,
        "ID Contrato": id_contrato,
        "NIT": nit,
        "Valor Factura": valor,
        "Fecha Factura": fecha_factura,
        "Estado Aprobación": estado_aprobacion,
        "Metadata": metadata or {}
    }
    db.setdefault("history", []).append(event)
    _save_db(db)


def get_history() -> List[Dict]:
    """
    Retorna la bitácora histórica de aprobaciones y rechazos.
    """
    if is_using_real_sheets():
        try:
            service = _get_sheets_service()
            spreadsheet_id = _get_spreadsheet_id()
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range="Historial de Aprobaciones!A2:G"
            ).execute()
            rows = result.get("values", [])
            history = []
            for r in rows:
                if len(r) < 7:
                    r += [""] * (7 - len(r))
                try:
                    meta_dict = json.loads(r[6]) if r[6] else {}
                except Exception:
                    meta_dict = {"raw_metadata": r[6]} if r[6] else {}
                history.append({
                    "Fecha Evento": r[0],
                    "ID Contrato": r[1],
                    "NIT": r[2],
                    "Valor Factura": float(r[3]) if r[3] else 0.0,
                    "Fecha Factura": r[4],
                    "Estado Aprobación": r[5],
                    "Metadata": meta_dict
                })
            return history
        except Exception as e:
            print(f"[Sheets Error] Error obteniendo historial de Google Sheets real: {e}")

    db = _load_db()
    return db.get("history", [])
