# Definición del Flujo del Grafo: agent.py (Hito 3)

Este módulo contiene el núcleo de lógica de control de flujo interactivo del sistema de Gestión de Gastos Recurrentes. Está implementado utilizando la **Graph Workflow API** de ADK 2.0 de Google, modelando un flujo de trabajo asíncrono y robusto que combina validaciones de seguridad deterministas, lógica de negocio automatizada y suspensión interactiva de tipo **Human-in-the-Loop (HITL)** mediante la primitiva `RequestInput`.

---

## Estructura del Grafo de Flujo de Trabajo

El flujo de ejecución es el siguiente:

1. **`START`**: Recibe la factura entrante formateada bajo el esquema estricto de `InvoiceInput`.
2. **`guard_security`**: Analiza si los campos string de la factura contienen inyecciones de código o bypass de reglas.
   - Si se detecta un patrón inseguro, desvía al nodo **`block_and_notify`** (`unsafe`).
   - Si está libre de inyección, avanza a **`check_auto_approval`** (`safe`).
3. **`check_auto_approval`**: Consulta `sheets_utils.py` y aplica las reglas de negocio contractuales:
   - **Auto-Aprobación:** Si el NIT coincide, la fecha del contrato está vigente y el desvío de monto es $\le 5\%$, pasa a **`auto_approved`**.
   - **Auto-Rechazo:** Si la factura fue emitida más de 30 días después del fin del contrato, se auto-rechaza y pasa a **`auto_rejected`**.
   - **Revisión Manual de Factura (HITL):** Si el contrato no existe, no coincide el NIT, o el desvío es $> 5\%$, pasa a **`request_human_review`**.
   - **Control de Vencimiento / Ventana de Pospago (HITL):** Si la factura se emitió después de la `Fecha Fin` pero dentro de los 30 días posteriores de gracia, pasa a **`request_expiration_review`**.

---

## Nodos Definidos y Lógica Human-in-the-Loop

### Nodos de Filtrado y Auto-Decisión
- **`guard_security`**: Filtra intentos de inyección y detiene la ejecución inmediatamente si detecta peligro.
- **`block_and_notify`**: Reporta la alerta de seguridad y aborta la transacción.
- **`check_auto_approval`**: Evalúa todas las reglas de negocio de manera ágil.
- **`auto_approved`**: Registra la aprobación histórica automática y confirma el éxito.
- **`auto_rejected`**: Registra el rechazo automático e informa el motivo.

### Flujo de Revisión de Facturas (Desvíos/Discrepancias)
- **`request_human_review`**: Suspende la ejecución asíncronamente emitiendo un `RequestInput` estructurado basado en el esquema `HumanReviewResponse`. Pregunta si se aprueba la factura y si se actualiza el monto contractual de referencia.
- **`apply_sheets_update`**: Recibe la respuesta del usuario, actualiza el monto en Sheets si fue aprobado y solicitado, registra la bitácora de auditoría histórica, y bifurca hacia aprobación (`approved`) o rechazo (`rejected`).
- **`final_action_approved` / `final_action_rejected`**: Nodos hoja que dan por concluida la transacción manual.

### Flujo de Control de Vencimientos / Ventana de Pospago
- **`request_expiration_review`**: Suspende la ejecución emitiendo un `RequestInput` estructurado basado en el esquema `ExpirationReviewResponse`. Permite al aprobador seleccionar entre: renovar contrato, inactivar contrato o simplemente rechazar la factura.
- **`apply_expiration_action`**: Aplica la decisión del usuario:
  - **Renovar (`retry`):** Actualiza la `Fecha Fin` en Sheets y redirige la ejecución en un **ciclo cerrado** de regreso a `check_auto_approval` para re-evaluar la factura.
  - **Inactivar:** Marca el contrato como "Inactivo", registra el rechazo y pasa a `final_action_rejected`.
  - **Rechazar Factura:** Registra el rechazo manual y pasa a `final_action_rejected`.
