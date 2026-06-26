#!/usr/bin/env python3
import os
import sys
import json
import datetime
import urllib.request
import urllib.error

# Configurar ruta para poder importar modulos de app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import sheets_utils

API_URL = "http://localhost:8080/api/invoice"

def run_cron_expiration_check():
    print(f"[{datetime.datetime.now().isoformat()}] Iniciando chequeo de vencimiento de contratos (Simulación Cron)...")
    
    try:
        contracts = sheets_utils.get_all_contracts()
    except Exception as e:
        print(f"Error al obtener contratos de Sheets: {e}")
        return {"status": "error", "message": f"Error al obtener contratos: {e}"}

    today = datetime.date.today()
    triggered_count = 0
    alerts_list = []

    for contract in contracts:
        # Solo verificar contratos Activos
        if contract.get("Estado") != "Activo":
            continue
            
        id_contrato = contract.get("ID Contrato")
        fecha_fin_str = contract.get("Fecha Fin")
        nit = contract.get("NIT", "N/A")
        monto = contract.get("Monto", 0.0)
        concepto = contract.get("Concepto", "Servicio")
        
        if not fecha_fin_str:
            continue
            
        try:
            fecha_fin = datetime.datetime.strptime(fecha_fin_str, "%Y-%m-%d").date()
        except Exception:
            print(f"Formato de fecha inválido para contrato {id_contrato}: {fecha_fin_str}")
            continue
            
        # Calcular los días transcurridos desde que expiró (o días que faltan para expirar)
        # Si dias_expirado > 0, significa que ya expiró.
        dias_expirado = (today - fecha_fin).days
        
        # Simular una alerta proactiva si:
        # - El contrato ya expiró y está en el rango de pospago (hasta 30 días)
        # - O si vence muy pronto (por ejemplo, en los próximos 15 días) para prevención.
        should_alert = False
        alert_reason = ""
        
        if 0 < dias_expirado <= 30:
            should_alert = True
            alert_reason = f"Expirado hace {dias_expirado} días (período de gracia de 30 días)"
        elif -15 <= dias_expirado <= 0:
            should_alert = True
            alert_reason = f"Próximo a vencer en {abs(dias_expirado)} días"
            
        if should_alert:
            print(f"\n⚠️ CONTRATO DETECTADO: {id_contrato} ({concepto}) - {alert_reason}")
            print(f"   Fecha Fin: {fecha_fin_str} | Monto de Referencia: {monto}")
            print(f"   >>> Lanzando flujo interactivo en el portal administrativo...")
            
            # Si el contrato aún no ha vencido, simulamos una fecha de cobro 1 día posterior a la Fecha Fin
            # para forzar la activación preventiva de la interrupción manual (HITL).
            if dias_expirado <= 0:
                fecha_simulada = (fecha_fin + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                fecha_simulada = today.strftime("%Y-%m-%d")
                
            payload = {
                "id_contrato": id_contrato,
                "nit": nit,
                "fecha": fecha_simulada,
                "valor": monto  # Usamos el mismo monto para que no haya desvío de dinero, solo alerta de fecha
            }
            
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                API_URL, 
                data=req_data, 
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            session_id = "N/A"
            agent_msg = ""
            status_res = ""
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    res_body = json.loads(response.read().decode("utf-8"))
                    status_res = res_body.get("status", "")
                    if res_body.get("status") == "suspended":
                        session_id = res_body.get("session_id", "")
                        agent_msg = res_body.get("message", "")
                        print(f"   ✅ ÉXITO: Flujo HITL iniciado. ID Sesión: {session_id}")
                        print(f"   Mensaje del Agente: {agent_msg}")
                    else:
                        print(f"   ℹ️ El agente resolvió de inmediato sin suspensión: {res_body.get('status')}")
                triggered_count += 1
                alerts_list.append({
                    "id_contrato": id_contrato,
                    "concepto": concepto,
                    "reason": alert_reason,
                    "session_id": session_id,
                    "message": agent_msg,
                    "status": status_res
                })
            except urllib.error.URLError as e:
                print(f"   ❌ Error al conectar con el servidor backend (puerto 8080): {e}")
                print("   Asegúrate de que el servidor administrativo esté corriendo en http://localhost:8080")
                break
                
    print(f"\n[{datetime.datetime.now().isoformat()}] Chequeo cron completado. Contratos alertados: {triggered_count}\n")
    return {
        "status": "success",
        "triggered_count": triggered_count,
        "alerts": alerts_list
    }

if __name__ == "__main__":
    run_cron_expiration_check()
