from pydantic import BaseModel, Field
from typing import Optional

class InvoiceInput(BaseModel):
    id_contrato: str = Field(..., description="ID único del contrato a validar")
    nit: str = Field(..., description="NIT del emisor de la factura")
    fecha: str = Field(..., description="Fecha de la factura en formato YYYY-MM-DD")
    valor: float = Field(..., description="Valor facturado")
    concepto: str = Field("", description="Concepto o descripción detallada de la factura")


class HumanReviewResponse(BaseModel):
    aprobar: bool = Field(..., description="¿Aprobar la factura a pesar del desvío o discrepancia?")
    actualizar_monto: bool = Field(False, description="¿Actualizar el monto de referencia del contrato en Sheets?")
    comentario: Optional[str] = Field(None, description="Comentario o justificación del aprobador")


class ExpirationReviewResponse(BaseModel):
    accion: str = Field(..., description="Acción sobre el contrato: 'renovar', 'inactivar' o 'no_hacer_nada'")
    nueva_fecha_fin: Optional[str] = Field(None, description="Nueva fecha de finalización del contrato (YYYY-MM-DD) si la acción es 'renovar'")


class WorkflowState(BaseModel):
    invoice: Optional[InvoiceInput] = None
    contract_data: Optional[dict] = None
    is_safe: bool = True
    safety_alert: Optional[str] = None
    approval_status: Optional[str] = None # 'auto_approved', 'approved', 'rejected', 'blocked'
    needs_update_sheets: bool = False
    human_decision: Optional[HumanReviewResponse] = None
    expiration_decision: Optional[ExpirationReviewResponse] = None
    needs_expiration_review: bool = False
    invoice_approval_result: Optional[dict] = None

