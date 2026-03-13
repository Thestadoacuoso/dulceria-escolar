import os
import json
from flask import Flask, render_template, request, jsonify
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

app = Flask(__name__)

# Configuración de Credenciales de Google y Telegram
TOKEN = os.environ.get('TOKEN', '8796430997:AAHXLpWug1AxqQRbLwhWch_cA9Mp45cx-Dg')
CHAT_ID = os.environ.get('CHAT_ID', '1347278058')

def conectar_hoja():
    """Establece la conexión con Google Sheets"""
    creds_json = os.environ.get('GOOGLE_CREDS')
    if not creds_json:
        raise ValueError("No se encontró la variable GOOGLE_CREDS en Render")
    
    info_claves = json.loads(creds_json)
    alcance = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds = Credentials.from_service_account_info(info_claves, scopes=alcance)
    cliente = gspread.authorize(creds)
    return cliente.open("Inventario Sugar Dash")

@app.route('/')
def index():
    try:
        doc = conectar_hoja()
        hoja = doc.worksheet("Stock")
        datos = hoja.get_all_records()
        
        productos = []
        for d in datos:
            productos.append({
                "nombre": d.get('Producto', 'Sin nombre'),
                "precio": d.get('Precio', 0),
                "disponible": str(d.get('Status', '')).upper() == "DISPONIBLE" and int(d.get('Cantidad', 0)) > 0,
                "sabores": d.get('Sabores', '').split(',') if d.get('Sabores') else []
            })
        return render_template('index.html', productos=productos)
    except Exception as e:
        print(f"Error cargando stock: {e}")
        return f"Error al conectar con el inventario: {e}", 500

@app.route('/enviar_pedido', methods=['POST'])
def enviar_pedido():
    datos = request.json
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    carrito = datos.get('productos', []) # Lista de productos seleccionados
    total_compra = datos.get('total', 0)
    cliente = datos.get('nombre_cliente')
    punto = datos.get('punto')
    descripcion = datos.get('descripcion', 'Sin descripción')
    metodo_pago = datos.get('metodo_pago')
    
    try:
        doc = conectar_hoja()
        hoja_ventas = doc.worksheet("Ventas")
        hoja_stock = doc.worksheet("Stock")
        
        lista_telegram = ""
        
        # PROCESAMOS CADA PRODUCTO DEL CARRITO
        for item in carrito:
            nombre_prod = item.get('nombre')
            precio_prod = item.get('precio')
            
            # 1. Registro en la pestaña Ventas
            hoja_ventas.append_row([ahora, cliente, nombre_prod, precio_prod, metodo_pago])
            
            # 2. Descuento de Stock
            nombre_base = nombre_prod.split(' (')[0]
            try:
                celda = hoja_stock.find(nombre_base)
                if celda:
                    cantidad_actual = int(hoja_stock.cell(celda.row, 3).value)
                    nueva_cantidad = max(0, cantidad_actual - 1)
                    hoja_stock.update_cell(celda.row, 3, nueva_cantidad)
                    
                    if nueva_cantidad <= 0:
                        hoja_stock.update_cell(celda.row, 4, "AGOTADO")
            except Exception as e:
                print(f"No se pudo descontar {nombre_prod}: {e}")

            # Añadir a la lista para el mensaje de Telegram
            lista_telegram += f"• {nombre_prod} (${precio_prod})\n"

        # 3. Notificación Consolidada a Telegram
        mensaje = (f"🛍️ *¡NUEVA VENTA MÚLTIPLE!*\n\n"
                   f"👤 *Cliente:* {cliente}\n"
                   f"📍 *Lugar:* {punto}\n"
                   f"👕 *Identificación:* {descripcion}\n"
                   f"💳 *Pago:* {metodo_pago}\n\n"
                   f"*DETALLE DEL PEDIDO:*\n{lista_telegram}\n"
                   f"💰 *TOTAL A COBRAR:* ${total_compra}")
        
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})
        
        return jsonify({"success": True})
    
    except Exception as e:
        print(f"Error procesando el carrito: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
