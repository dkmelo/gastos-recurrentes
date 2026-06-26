import os
import json
import uvicorn
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Importar utilidades y agente
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent import app as agent_app
from app import sheets_utils
from google.adk.runners import InMemoryRunner
from google.genai import types

server = FastAPI(
    title="GastosRecurrentes API",
    description="Backend para el sistema de control de Gastos Recurrentes usando ADK 2.0"
)

# Configurar CORS
server.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Almacenamiento en memoria para sesiones activas
# mapea session_id -> {"runner": runner, "session": session}
active_sessions: Dict[str, Dict[str, Any]] = {}
blocked_events: list = []

class InvoiceRequest(BaseModel):
    id_contrato: str
    nit: str
    fecha: str
    valor: float
    concepto: str = ""

class ResumeRequest(BaseModel):
    session_id: str
    interrupt_id: str
    decision: Dict[str, Any]


@server.get("/api/contracts")
def get_contracts():
    """
    Retorna todos los contratos de Google Sheets (real o mock).
    """
    try:
        return sheets_utils.get_all_contracts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@server.get("/api/history")
def get_history():
    """
    Retorna la bitácora histórica de aprobaciones de Google Sheets (real o mock).
    """
    try:
        return sheets_utils.get_history()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@server.post("/api/invoice")
async def process_invoice(req: InvoiceRequest):
    """
    Inicia la ejecución del grafo para una factura entrante.
    Si se detecta una suspensión por HITL, retorna los detalles para interactuar.
    Si se autoaprueba o bloquea, retorna el estado final.
    """
    try:
        # Crear un runner y una sesión de ejecución
        runner = InMemoryRunner(app=agent_app)
        session = await runner.session_service.create_session(
            app_name="app", user_id="web_user"
        )
        
        # Almacenar en sesiones activas para reanudación
        active_sessions[session.id] = {
            "runner": runner,
            "session": session
        }
        
        # Enviar la factura al grafo
        message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=json.dumps(req.model_dump()))]
        )
        
        # Ejecutar hasta que termine o se suspenda
        suspended_event = None
        final_output = None
        
        async for event in runner.run_async(
            user_id="web_user",
            session_id=session.id,
            new_message=message
        ):
            # Comprobar si hay una interrupción / RequestInput
            if hasattr(event, "message") and event.message and event.message.parts and event.message.parts[0].function_call:
                func_call = event.message.parts[0].function_call
                if func_call.name == "adk_request_input":
                    suspended_event = event
                    break
            if event.output is not None:
                final_output = event.output

        if suspended_event:
            func_call = suspended_event.message.parts[0].function_call
            args = func_call.args or {}
            suspension_info = {
                "status": "suspended",
                "session_id": session.id,
                "interrupt_id": func_call.id or args.get("interruptId"),
                "message": args.get("message", "Revisión manual requerida"),
                "payload": args.get("payload", {}),
                "response_schema": args.get("response_schema", {})
            }
            active_sessions[session.id]["suspension"] = suspension_info
            return suspension_info
            
        # Si terminó de inmediato (autoaprobado, autorechazado, o bloqueado por seguridad)
        # Limpiamos la sesión ya terminada
        if session.id in active_sessions:
            del active_sessions[session.id]
            
        if final_output and isinstance(final_output, dict) and final_output.get("status") == "blocked":
            import uuid
            from datetime import datetime
            blocked_events.append({
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "message": final_output.get("message"),
                "id_contrato": req.id_contrato,
                "nit": req.nit,
                "fecha": req.fecha,
                "valor": req.valor,
                "concepto": req.concepto
            })
            
        return {
            "status": "completed",
            "session_id": session.id,
            "output": final_output
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@server.get("/api/pending")
def get_pending_sessions():
    """
    Retorna la lista de todas las sesiones de agente suspendidas (HITL) esperando respuesta humana.
    """
    pending = []
    for s_id, data in active_sessions.items():
        if "suspension" in data:
            pending.append(data["suspension"])
    return {
        "pending": pending,
        "blocked": blocked_events
    }


@server.post("/api/blocked/dismiss/{event_id}")
def dismiss_blocked_event(event_id: str):
    """
    Elimina un evento de bloqueo de seguridad por dismissed.
    """
    global blocked_events
    blocked_events = [e for e in blocked_events if e["id"] != event_id]
    return {"status": "ok"}


@server.post("/api/cron/check")
def trigger_cron_check():
    """
    Ejecuta el chequeo de vencimiento de contratos (simulación cron).
    """
    try:
        from app.cron_check import run_cron_expiration_check
        result = run_cron_expiration_check()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al ejecutar chequeo: {e}")


@server.post("/api/resume")
async def resume_session(req: ResumeRequest):
    """
    Reanuda un flujo de trabajo suspendido enviando la decisión del humano.
    """
    if req.session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="La sesión no existe o ya ha expirado/finalizado.")
        
    try:
        session_data = active_sessions[req.session_id]
        runner = session_data["runner"]
        session = session_data["session"]
        
        # Construir el mensaje de respuesta de la función
        resume_message = types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        name="adk_request_input",
                        id=req.interrupt_id,
                        response=req.decision
                    )
                )
            ]
        )
        
        suspended_event = None
        final_output = None
        
        # Correr el runner de nuevo con la respuesta
        async for event in runner.run_async(
            user_id="web_user",
            session_id=session.id,
            new_message=resume_message
        ):
            if hasattr(event, "message") and event.message and event.message.parts and event.message.parts[0].function_call:
                func_call = event.message.parts[0].function_call
                if func_call.name == "adk_request_input":
                    suspended_event = event
                    break
            if event.output is not None:
                final_output = event.output
                
        if suspended_event:
            func_call = suspended_event.message.parts[0].function_call
            args = func_call.args or {}
            suspension_info = {
                "status": "suspended",
                "session_id": session.id,
                "interrupt_id": func_call.id or args.get("interruptId"),
                "message": args.get("message", "Revisión manual requerida"),
                "payload": args.get("payload", {}),
                "response_schema": args.get("response_schema", {})
            }
            active_sessions[session.id]["suspension"] = suspension_info
            return suspension_info
            
        # Si ya terminó completamente, limpiar la sesión
        if req.session_id in active_sessions:
            del active_sessions[req.session_id]
            
        return {
            "status": "completed",
            "session_id": session.id,
            "output": final_output
        }

        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@server.get("/logo.png")
def get_logo():
    """
    Sirve el logo de la aplicación.
    """
    logo_path = os.path.join(os.path.dirname(__file__), "templates", "logo.png")
    if os.path.exists(logo_path):
        from fastapi.responses import FileResponse
        return FileResponse(logo_path)
    raise HTTPException(status_code=404, detail="Logo no encontrado")


# Servir la interfaz SPA Premium en el endpoint raíz /
@server.get("/", response_class=HTMLResponse)
async def serve_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        # Fallback si por alguna razón no se encuentra el archivo
        return """
        <html>
            <body style="font-family: sans-serif; text-align: center; padding-top: 100px; background: #0f172a; color: white;">
                <h1>GastosRecurrentes UI</h1>
                <p>Archivo templates/index.html no encontrado. Por favor, asegúrese de que el archivo existe.</p>
            </body>
        </html>
        """


if __name__ == "__main__":
    uvicorn.run("main:server", host="0.0.0.0", port=8080, reload=True)
