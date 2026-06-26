import asyncio
import json
import sys
import os

# Asegurar que la carpeta gastos-recurrentes esté en el path de importación
sys.path.append("/Users/davidcamelo/Documents/AntiGravity/GastosRecurrentes/gastos-recurrentes")

from app.agent import app
from app import sheets_utils
from google.adk.runners import InMemoryRunner
from google.genai import types

async def run_hitl_scenario_1_monto():
    """
    Escenario 1: Factura con desvío (7%).
    1. Se inicia y suspende pidiendo revisión.
    2. El humano aprueba y solicita actualizar el monto en Sheets.
    3. El flujo termina como 'approved' y se verifica que el monto contractual se actualizó a 107.0.
    """
    print("\n==========================================")
    print("EJECUTANDO ESCENARIO HITL 1: DESVÍO DE MONTO (APROBACIÓN + ACTUALIZACIÓN BD)")
    print("==========================================")
    
    # Reset de la base de datos simulada
    sheets_utils._save_db(sheets_utils.INITIAL_MOCK_DATA)
    
    runner = InMemoryRunner(app=app)
    session = await runner.session_service.create_session(
        app_name="app", user_id="test_user"
    )
    
    # 1. Enviar factura con desvío
    invoice_data = {
        "id_contrato": "CON-101",
        "nit": "123456789-0",
        "fecha": "2026-06-25",
        "valor": 107.0  # Monto de referencia es 100.0 (7% desvío)
    }
    
    print(f"Paso 1: Iniciando ejecución con factura: {invoice_data}")
    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=json.dumps(invoice_data))]
    )
    
    # Correr hasta la suspensión
    request_input_event = None
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=message
    ):
        # Buscamos eventos de RequestInput
        if hasattr(event, "message") and event.message and event.message.parts and event.message.parts[0].function_call:
            print(f"\n[Suspension Detectada] Mensaje de solicitud: {event.message}")
            request_input_event = event
            
    assert request_input_event is not None, "El flujo debió suspenderse pidiendo revisión manual."
    
    # Obtener el ID de la interrupción / llamada de función
    func_call = request_input_event.message.parts[0].function_call
    interrupt_id = func_call.id
    
    # 2. Reanudar enviando la decisión humana (HumanReviewResponse) como FunctionResponse
    human_decision = {
        "aprobar": True,
        "actualizar_monto": True,
        "comentario": "Desvío justificado por aumento de tarifas de servicio."
    }
    
    print(f"\nPaso 2: Reanudando flujo con decisión humana (FunctionResponse): {human_decision}")
    resume_message = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    name="adk_request_input",
                    id=interrupt_id,
                    response=human_decision
                )
            )
        ]
    )
    
    final_output = None
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=resume_message
    ):
        if event.output is not None:
            final_output = event.output
            
    print(f"\nResultado Final: {final_output}")
    assert final_output is not None
    assert final_output.get("result") == "approved"
    assert final_output.get("data", {}).get("status") == "approved"
    
    # 3. Validar cambios persistidos en Sheets simulado
    updated_contract = sheets_utils.get_contract("CON-101")
    print(f"\nContrato actualizado en BD: {updated_contract}")
    assert updated_contract["Monto"] == 107.0, "El monto contractual debió actualizarse a 107.0"
    
    # Validar historial
    history = sheets_utils.get_history()
    last_event = history[-1]
    print(f"Último evento de auditoría: {last_event}")
    assert last_event["ID Contrato"] == "CON-101"
    assert last_event["Estado Aprobación"] == "approved"
    assert last_event["Metadata"].get("monto_actualizado") is True
    
    print("\n🎉 ¡ESCENARIO HITL 1 PASÓ EXITOSAMENTE!")


