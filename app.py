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
    
    # Permisos necesarios para Sheets y Drive
    alcance = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds = Credentials.from_service_account_info(info_claves, scopes=alcance)
    cliente = gspread.authorize(creds)
    
    # Asegúrate de que tu archivo en Google se llame así exactamente
    return cliente.open("Inventario Sugar Dash")

@app.route('/')
def index():
    try:
        doc = conectar_hoja()
        hoja = doc.worksheet("Stock")
        datos = hoja.get_all_records()
        
        # Formatear datos para el catálogo web
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
    
    try:
        doc = conectar_hoja()
        
        # 1. Registrar la venta en la pestaña "Ventas"
        hoja_ventas = doc.worksheet("Ventas")
        hoja_ventas.append_row([
            ahora, 
            datos.get('nombre_cliente'), 
            datos.get('dulce'), 
            datos.get('precio'), 
            datos.get('metodo_pago')
        ])

        # 2. Restar 1 unidad del Stock
        hoja_stock = doc.worksheet("Stock")
        # Buscamos el producto por su nombre (quitando el sabor si viene en paréntesis)
        nombre_base = datos.get('dulce').split(' (')[0]
        celda = hoja_stock.find(nombre_base)
        
        if celda:
            cantidad_actual = int(hoja_stock.cell(celda.row, 3).value)
            nueva_cantidad = cantidad_actual - 1
            hoja_stock.update_cell(celda.row, 3, nueva_cantidad)
            
            # Si se acaba el producto, marcar como AGOTADO
            if nueva_cantidad <= 0:
                hoja_stock.update_cell(celda.row, 4, "AGOTADO")

        # 3. Notificar por Telegram
        mensaje = (f"🍭 *¡VENTA REGISTRADA!*\n\n"
                   f"👤 *Cliente:* {datos.get('nombre_cliente')}\n"
                   f"📦 *Producto:* {datos.get('dulce')}\n"
                   f"📍 *Punto:* {datos.get('punto', 'No especificado')}\n"
                   f"💳 *Pago:* {datos.get('metodo_pago')}\n"
                   f"💰 *Total:* ${datos.get('precio')}")
        
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})
        
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error en pedido: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    # Render usa la variable de entorno PORT
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
