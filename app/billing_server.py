import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(
    title="Portal de Facturación - Proveedores",
    description="Portal independiente para que los proveedores emitan sus facturas de consumo recurrentes."
)

@app.get("/", response_class=HTMLResponse)
async def serve_billing_portal():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "billing_index.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        return """
        <html>
            <body style="font-family: sans-serif; text-align: center; padding-top: 100px; background: #0f172a; color: white;">
                <h1>Portal de Facturación del Proveedor (8181)</h1>
                <p>Archivo templates/billing_index.html no encontrado.</p>
            </body>
        </html>
        """

if __name__ == "__main__":
    uvicorn.run("billing_server:app", host="0.0.0.0", port=8181, reload=True)
