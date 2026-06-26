# Filtros de Seguridad y Detección de Prompt Injection: security.py

Este módulo implementa el guardián de seguridad cognitivo del sistema, encargado de validar la entrada mediante IA antes de interactuar con cualquier componente del flujo de trabajo, almacenamiento o decisiones.

---

## Estrategia de Mitigación (Detección Semántica por LLM)

Para neutralizar intentos de bypass o aprobación maliciosa introducida a través de los datos de la factura de forma multilingüe y tolerante a errores ortográficos, el módulo realiza una auditoría completa:

1. **Validación Estricta de Tipos:** Los campos numéricos y de fecha (`valor` y `fecha`) son filtrados estrictamente por la capa de Pydantic (`InvoiceInput`).
2. **Análisis de Intención por LLM (Pure Gemini Filter):** Todos los campos de entrada se serializan en un payload de auditoría JSON holístico y se evalúan mediante `gemini-2.5-flash` con `temperature=0.0`.
3. **Independencia del Idioma:** Al utilizar Gemini, se eliminan todas las expresiones regulares y heurísticas de palabras clave. Se detecta con precisión la intención maliciosa (Prompt Injection, desvío de reglas, verbos imperativos) en cualquier idioma (Español, Inglés, Alemán, Portugués, etc.).

---

## Mecanismo de Autenticación Híbrida (Sheets Service Account + User ADC)

Para evitar bloqueos de permisos en Vertex AI al usar la cuenta de servicio restringida de Google Sheets (`sheets-agent-authdata.json`), el cargador de credenciales realiza una maniobra dinámica:
- Detecta si la variable de entorno `GOOGLE_APPLICATION_CREDENTIALS` apunta al archivo de la cuenta de servicio de Sheets.
- Oculta temporalmente la variable del entorno al inicializar el cliente de Gemini.
- Fuerza al cliente a cargar las Application Default Credentials (ADC) de usuario (`vertexai=True`).
- Restaura de forma inmediata las credenciales para que las operaciones con Google Sheets continúen operando sin interrupción.

---

## Funciones Principales

- `analyze_input_for_injection(**kwargs) -> Tuple[bool, str]`:
  - Recibe el payload completo de la factura.
  - Ejecuta un análisis semántico restrictivo usando `gemini-2.5-flash`.
  - Retorna `(True, "")` si la carga es segura y meramente descriptiva.
  - Retorna `(False, "Descripción detallada del ataque rechazado")` si detecta intenciones de inyección de prompts, secuestro de instrucciones o comandos imperativos.
  - Bloquea por defecto en caso de falla de conexión o inicialización de la API para garantizar la seguridad del sistema.
