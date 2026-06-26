# GastosRecurrentes (Recurring Expense Management) 🚀

Bilingual project documentation (English & Español) describing the recurrent invoice automated processing system built with Google’s **Agent Development Kit (ADK) 2.0** and **Graph Workflow API**.

---

## 🇺🇸 ENGLISH

### Overview
`GastosRecurrentes` is an intelligent, high-performance backoffice system designed to automate the validation, matching, and approval lifecycle of recurring service invoices (e.g., internet, hosting, IT services). It replaces manual review burdens with deterministic checks and cognitive evaluations while gracefully routing exceptions to asynchronous **Human-in-the-Loop (HITL)** flows.

---

### Core Architecture & Features
1. **Deterministic Verification (Non-LLM)**: Matches `id_contrato` (Contract ID) and `valor` (Amount) with reference contracts in Google Sheets using the vendor's `NIT` for cross-validation.
   - **Over 30 days past `Fecha Fin` (End Date)**: Automatically rejected.
   - **Under 30 days past `Fecha Fin` (Grace Period)**: Pauses execution and launches an asynchronous renewal/vencimiento review flow.
   - **Valid & Active**: If deviation is $\le 5\%$, the invoice is automatically approved.
2. **Cognitive Security Filter (Pure LLM)**: Powered by `gemini-2.5-flash` at `temperature=0.0`. It performs holistic semantic audits on all payload inputs to block **Prompt Injections**, rule-bypass attempts, or imperative instructions in any language (English, Spanish, Portuguese, German, etc.) without relying on brittle regex patterns.
3. **Hybrid Auth Bypass (Sheets + User ADC)**: Automatically manages credentials. It temporarily hides Google Sheets Service Account variables during Gemini SDK initialization to force Vertex AI to load the user's **Application Default Credentials (ADC)**, restoring it immediately to keep Sheets syncing smoothly.
4. **Asynchronous Human-In-The-Loop**: Beautiful web-based admin panel to approve discrepancies, renew contracts, or mark them as inactive.

---

### Project Structure
```text
gastos-recurrentes/
├── app/
│   ├── agent.py               # Main Workflow Graph definition (ADK 2.0)
│   ├── security.py            # Pure-LLM security auditor & ADC bypass logic
│   ├── sheets_utils.py        # Google Sheets read/write operations
│   ├── main.py                # Backoffice Server (Port 8080) & Webhook Receiver
│   ├── billing_server.py      # Provider Invoice Portal Simulator (Port 8181)
│   ├── schemas.py             # Pydantic schemas (State, Inputs)
│   ├── templates/
│   │   ├── index.html         # Backoffice / Audit UI (Port 8080)
│   │   └── billing_index.html # Provider billing simulator UI (Port 8181)
│   ├── agent.md               # Homologous documentation for agent.py
│   ├── security.md            # Homologous documentation for security.py
│   └── sheets_utils.md        # Homologous documentation for sheets_utils.py
```

---

### Running the Project

#### 1. Setup Environment
Ensure your Google Cloud User credentials are logged in for Gemini model access:
```bash
gcloud auth application-default login
```
Set up `.env` with your API Key and Sheet spreadsheet parameters:
```env
GEMINI_API_KEY="AIzaSy..."
SPREADSHEET_ID="1..."
```

#### 2. Install Dependencies
```bash
uv pip install -r pyproject.toml
# or
agents-cli install
```

#### 3. Run Servers
Run the **Backoffice Server** (Port `8080`):
```bash
python app/main.py
```
Run the **Provider Billing Simulator** (Port `8181`):
```bash
python app/billing_server.py
```

---

## 🇪🇸 ESPAÑOL

### Descripción General
`GastosRecurrentes` es un sistema inteligente y de alto rendimiento diseñado para automatizar el ciclo de validación, cotejo y aprobación de facturas de servicios recurrentes (internet, hosting, licenciamiento, etc.). Elimina la carga manual mediante validaciones deterministas y evaluaciones cognitivas, canalizando excepciones hacia flujos asíncronos de **Intervención Humana (Human-in-the-Loop - HITL)**.

---

### Arquitectura Central y Capacidades
1. **Cotejo Determinista (Sin LLM)**: Compara el `id_contrato` y el `valor` facturado con los contratos registrados en Google Sheets usando el `NIT` del proveedor como doble verificación.
   - **Vencido por más de 30 días**: Autorechazo inmediato.
   - **Vencido por menos de 30 días (Margen de gracia)**: Congela la validación y dispara de forma automática el flujo de control y renovación de vencimientos.
   - **Vigente y Activo**: Si la desviación respecto al monto de referencia es $\le 5\%$, la factura se aprueba automáticamente.
2. **Filtro de Seguridad Cognitivo (LLM Puro)**: Evaluado por `gemini-2.5-flash` con `temperature=0.0`. Realiza una auditoría semántica integral sobre todo el payload de entrada para bloquear intentos de **Prompt Injection**, elisión de reglas o comandos imperativos en cualquier idioma (Español, Inglés, Portugués, Alemán, etc.) sin depender de expresiones regulares.
3. **Bypass Dinámico de Credenciales (Sheets + ADC)**: Alterna de forma transparente la cuenta de servicio de Sheets y las **Application Default Credentials (ADC)** de Google Cloud para el SDK de Gemini, evitando bloqueos de permisos de Vertex AI sin romper la persistencia de Sheets.
4. **Intervención Humana Asíncrona (HITL)**: Elegante dashboard web para interactuar con ejecuciones pendientes, aprobar desvíos de presupuesto, e inactivar o renovar contratos.

---

### Estructura de Archivos
```text
gastos-recurrentes/
├── app/
│   ├── agent.py               # Definición del Grafo de Workflow (ADK 2.0)
│   ├── security.py            # Auditor cognitivo de seguridad y bypass de ADC
│   ├── sheets_utils.py        # Conector oficial de lectura/escritura con Google Sheets
│   ├── main.py                # Servidor de Backoffice (Puerto 8080) y Webhook
│   ├── billing_server.py      # Simulador de Facturación de Proveedores (Puerto 8181)
│   ├── schemas.py             # Modelos de datos de Pydantic (Estado, Inputs)
│   ├── templates/
│   │   ├── index.html         # Panel de Control y Auditoría HITL (Puerto 8080)
│   │   └── billing_index.html # Portal del Emisor de Facturas (Puerto 8181)
│   ├── agent.md               # Documentación homóloga de agent.py
│   ├── security.md            # Documentación homóloga de security.py
│   └── sheets_utils.md        # Documentación homóloga de sheets_utils.py
```

---

### Cómo Ejecutar el Proyecto

#### 1. Configuración de Entorno
Inicia sesión en tus credenciales de usuario de Google Cloud para el acceso a Gemini:
```bash
gcloud auth application-default login
```
Configura las variables de entorno en tu archivo `.env`:
```env
GEMINI_API_KEY="AIzaSy..."
SPREADSHEET_ID="1..."
```

#### 2. Instalación de Dependencias
```bash
uv pip install -r pyproject.toml
# o
agents-cli install
```

#### 3. Levantar los Servidores
Inicia el **Servidor de Backoffice** (Puerto `8080`):
```bash
python app/main.py
```
Inicia el **Simulador de Proveedores** (Puerto `8181`):
```bash
python app/billing_server.py
```
