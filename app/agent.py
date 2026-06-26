import datetime
from typing import Dict, Any, Generator

from google.adk.workflow import Workflow, START, node, Edge
from google.adk.events.event import Event
from google.adk.events import RequestInput
from google.adk.agents.context import Context
from google.adk.apps import App

from app.schemas import InvoiceInput, WorkflowState, HumanReviewResponse, ExpirationReviewResponse
from app import sheets_utils
from app import security


@node
def guard_security(node_input: InvoiceInput) -> Event:
    """
    Nodo de seguridad determinista. Analiza si la entrada contiene intentos de inyección.
    """
    is_safe, error_msg = security.analyze_input_for_injection(
        **node_input.model_dump()
    )
    if not is_safe:
        return Event(
            output=None,
            route="unsafe",
            state={
                "is_safe": False,
                "safety_alert": error_msg,
                "approval_status": "blocked"
            }
        )
    return Event(output=node_input, route="safe")


@node
def block_and_notify(ctx: Context) -> Dict[str, Any]:
    """
    Nodo para manejar y reportar intentos de inyección detectados.
    """
    alert = ctx.state.get("safety_alert", "Inyección sospechosa detectada.")
    return {
        "status": "blocked",
        "message": f"EJECUCIÓN ABORTADA POR SEGURIDAD: {alert}"
    }


@node
def check_auto_approval(ctx: Context, node_input: InvoiceInput) -> Event:
    """
    Nodo que evalúa las condiciones deterministas para la autoaprobación de la factura.
    """
    id_contrato = node_input.id_contrato
    contract = sheets_utils.get_contract(id_contrato)
    
    # Aseguramos guardar el input en el estado para recuperarlo en nodos asíncronos (usando estilo diccionario)
    ctx.state["invoice"] = node_input.model_dump()
    
    # 1. Si el contrato no existe (o no se encuentra coincidencia)
    if not contract:
        ctx.state["contract_data"] = None
        return Event(
            output={
                "id_contrato": id_contrato,
                "status": "ignored",
                "reason": f"Contrato {id_contrato} no existe o no tiene coincidencia en Sheets."
            },
            route="ignored",
            state={"contract_data": None}
        )
        
    ctx.state["contract_data"] = contract
    
    # 1. Validación de coincidencia de NIT (si no coincide, se auto-rechaza de inmediato)
    if node_input.nit != contract["NIT"]:
        sheets_utils.add_approval_history(
            id_contrato=id_contrato,
            nit=node_input.nit,
            valor=node_input.valor,
            fecha_factura=node_input.fecha,
            estado_aprobacion="auto_rejected",
            metadata={"razon": f"Discrepancia de NIT: NIT de la factura ({node_input.nit}) no coincide con el del contrato ({contract['NIT']})"}
        )
        return Event(
            output={
                "status": "rejected",
                "reason": f"El NIT de la factura ({node_input.nit}) no coincide con el NIT del contrato ({contract['NIT']})."
            },
            route="auto_rejected",
            state={"approval_status": "rejected", "contract_data": contract}
        )

    # Validar fechas
    try:
        fecha_factura = datetime.datetime.strptime(node_input.fecha, "%Y-%m-%d").date()
        fecha_fin = datetime.datetime.strptime(contract["Fecha Fin"], "%Y-%m-%d").date()
    except Exception as e:
        # Error parsing fechas, requiere revisión humana
        return Event(
            output=node_input,
            route="needs_review",
            state={"contract_data": contract}
        )
        
    diferencia_dias = (fecha_factura - fecha_fin).days
    
    # 2. Si la fecha supera por más de 30 días la fecha fin (Autorechazo)
    if diferencia_dias > 30:
        sheets_utils.add_approval_history(
            id_contrato=id_contrato,
            nit=node_input.nit,
            valor=node_input.valor,
            fecha_factura=node_input.fecha,
            estado_aprobacion="auto_rejected",
            metadata={"razon": f"Factura emitida {diferencia_dias} días después de la Fecha Fin"}
        )
        return Event(
            output={
                "status": "rejected",
                "reason": f"Factura emitida {diferencia_dias} días después del fin del contrato (máximo 30)"
            },
            route="auto_rejected",
            state={"approval_status": "rejected", "contract_data": contract}
        )
        
    # Guardar en estado si el contrato requiere revisión de vencimiento posterior
    needs_expiration = False
    if diferencia_dias > 0 or (-15 <= diferencia_dias <= 0):
        ctx.state["needs_expiration_review"] = True
        needs_expiration = True
        
    monto_referencia = contract["Monto"]
    if monto_referencia <= 0:
        return Event(
            output=node_input,
            route="needs_review",
            state={"contract_data": contract}
        )
        
    desvio = abs(node_input.valor - monto_referencia) / monto_referencia
    
    if desvio <= 0.05:
        # Se cumplen todas las condiciones -> Auto-Aprobación
        sheets_utils.add_approval_history(
            id_contrato=id_contrato,
            nit=node_input.nit,
            valor=node_input.valor,
            fecha_factura=node_input.fecha,
            estado_aprobacion="auto_approved",
            metadata={"desvio_porcentaje": f"{desvio * 100:.2f}%"}
        )
        
        # Si requiere revisión de vencimiento, vamos directamente allí pasando la aprobación de la factura
        if needs_expiration:
            ctx.state["needs_expiration_review"] = False
            ctx.state["invoice_approval_result"] = {
                "status": "auto_approved",
                "id_contrato": id_contrato,
                "desvio": f"{desvio * 100:.2f}%"
            }
            return Event(
                output=node_input,
                route="vencimiento_review",
                state={"approval_status": "auto_approved", "contract_data": contract}
            )
            
        return Event(
            output={
                "status": "auto_approved",
                "id_contrato": id_contrato,
                "desvio": f"{desvio * 100:.2f}%"
            },
            route="auto_approved",
            state={"approval_status": "auto_approved", "contract_data": contract}
        )
    else:
        # Fuera de rango de desvío
        return Event(
            output=node_input,
            route="needs_review",
            state={"contract_data": contract, "needs_expiration_review": needs_expiration}
        )