async def run_hitl_scenario_2_vencimiento():
    """
    Escenario 2: Factura vencida en margen de pospago (CON-102 venció hace 5 días).
    1. Se inicia y suspende pidiendo acción de vencimiento.
    2. El aprobador selecciona 'renovar' y amplía la fecha fin a '2027-06-20'.
    3. El flujo ejecuta el ciclo (retry) de vuelta a check_auto_approval.
    4. El contrato ya está vigente y se auto-aprueba la factura con éxito!
    """
    print("\n==========================================")
    print("EJECUTANDO ESCENARIO HITL 2: CONTROL VENCIMIENTOS (RENOVACIÓN + CICLO + AUTOAPROBACIÓN)")
    print("==========================================")
    
    # Reset de la base de datos simulada
    sheets_utils._save_db(sheets_utils.INITIAL_MOCK_DATA)
    
    runner = InMemoryRunner(app=app)
    session = await runner.session_service.create_session(
        app_name="app", user_id="test_user"
    )
    
    # 1. Enviar factura con fecha vencida de 5 días
    invoice_data = {
        "id_contrato": "CON-102",  # Fecha Fin original: 2026-06-20
        "nit": "987654321-1",
        "fecha": "2026-06-25",     # 5 días después de Fecha Fin
        "valor": 500.0             # Monto de referencia es 500.0
    }
    
    print(f"Paso 1: Iniciando ejecución con factura: {invoice_data}")
    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=json.dumps(invoice_data))]
    )
    
    request_input_event = None
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=message
    ):
        if hasattr(event, "message") and event.message and event.message.parts and event.message.parts[0].function_call:
            print(f"\n[Suspension Detectada] Mensaje de solicitud: {event.message}")
            request_input_event = event
            
    assert request_input_event is not None, "El flujo debió suspenderse por control de vencimientos."
    
    # Obtener el ID de la interrupción / llamada de función
    func_call = request_input_event.message.parts[0].function_call
    interrupt_id = func_call.id
    
    # 2. Reanudar con acción de Renovación (ExpirationReviewResponse) como FunctionResponse
    expiration_decision = {
        "accion": "renovar",
        "nueva_fecha_fin": "2027-06-20"  # Prorrogamos el contrato 1 año
    }
    
    print(f"\nPaso 2: Reanudando flujo indicando renovación del contrato: {expiration_decision}")
    resume_message = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    name="adk_request_input",
                    id=interrupt_id,
                    response=expiration_decision
                )
            )
        ]
    )
    
    final_output = None
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=resume_message
    ):
        if event.output is not None:
            final_output = event.output
            
    print(f"\nResultado Final tras ciclo de reintento: {final_output}")
    assert final_output is not None
    # Como el contrato se renovó, el grafo redirigió de vuelta a check_auto_approval.
    # El contrato ahora vence en 2027-06-20, por lo que la factura del 2026-06-25 es 100% vigente.
    # El NIT coincide, el valor (500) es idéntico, por lo tanto, ¡se debió autoaprobar con éxito!
    assert final_output.get("result") == "success"
    assert final_output.get("data", {}).get("status") == "auto_approved"
    
    # 3. Validar cambios persistidos en Sheets simulado
    updated_contract = sheets_utils.get_contract("CON-102")
    print(f"\nContrato actualizado en BD: {updated_contract}")
    assert updated_contract["Fecha Fin"] == "2027-06-20", "La fecha fin debió actualizarse a 2027-06-20"
    
    # Validar historial de auditoría
    history = sheets_utils.get_history()
    # Debe haber un registro de autoaprobación final
    last_event = history[-1]
    print(f"Último evento de auditoría en historial: {last_event}")
    assert last_event["ID Contrato"] == "CON-102"
    assert last_event["Estado Aprobación"] == "auto_approved"
    
    print("\n🎉 ¡ESCENARIO HITL 2 PASÓ EXITOSAMENTE!")


async def main():
    await run_hitl_scenario_1_monto()
    await run_hitl_scenario_2_vencimiento()
    print("\n🌟 ¡TODOS LOS ESCENARIOS ASÍNCRONOS HITL SE EJECUTARON Y VALIDARON CON ÉXITO ABSOLUTO!")

if __name__ == "__main__":
    asyncio.run(main())
