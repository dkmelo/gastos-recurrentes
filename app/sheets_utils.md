# Utilidades de Almacenamiento Simulado: sheets_utils.py

Este módulo implementa el almacenamiento central del sistema de Gestión de Gastos Recurrentes. En esta fase inicial, simula de forma local e idéntica la estructura de Google Sheets mediante un archivo JSON local (`sheets_mock.json`).

---

## Estructura de Datos Simulada

La base de datos emula un libro de cálculo con dos pestañas clave:

1. **Contratos (Hoja Principal)**:
   - Contiene la información contractual vigente de los proveedores.
   - Campos: `ID Contrato` (Clave Única), `NIT`, `Monto`, `Fecha Inicio`, `Fecha Fin`, `Razon Social`, `Concepto`, `Estado`.
   - **Regla de negocio:** Toda búsqueda de contrato ignorará de manera explícita aquellos registros cuyo `Estado` sea `"Inactivo"`.

2. **Historial de Aprobaciones (Hoja Secundaria)**:
   - Bitácora de auditoría histórica para registrar aprobaciones automáticas, aprobaciones humanas, rechazos automáticos y rechazos de usuario.
   - Campos: `Fecha Evento`, `ID Contrato`, `NIT`, `Valor Factura`, `Fecha Factura`, `Estado Aprobación`, `Metadata`.

---

## Funciones Principales

- `get_contract(id_contrato: str) -> Optional[dict]`:
  - Obtiene un contrato activo por su clave única. Si el contrato existe pero está `"Inactivo"`, retorna `None`.
  
- `get_all_contracts() -> list[dict]`:
  - Retorna el listado completo de contratos para visualización en la interfaz.

- `update_contract_monto(id_contrato: str, nuevo_monto: float) -> bool`:
  - Modifica el monto registrado de un contrato de manera persistente.

- `update_contract_fecha_fin(id_contrato: str, nueva_fecha_fin: str) -> bool`:
  - Amplía la fecha de vencimiento (útil para el flujo de renovación).

- `inactivate_contract(id_contrato: str) -> bool`:
  - Cambia el estado de un contrato a `"Inactivo"`.

- `add_approval_history(id_contrato, nit, valor, fecha_factura, estado_aprobacion, metadata) -> None`:
  - Registra cada decisión (auto_approved, human_approved, rejected) con su respectiva bitácora.

---

## Transición a API Real de Google Sheets

La arquitectura de este módulo permite que en los hitos posteriores se reemplace la lectura/escritura de `sheets_mock.json` por llamadas directas a la API de Google Sheets utilizando la biblioteca oficial `google-api-python-client`, sin que los nodos de procesamiento del grafo sufran alteraciones en sus firmas de función.