@node
def auto_approved(node_input: dict) -> dict:
    return {
        "result": "success",
        "detail": f"Factura auto-aprobada con éxito para el contrato {node_input.get('id_contrato')}.",
        "data": node_input
    }


@node
def auto_rejected(node_input: dict) -> dict:
    return {
        "result": "rejected",
        "detail": node_input.get("reason", "Factura auto-rechazada."),
        "data": node_input
    }


@node
def auto_ignored(node_input: dict) -> dict:
    return {
        "result": "ignored",
        "detail": node_input.get("reason", "Factura ignorada automáticamente porque el contrato no existe."),
        "data": node_input
    }


@node
def request_human_review(ctx: Context, node_input: InvoiceInput) -> Generator[RequestInput, Any, Any]:
    """
    Nodo interactivo (HITL). Pausa la ejecución para solicitar revisión de la factura.
    """
    contract = ctx.state.get("contract_data")
    monto_ref = contract["Monto"] if contract else 0.0
    desvio_porc = (abs(node_input.valor - monto_ref) / monto_ref * 100) if monto_ref > 0 else 0.0
    
    mensaje = (
        f"REVISIÓN MANUAL REQUERIDA para Factura de Contrato '{node_input.id_contrato}'.\n"
        f"Detalles Factura: NIT: {node_input.nit}, Fecha: {node_input.fecha}, Valor: {node_input.valor}\n"
        f"Detalles Contrato de Referencia: NIT: {contract.get('NIT') if contract else 'N/A'}, Monto Contractual: {monto_ref}\n"
        f"Desvío Detectado: {desvio_porc:.2f}%\n"
        f"Por favor, indica si apruebas la factura y si deseas actualizar el monto del contrato en sheets."
    )
    yield RequestInput(
        message=mensaje,
        payload={"invoice": node_input.model_dump(), "contract": contract},
        response_schema=HumanReviewResponse
    )


