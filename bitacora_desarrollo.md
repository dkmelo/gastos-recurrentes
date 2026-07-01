# Bitácora de Desarrollo: GastosRecurrentes

Este archivo registra cronológicamente los avances, decisiones de diseño, modificaciones y validaciones realizadas en el proyecto de Automatización de Gestión de Gastos Recurrentes.

---

## [2026-06-25] Hito 0: Verificación de Entorno y Autenticación (ADC) - Completado

### Actividades Realizadas
1. **Entorno Virtual de Python (3.12):**
   - Se creó y configuró un entorno virtual (`venv`) utilizando **Python 3.12.13** para garantizar total compatibilidad con las librerías del Agent Development Kit (`google-adk`).
   - Se instalaron con éxito las dependencias base en el entorno virtual (`google-adk[gcp,eval]`, `fastapi`, `uvicorn`, `pydantic`, `jinja2`, entre otras).
2. **Verificación de Herramientas CLI:**
   - Se validó que `agents-cli` está instalado en `/Users/davidcamelo/.local/bin/agents-cli` (v0.5.0).
   - Se validó que `gcloud` está configurado correctamente con la cuenta activa `david.camelo@isec.com.co`.
3. **Validación de ADC (Application Default Credentials):**
   - Se ejecutó un script de verificación dentro del `venv` importando `google.auth`. 
   - **Resultado:** Autenticación exitosa contra el proyecto de Google Cloud `ia-agentica-dac`.
4. **Scaffolding Inicial del Agente:**
   - Se ejecutó `agents-cli scaffold create gastos-recurrentes --prototype --agent adk -y` para generar la estructura inicial del agente en la subcarpeta `gastos-recurrentes`.

### Estado de los Componentes
- `venv`: Configurado y listo (Python 3.12.13).
- `google-adk`: Instalado y verificado.
- `gcloud` / `ADC`: Activo y autenticado.
- Proyecto GCP: `ia-agentica-dac`.

---

## [2026-06-25] Hito 1: Setup y Simulación de Almacenamiento (Sheets mock) - Completado

### Actividades Realizadas
1. **Esquemas de Entrada y Estado (Pydantic):**
   - Se implementaron en `app/schemas.py` los modelos base de validación y de rastreo de estado: `InvoiceInput` (factura entrante con validación de tipos) y `WorkflowState` (para rastrear el flujo y las decisiones).
2. **Simulación de Base de Datos Google Sheets:**
   - Se desarrolló `app/sheets_utils.py` para leer y escribir sobre una simulación JSON local (`sheets_mock.json`).
   - Se configuraron datos contractuales iniciales que representan casos activos, próximos a vencer, expirados (con ventana de renovación o listos para auto-rechazo), e inactivos (para verificar que se omitan en las búsquedas).
3. **Documentación del Módulo de Persistencia:**
   - Se redactó `app/sheets_utils.md` como el archivo homólogo de documentación del componente.
4. **Validación de Funcionalidad:**
   - Se creó un script de verificación automatizado en el directorio `scratch` que importó con éxito los módulos y corrió un conjunto de pruebas unitarias locales sobre la lectura, filtrado (omisión de inactivos), actualización de montos e inserción histórica de auditoría.
   - **Resultado:** ¡Todas las pruebas pasaron con éxito!

---

## [2026-06-25] Hito 2: Implementación del Grafo Determinista (Fase de Autoaprobación) - Completado

### Actividades Realizadas
1. **Filtro Determinista de Seguridad (`app/security.py`):**
   - Implementación de lógica regex estricta para detener intentos de bypass (Prompt Injection) en campos string de la factura antes de interactuar con el LLM u otros nodos.
2. **Desarrollo del Grafo de Flujo (`app/agent.py`):**
   - Creación del objeto `Workflow` conectando los nodos `START`, `guard_security`, `check_auto_approval`, `block_and_notify`, `auto_approved` y `auto_rejected`.
   - Se usaron objetos `Edge` explícitos de la API de grafos de ADK 2.0 para definir rutas condicionales de negocio seguras y robustas.
   - Configuración de placeholders para los flujos interactivos (`needs_review_placeholder` y `vencimiento_review_placeholder`) que se completarán en el Hito 3.
3. **Documentación Homóloga:**
   - Redacción de `app/security.md` y `app/agent.md` detallando el rol de cada nodo y las expresiones de seguridad detectadas.
