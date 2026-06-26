import os
import sys

# Asegurar importaciones
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import sheets_utils

def populate():
    print("==========================================")
    print("POBLANDO MOCK DATA EN GOOGLE SHEETS REAL")
    print("==========================================")
    
    if not sheets_utils.is_using_real_sheets():
        print("Error: USE_REAL_SHEETS no está configurado como True. Actívalo en tu .env primero.")
        return

    try:
        service = sheets_utils._get_sheets_service()
        spreadsheet_id = sheets_utils._get_spreadsheet_id()
        
        # 1. Preparar datos de "Contratos"
        contracts_headers = ["ID Contrato", "NIT", "Monto", "Fecha Inicio", "Fecha Fin", "Razon Social", "Concepto", "Estado"]
        contracts_rows = [contracts_headers]
        
        for c in sheets_utils.INITIAL_MOCK_DATA["contracts"]:
            contracts_rows.append([
                c["ID Contrato"],
                c["NIT"],
                c["Monto"],
                c["Fecha Inicio"],
                c["Fecha Fin"],
                c["Razon Social"],
                c["Concepto"],
                c["Estado"]
            ])
            
        print(f"Escribiendo {len(contracts_rows) - 1} contratos en 'Contratos!A1'...")
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Contratos!A1",
            valueInputOption="RAW",
            body={"values": contracts_rows}
        ).execute()
        
        # 2. Preparar datos de "Historial de Aprobaciones"
        history_headers = ["Fecha Evento", "ID Contrato", "NIT", "Valor Factura", "Fecha Factura", "Estado Aprobación", "Metadata"]
        print("Escribiendo encabezados en 'Historial de Aprobaciones!A1'...")
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Historial de Aprobaciones!A1",
            valueInputOption="RAW",
            body={"values": [history_headers]}
        ).execute()
        
        print("\n🎉 ¡GOOGLE SHEETS POBLADO EXITOSAMENTE CON LOS DATOS DE PRUEBA!")
        
    except Exception as e:
        print(f"\n❌ Error al conectar o escribir en Google Sheets: {e}")
        print("Asegúrate de que la hoja de cálculo tiene creadas las pestañas llamadas 'Contratos' e 'Historial de Aprobaciones'.")

if __name__ == "__main__":
    populate()