@node
def apply_sheets_update(ctx: Context, node_input: HumanReviewResponse) -> Event:
    """
    Nodo que aplica la decisión humana sobre la factura y actualiza la base de datos si es requerido.
    """
    invoice_dict = ctx.state.get("invoice")
    invoice = InvoiceInput(**invoice_dict) if invoice_dict else None
    
    ctx.state["human_decision"] = node_input.model_dump()
    
    id_contrato = invoice.id_contrato if invoice else "UNKNOWN"
    nit = invoice.nit if invoice else "UNKNOWN"
    valor = invoice.valor if invoice else 0.0
    fecha = invoice.fecha if invoice else "UNKNOWN"
    
    needs_expiration = ctx.state.get("needs_expiration_review", False)
    
    if node_input.aprobar:
        metadata = {"comentario": node_input.comentario or ""}
        if node_input.actualizar_monto and invoice:
            sheets_utils.update_contract_monto(id_contrato, invoice.valor)
            metadata["monto_actualizado"] = True
            metadata["nuevo_monto"] = invoice.valor
            
        sheets_utils.add_approval_history(
            id_contrato=id_contrato,
            nit=nit,
            valor=valor,
            fecha_factura=fecha,
            estado_aprobacion="approved",
            metadata=metadata
        )
        
        if needs_expiration:
            ctx.state["needs_expiration_review"] = False
            ctx.state["invoice_approval_result"] = {
                "status": "approved",
                "id_contrato": id_contrato,
                "comentario": node_input.comentario
            }
            return Event(
                output=invoice,
                route="vencimiento_review",
                state={"approval_status": "approved"}
            )
            
        return Event(
            output={
                "status": "approved",
                "id_contrato": id_contrato,
                "comentario": node_input.comentario
            },
            route="approved",
            state={"approval_status": "approved"}
        )
    else:
        sheets_utils.add_approval_history(
            id_contrato=id_contrato,
            nit=nit,
            valor=valor,
            fecha_factura=fecha,
            estado_aprobacion="rejected",
            metadata={"comentario": node_input.comentario or "", "razon": "Rechazo manual"}
        )
        
        if needs_expiration:
            ctx.state["needs_expiration_review"] = False
            ctx.state["invoice_approval_result"] = {
                "status": "rejected",
                "id_contrato": id_contrato,
                "comentario": node_input.comentario
            }
            return Event(
                output=invoice,
                route="vencimiento_review",
                state={"approval_status": "rejected"}
            )
            
        return Event(
            output={
                "status": "rejected",
                "id_contrato": id_contrato,
                "comentario": node_input.comentario
            },
            route="rejected",
            state={"approval_status": "rejected"}
        )


@node
def request_expiration_review(ctx: Context, node_input: InvoiceInput) -> Generator[RequestInput, Any, Any]:
    """
    Nodo interactivo (HITL). Pausa la ejecución debido a contrato vencido en ventana de pospago.
    """
    contract = ctx.state.get("contract_data")
    fecha_fin = contract.get("Fecha Fin") if contract else "N/A"
    
    mensaje = (
        f"CONTROL DE VENCIMIENTO: El contrato '{node_input.id_contrato}' está vencido o próximo a vencer (Fecha Fin registrada: '{fecha_fin}').\n"
        f"Por favor, selecciona una acción: renovar el contrato (definiendo una nueva Fecha Fin de prórroga), inactivar el contrato, o no hacer nada (se rechazará el cobro actual sin alterar el contrato)."
    )
    yield RequestInput(
        message=mensaje,
        payload={"invoice": node_input.model_dump(), "contract": contract},
        response_schema=ExpirationReviewResponse
    )


