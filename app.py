import os
import json
from datetime import datetime

import requests
import gspread
from flask import Flask, render_template, request, jsonify
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# Configuración
TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SPREADSHEET_NAME = "Inventario Sugar Dash"


def safe_int(valor, default=0):
    """Convierte un valor a entero de forma segura."""
    try:
        if valor is None:
            return default

        texto = str(valor).strip()
        if texto == "":
            return default

        return int(float(texto))
    except (ValueError, TypeError):
        return default


def conectar_hoja():
    """Establece la conexión con Google Sheets."""
    creds_json = os.environ.get("GOOGLE_CREDS")
    if not creds_json:
        raise ValueError("No se encontró la variable GOOGLE_CREDS en el entorno.")

    try:
        info_claves = json.loads(creds_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"GOOGLE_CREDS no contiene un JSON válido: {e}")

    alcance = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    try:
        creds = Credentials.from_service_account_info(info_claves, scopes=alcance)
        cliente = gspread.authorize(creds)
        return cliente.open(SPREADSHEET_NAME)
    except Exception as e:
        raise RuntimeError(f"No se pudo conectar con Google Sheets: {e}")


@app.route("/")
def index():
    try:
        doc = conectar_hoja()
        hoja = doc.worksheet("Stock")
        datos = hoja.get_all_records()

        productos = []

        for d in datos:
            nombre_producto = str(d.get("Producto", "Sin nombre")).strip()
            precio = safe_int(d.get("Precio", 0))
            cantidad = safe_int(d.get("Cantidad", 0))
            status = str(d.get("Status", "")).strip().upper()
            sabores_raw = d.get("Sabores", "")

            # Si el producto ya trae sabor en el nombre, NO usar la columna Sabores
            sabores = []
            if sabores_raw and "(" not in nombre_producto and ")" not in nombre_producto:
                sabores = [
                    s.strip()
                    for s in str(sabores_raw).split(",")
                    if s and str(s).strip()
                ]

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
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    productos_pedido = datos.get("productos", [])
    nombre_cliente = str(datos.get("nombre_cliente", "")).strip()
    punto_entrega = str(datos.get("punto", "")).strip()
    descripcion_fisica = str(datos.get("descripcion", "Sin descripción")).strip()
    metodo_pago = str(datos.get("metodo_pago", "")).strip()
    total_venta = safe_int(datos.get("total", 0))

    # Validaciones básicas
    if not productos_pedido:
        return jsonify({"success": False, "error": "El carrito está vacío."}), 400

    if not nombre_cliente:
        return jsonify({"success": False, "error": "Falta el nombre del cliente."}), 400

    if not punto_entrega:
        return jsonify({"success": False, "error": "Falta el punto de entrega."}), 400

    if not metodo_pago:
        return jsonify({"success": False, "error": "Falta el método de pago."}), 400

    try:
        doc = conectar_hoja()
        hoja_ventas = doc.worksheet("Ventas")
        hoja_stock = doc.worksheet("Stock")

        # Leemos todos los registros del stock una vez
        registros_stock = hoja_stock.get_all_records()

        resumen_productos = ""

        for item in productos_pedido:
            nombre_full = str(item.get("nombre", "")).strip()
            precio_unitario = safe_int(item.get("precio", 0))

            if not nombre_full:
                continue

            # 1. Registrar venta individual
            hoja_ventas.append_row([
                ahora,
                nombre_cliente,
                nombre_full,
                precio_unitario,
                metodo_pago
            ])

            # 2. Descontar del stock
            # Quitamos la parte del sabor si viene entre paréntesis
            nombre_base = nombre_full.split(" (")[0].strip()

            fila_encontrada = None
            for i, fila in enumerate(registros_stock, start=2):  # fila 2 por encabezados
                producto_hoja = str(fila.get("Producto", "")).strip()
                if producto_hoja == nombre_base or producto_hoja == nombre_full:
                    fila_encontrada = i
                    break

            if fila_encontrada:
                try:
                    cantidad_actual = safe_int(hoja_stock.cell(fila_encontrada, 3).value)
                    nueva_cantidad = max(0, cantidad_actual - 1)

                    # Columna 3 = Cantidad
                    hoja_stock.update_cell(fila_encontrada, 3, nueva_cantidad)

                    # Columna 4 = Status
                    if nueva_cantidad <= 0:
                        hoja_stock.update_cell(fila_encontrada, 4, "AGOTADO")
                    else:
                        hoja_stock.update_cell(fila_encontrada, 4, "DISPONIBLE")

                    # También actualizamos la copia local para siguientes productos del mismo pedido
                    registros_stock[fila_encontrada - 2]["Cantidad"] = nueva_cantidad
                    registros_stock[fila_encontrada - 2]["Status"] = "AGOTADO" if nueva_cantidad <= 0 else "DISPONIBLE"

                except Exception as e:
                    print(f"No se pudo actualizar stock de {nombre_base}: {e}")
            else:
                print(f"No se encontró el producto en Stock: {nombre_base}")

            resumen_productos += f"• {nombre_full} (${precio_unitario})\n"

        # 3. Enviar notificación a Telegram
        if not TOKEN or not CHAT_ID:
            raise ValueError("Faltan TOKEN o CHAT_ID en las variables de entorno.")

        mensaje = (
            f"🛍️ *¡NUEVO PEDIDO DE {len(productos_pedido)} PRODUCTOS!*\n\n"
            f"👤 *Cliente:* {nombre_cliente}\n"
            f"📍 *Punto:* {punto_entrega}\n"
            f"👕 *Identidad:* {descripcion_fisica}\n"
            f"💳 *Pago:* {metodo_pago}\n\n"
            f"*DETALLE:*\n{resumen_productos}\n"
            f"💰 *TOTAL A COBRAR:* ${total_venta}"
        )

        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        respuesta = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": mensaje,
                "parse_mode": "Markdown"
            },
            timeout=10
        )

        if respuesta.status_code != 200:
            raise RuntimeError(f"Telegram devolvió error: {respuesta.text}")

        return jsonify({"success": True})

    except Exception as e:
        print(f"Error procesando el pedido: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
