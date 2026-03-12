import os
import json
from flask import Flask, render_template, request, jsonify
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

app = Flask(__name__)

# Configuración de Credenciales de Google
# En Render, crearás una variable llamada GOOGLE_CREDS con el contenido del JSON
creds_json = os.environ.get('GOOGLE_CREDS')
TOKEN = os.environ.get('TOKEN', '8796430997:AAHXLpWug1AxqQRbLwhWch_cA9Mp45cx-Dg')
CHAT_ID = os.environ.get('CHAT_ID', '1347278058')

    def conectar_hoja():
    creds_json = os.environ.get('GOOGLE_CREDS')
    if not creds_json:
        raise ValueError("No se encontró la variable GOOGLE_CREDS")
    
    info_claves = json.loads(creds_json)
    
    # REVISA QUE ESTO ESTÉ IDÉNTICO:
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
        hoja = conectar_hoja().worksheet("Stock")
        datos = hoja.get_all_records()
        
        # Formatear datos para el HTML
        productos = []
        for d in datos:
            productos.append({
                "nombre": d['Producto'],
                "precio": d['Precio'],
                "disponible": str(d['Status']).upper() == "DISPONIBLE" and d['Cantidad'] > 0,
                "sabores": d.get('Sabores', '').split(',') if d.get('Sabores') else []
            })
        return render_template('index.html', productos=productos)
    except Exception as e:
        print(f"Error cargando stock: {e}")
        return "Error al conectar con el inventario", 500

@app.route('/enviar_pedido', methods=['POST'])
def enviar_pedido():
    datos = request.json
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        doc = conectar_hoja()
        
        # 1. Registrar Venta
        hoja_ventas = doc.worksheet("Ventas")
        hoja_ventas.append_row([
            ahora, 
            datos.get('nombre_cliente'), 
            datos.get('dulce'), 
            datos.get('precio'), 
            datos.get('metodo_pago')
        ])

        # 2. Restar del Stock
        hoja_stock = doc.worksheet("Stock")
        celda = hoja_stock.find(datos.get('dulce').split(' (')[0]) # Busca el nombre base
        cantidad_actual = int(hoja_stock.cell(celda.row, 3).value)
        nueva_cantidad = cantidad_actual - 1
        hoja_stock.update_cell(celda.row, 3, nueva_cantidad)
        
        if nueva_cantidad <= 0:
            hoja_stock.update_cell(celda.row, 4, "AGOTADO")

        # 3. Notificar Telegram
        mensaje = (f"🍭 *¡VENTA REGISTRADA!*\n\n"
                   f"👤 {datos.get('nombre_cliente')}\n"
                   f"📦 {datos.get('dulce')}\n"
                   f"📍 {datos.get('punto')}\n"
                   f"💳 {datos.get('metodo_pago')}\n"
                   f"💰 ${datos.get('precio')}")
        
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})
        
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error en pedido: {e}")
        return jsonify({"success": False}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)