4. **Validación Completa en Memoria (`scratch/test_graph.py`):**
   - Desarrollo de un suite de testeo end-to-end asíncrono utilizando `InMemoryRunner` de ADK 2.0.
   - Se verificaron los 5 escenarios de negocio definidos en el plan de evaluación:
     - **Caso 1 (Autoaprobación Exacta):** Retornó de forma exitosa `auto_approved` con desvío de `0.00%`.
     - **Caso 2 (Desvío del 3% Permitido):** Retornó exitosamente `auto_approved` con desvío de `3.00%`.
     - **Caso 3 (Desvío del 7% Fuera de Rango):** Dirigido correctamente a `pending_human_review`.
     - **Caso 4a (Expirado > 30 días):** Auto-rechazado de forma inmediata con estado `rejected` por exceder el margen de pospago.
     - **Caso 4b (Expirado <= 30 días):** Dirigido correctamente al flujo de control y renovación `pending_expiration_review`.
     - **Caso 5 (Prompt Injection):** Detectado instantáneamente en el NIT de entrada, abortando con estado `blocked` y mensaje de alerta sin interactuar con ningún LLM.
   - **Resultado:** ¡Todos los escenarios asertivos pasaron con 100% de éxito!

---

## [2026-06-25] Hito 3: Integración de Human-in-the-Loop (HITL) - Completado

### Actividades Realizadas
1. **Modelos de Decisión (Pydantic):**
   - Se agregaron los esquemas estrictos `HumanReviewResponse` y `ExpirationReviewResponse` en `app/schemas.py` para capturar la respuesta humana estructurada.
2. **Nodos Interactivos del Grafo (`app/agent.py`):**
   - Implementación de lógica asíncrona real en el grafo mediante `RequestInput` de ADK 2.0.
   - Nodos creados: `request_human_review`, `apply_sheets_update`, `request_expiration_review` y `apply_expiration_action`.
3. **Ciclo de Reintento Cerrado (Retry Loop):**
   - Si el contrato vencido es renovado mediante la decisión humana, el flujo vuelve automáticamente a `check_auto_approval` para re-evaluarse bajo el nuevo estado del contrato, logrando auto-aprobarse de forma determinista.
4. **Depuración y Validación de la Suite de Pruebas (`scratch/test_hitl.py`):**
   - Se depuró la captura del `interrupt_id` desde `event.message.parts[0].function_call.id`.
   - Se resolvió la reanudación asíncrona en los tests de `InMemoryRunner` construyendo el payload con `types.Part(function_response=types.FunctionResponse(...))` de forma directa.
   - **Resultados de las Pruebas:**
     - **Escenario 1 (Desvío de Monto):** Suspensión -> Reanudación aprobando factura y actualizando monto contractual -> Modificación de Sheets mock -> Finalizado como aprobado exitosamente.
      - **Escenario 2 (Control de Vencimiento):** Suspensión -> Reanudación renovando contrato -> Actualización de fecha fin -> Re-ejecución del flujo (ciclo de reintento) -> Auto-aprobación exitosa y auditada.

---

## [2026-06-25] Hito 4: Servidor FastAPI, Conexión a Google Sheets y UI SPA Premium - Completado

### Actividades Realizadas
1. **Integración Híbrida de Google Sheets (`app/sheets_utils.py`):**
   - Implementado soporte oficial para Google Sheets API (`google-api-python-client`) utilizando Application Default Credentials (ADC).
   - Añadido interruptor por entorno (`USE_REAL_SHEETS=True/False`) para alternar fluidamente entre la base de datos real de Sheets y la simulación local `sheets_mock.json` sin alterar las firmas ni lógica del agente.
2. **Servidor API de FastAPI (`app/main.py`):**
   - Desarrollado el servidor FastAPI levantado exitosamente en el puerto `8080`.
   - Creados endpoints unificados: `/api/contracts` y `/api/history` para lectura de datos; `/api/invoice` para iniciar la ejecución del agente (retornando inmediato el estado completo o de suspensión de interrupción); y `/api/resume` para continuar hilos suspendidos mediante payloads de decisión humana.
3. **Interfaz de Usuario SPA Premium (`app/templates/index.html`):**
   - Creada una Single Page Application con un diseño de impacto visual "wow" (Glassmorphism de fondo oscuro, tipografías premium, animaciones sutiles y estados de color).
   - Diseñado un **Monitor de Ejecución en tiempo real** que despliega el avance del agente. Si ocurre una suspensión, despliega paneles dinámicos interactivos para que el usuario mismo decida si aprueba la factura o renueva el contrato.
   - Cuenta con una sección de acceso rápido para inyectar casos de prueba preestablecidos (Autoaprobación, desvío 3%, desvío 7% para interrupción de monto, contrato expirado en ventana de pospago para interrupción de vencimiento, y Prompt Injection para bloqueo).
