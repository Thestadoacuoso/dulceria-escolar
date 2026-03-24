import os
import json
from datetime import datetime
import pytz  # <--- CAMBIO 1: Importamos la librería de zonas horarias
import requests
import gspread
from flask import Flask, render_template, request, jsonify
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# Configuración - CON TU TOKEN Y CHAT_ID DE GRUPO
TOKEN = "8796430997:AAHXLpWug1AxqQRbLwhWch_cA9Mp45cx-Dg"
CHAT_ID = "-1003713663194" 
SPREADSHEET_NAME = "Inventario Sugar Dash"

def safe_int(valor, default=0):
    """Convierte celdas de Excel a números sin que el programa truene."""
    try:
        if valor is None: return default
        texto = str(valor).strip()
        if texto == "": return default
        return int(float(texto))
    except (ValueError, TypeError):
        return default

def conectar_hoja():
    """Conexión segura con Google."""
    creds_json = os.environ.get("GOOGLE_CREDS")
    if not creds_json:
        raise ValueError("No se encontró la variable GOOGLE_CREDS en Render.")
    info_claves = json.loads(creds_json)
    alcance = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(info_claves, scopes=alcance)
    cliente = gspread.authorize(creds)
    return cliente.open(SPREADSHEET_NAME)

@app.route("/")
def index():
    try:
        doc = conectar_hoja()
        hoja = doc.worksheet("Stock") # Asegúrate que tu pestaña se llame Stock
        datos = hoja.get_all_records()
        productos = []

        for d in datos:
            nombre_producto = str(d.get("Producto", "Sin nombre")).strip()
            precio = safe_int(d.get("Precio", 0))
            cantidad = safe_int(d.get("Cantidad", 0))
            status = str(d.get("Status", "")).strip().upper()
            sabores_raw = d.get("Sabores", "")

            sabores = []
            if sabores_raw and "(" not in nombre_producto:
                sabores = [s.strip() for s in str(sabores_raw).split(",") if s.strip()]

            productos.append({
                "nombre": nombre_producto,
                "precio": precio,
                "disponible": status == "DISPONIBLE" and cantidad > 0,
                "sabores": sabores
            })
        return render_template("index.html", productos=productos)
    except Exception as e:
        print(f"Error cargando stock: {e}")
        return f"Error al conectar con el inventario: {e}", 500

@app.route("/enviar_pedido", methods=["POST"])
def enviar_pedido():
    datos = request.get_json(silent=True) or {}
    
    # --- CAMBIO 2: CONFIGURACIÓN DE HORA MÉXICO ---
    mexico_tz = pytz.timezone('America/Mexico_City')
    ahora = datetime.now(mexico_tz).strftime("%Y-%m-%d %H:%M:%S")
    # ----------------------------------------------

    productos_pedido = datos.get("productos", [])
    nombre_cliente = str(datos.get("nombre_cliente", "")).strip()
    punto_entrega = str(datos.get("punto", "")).strip()
    descripcion_fisica = str(datos.get("descripcion", "Sin descripción")).strip()
    metodo_pago = str(datos.get("metodo_pago", "")).strip()
    total_venta = safe_int(datos.get("total", 0))

    if not productos_pedido or not nombre_cliente or not punto_entrega:
        return jsonify({"success": False, "error": "Datos incompletos"}), 400

    try:
        doc = conectar_hoja()
        hoja_ventas = doc.worksheet("Ventas")
        hoja_stock = doc.worksheet("Stock")
        registros_stock = hoja_stock.get_all_records()

        resumen_productos = ""

        for item in productos_pedido:
            nombre_full = str(item.get("nombre", "")).strip()
            precio_unitario = safe_int(item.get("precio", 0))

            # 1. Registrar venta
            hoja_ventas.append_row([ahora, nombre_cliente, nombre_full, precio_unitario, metodo_pago])

            # 2. Descontar stock (Columna 3 según tu Excel actual)
            nombre_base = nombre_full.split(" (")[0].strip()
            fila_encontrada = None
            for i, fila in enumerate(registros_stock, start=2):
                if str(fila.get("Producto", "")).strip() == nombre_base:
                    fila_encontrada = i
                    break

            if fila_encontrada:
                try:
                    cantidad_actual = safe_int(hoja_stock.cell(fila_encontrada, 3).value)
                    nueva_cantidad = max(0, cantidad_actual - 1)
                    
                    # Columna 3 = Cantidad / Columna 4 = Status
                    hoja_stock.update_cell(fila_encontrada, 3, nueva_cantidad)
                    if nueva_cantidad <= 0:
                        hoja_stock.update_cell(fila_encontrada, 4, "AGOTADO")
                except Exception as e:
                    print(f"Error en stock: {e}")

            resumen_productos += f"• {nombre_full} (${precio_unitario})\n"

        # 3. Notificación a Telegram (Al grupo)
        mensaje = (
            f"🛍️ *¡NUEVO PEDIDO DE {len(productos_pedido)} PRODUCTOS!*\n\n"
            f"👤 *Cliente:* {nombre_cliente}\n"
            f"📍 *Punto:* {punto_entrega}\n"
            f"👕 *Identidad:* {descripcion_fisica}\n"
            f"💳 *Pago:* {metodo_pago}\n\n"
            f"*DETALLE:*\n{resumen_productos}\n"
            f"💰 *TOTAL A COBRAR:* ${total_venta}"
        )

        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})

        return jsonify({"success": True})

    except Exception as e:
        print(f"Error procesando el pedido: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