@node
def apply_expiration_action(ctx: Context, node_input: ExpirationReviewResponse) -> Event:
    """
    Nodo que aplica la acción elegida por el usuario sobre un contrato vencido.
    """
    invoice_dict = ctx.state.get("invoice")
    invoice = InvoiceInput(**invoice_dict) if invoice_dict else None
    
    ctx.state["expiration_decision"] = node_input.model_dump()
    id_contrato = invoice.id_contrato if invoice else "UNKNOWN"
    nit = invoice.nit if invoice else "UNKNOWN"
    valor = invoice.valor if invoice else 0.0
    fecha = invoice.fecha if invoice else "UNKNOWN"
    
    accion = node_input.accion.lower()
    
    if accion == "renovar":
        nueva_fecha = node_input.nueva_fecha_fin
        if not nueva_fecha:
            # Si no se provee nueva fecha, asumimos que no se puede renovar y se rechaza
            return Event(
                output={"status": "rejected", "reason": "Renovación solicitada sin proporcionar una nueva fecha fin."},
                route="rejected",
                state={"approval_status": "rejected"}
            )
        sheets_utils.update_contract_fecha_fin(id_contrato, nueva_fecha)
        
        # Si la factura ya fue pre-aprobada o rechazada en el paso anterior, devolvemos ese resultado final
        invoice_result = ctx.state.get("invoice_approval_result")
        if invoice_result:
            status = invoice_result.get("status")
            if status in ["approved", "auto_approved"]:
                return Event(output=invoice_result, route="approved", state={"approval_status": status})
            else:
                return Event(output=invoice_result, route="rejected", state={"approval_status": "rejected"})
                
        # Reintentamos el proceso de validación sobre el mismo contrato con la nueva fecha fin ya persistida
        return Event(output=invoice, route="retry")
        
    elif accion == "inactivar":
        sheets_utils.inactivate_contract(id_contrato)
        sheets_utils.add_approval_history(
            id_contrato=id_contrato,
            nit=nit,
            valor=valor,
            fecha_factura=fecha,
            estado_aprobacion="rejected",
            metadata={"razon": "Contrato inactivado por decisión del usuario."}
        )
        return Event(
            output={"status": "rejected", "reason": f"Contrato {id_contrato} marcado como Inactivo. Factura rechazada."},
            route="rejected",
            state={"approval_status": "rejected"}
        )
        
    else: # no_hacer_nada o similar
        sheets_utils.add_approval_history(
            id_contrato=id_contrato,
            nit=nit,
            valor=valor,
            fecha_factura=fecha,
            estado_aprobacion="rejected",
            metadata={"razon": "Rechazado manualmente en control de vencimiento (No hacer nada)."}
        )
        return Event(
            output={"status": "rejected", "reason": f"Se rechazó la solicitud actual en el control de vencimiento del contrato {id_contrato} (No hacer nada)."},
            route="rejected",
            state={"approval_status": "rejected"}
        )


@node
def final_action_approved(node_input: dict) -> dict:
    return {
        "result": "approved",
        "detail": f"Flujo interactivo completado. Factura aprobada para {node_input.get('id_contrato')}.",
        "data": node_input
    }


@node
def final_action_rejected(node_input: dict) -> dict:
    return {
        "result": "rejected",
        "detail": node_input.get("reason", "Flujo interactivo completado. Factura rechazada."),
        "data": node_input
    }


# Definición del flujo del Grafo
root_agent = Workflow(
    name="workflow_gastos_recurrentes",
    input_schema=InvoiceInput,
    state_schema=WorkflowState,
    edges=[
        Edge(from_node=START, to_node=guard_security),
        Edge(from_node=guard_security, to_node=block_and_notify, route="unsafe"),
        Edge(from_node=guard_security, to_node=check_auto_approval, route="safe"),
        Edge(from_node=check_auto_approval, to_node=auto_approved, route="auto_approved"),
        Edge(from_node=check_auto_approval, to_node=auto_rejected, route="auto_rejected"),
        Edge(from_node=check_auto_approval, to_node=auto_ignored, route="ignored"),
        
        # Flujo de Revisión de Facturas (Desvíos / Discrepancias)
        Edge(from_node=check_auto_approval, to_node=request_human_review, route="needs_review"),
        Edge(from_node=request_human_review, to_node=apply_sheets_update),
        Edge(from_node=apply_sheets_update, to_node=final_action_approved, route="approved"),
        Edge(from_node=apply_sheets_update, to_node=final_action_rejected, route="rejected"),
        Edge(from_node=apply_sheets_update, to_node=request_expiration_review, route="vencimiento_review"),
        
        # Flujo de Control de Vencimientos / Ventana de Pospago
        Edge(from_node=check_auto_approval, to_node=request_expiration_review, route="vencimiento_review"),
        Edge(from_node=request_expiration_review, to_node=apply_expiration_action),
        Edge(from_node=apply_expiration_action, to_node=check_auto_approval, route="retry"), # Reintento condicional (Ciclo)
        Edge(from_node=apply_expiration_action, to_node=final_action_rejected, route="rejected"),
        Edge(from_node=apply_expiration_action, to_node=final_action_approved, route="approved")
    ]
)

app = App(
    root_agent=root_agent,
    name="app",
)