4. **Verificación y Puesta en Marcha:**
   - Servidor FastAPI levantado y corriendo activamente en segundo plano. La interfaz SPA ya se encuentra servida de forma completa y reactiva.

---

## [2026-06-25] Hito 5: Desacoplamiento de Ingestión (Port 8181) y Webhook asíncrono - Completado

### Actividades Realizadas
1. **Portal de Facturación Electrónica para Proveedores (`app/billing_server.py` y `app/templates/billing_index.html`):**
   - Desarrollado un servidor de frontend independiente en el puerto **`8181`** que sirve un portal para proveedores.
   - Cuenta con un formulario premium con diseño Glassmorphic para simular la emisión de cargos o facturas recurrentes (`ID Contrato`, `NIT`, `Fecha`, `Valor`).
   - Implementado un panel de acceso rápido para inyectar con un solo clic los 5 escenarios típicos de negocio.
   - Consume directamente el webhook del agente (`POST http://localhost:8080/api/invoice`) y muestra notificaciones elegantes de éxito, suspensión de flujo o error.
2. **Webhook & Polling Asíncrono de Intervenciones (`app/main.py`):**
   - El endpoint de facturación en el puerto `8080` actúa ahora como un receptor desacoplado (Webhook) que almacena ejecuciones suspendidas asíncronamente en memoria.
   - Creado un nuevo endpoint unificado `GET /api/pending` que expone la lista de todas las interrupciones manuales activas a la espera de aprobación.
3. **Rediseño Completo del Panel Administrativo HITL (`app/templates/index.html`):**
   - Eliminados todos los botones de simulación o formularios de entrada de facturas en la interfaz de administración del puerto `8080`.
   - Implementado **Polling en tiempo real** (cada 3 segundos) para consultar de manera asíncrona la lista de interrupciones manuales (HITL) pendientes en el backend.
   - Al hacer clic sobre cualquier tarea pendiente de la lista izquierda, el monitor de ejecución derecho carga dinámicamente el diagrama de flujo y despliega los formularios interactivos para aprobar, rechazar o renovar el contrato en Sheets.
4. **Verificación Integrada End-to-End:**
   - Iniciados exitosamente ambos micro-servicios en puertos concurrentes e independientes (`8080` y `8181`). El flujo integrado opera de forma robusta e independiente de cualquier software cliente.

---

## [2026-06-26] Flujo Secuencial Desacoplado de Expiraciones (Caso 2) - Completado

### Actividades Realizadas
1. **Actualización de Schemas (`app/schemas.py`)**:
   * Se añadieron los campos `needs_expiration_review` e `invoice_approval_result` a la clase `WorkflowState` de Pydantic. Esto evita que ADK levante excepciones de validación al persistir estas banderas lógicas de control secuencial durante la sesión.
2. **Definición de Bordes del Grafo (`app/agent.py`)**:
   * Se agregó el borde explícito `Edge(from_node=apply_sheets_update, to_node=request_expiration_review, route="vencimiento_review")` al objeto principal `root_agent`. Esto conecta de manera robusta el final de la revisión por desvío con el inicio del control de vencimiento.
3. **Preservación de Estado Asíncrono (`app/agent.py`)**:
   * Se modificó el nodo `check_auto_approval` de modo que si un contrato califica para control de vencimiento (por expirar en 15 días o menos, o vencido hace menos de 30 días) y tiene desvíos de monto superiores al 5%, se marca `needs_expiration_review = True` y se preserva en el estado del evento retornado hacia el desvío (`needs_review`).
   * Al resolverse el desvío por el administrador en `apply_sheets_update`, el agente rescata esta bandera y redirige asíncronamente a la tarea interactiva de control de vencimiento.
4. **Coherencia Documental de Arquitectura (`project_specs.md`)**:
   * Se actualizó y reescribió por completo el diagrama de flujo Mermaid de especificaciones para reflejar de forma exacta (1-a-1) todos los nombres de nodos, rutas lógicas y ciclos de reintento implementados en el código de Python de `app/agent.py`.
5. **Validación de Relanzamiento**:
   * El servidor uvicorn reanudó su ejecución de manera impecable y se confirmó el correcto funcionamiento de los endpoints con las modificaciones lógicas en caliente.
