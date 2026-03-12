import os
from flask import Flask, render_template, request, jsonify
import requests

# ESTA LÍNEA ES LA QUE RENDER ESTÁ BUSCANDO:
app = Flask(__name__)

TOKEN = os.environ.get('TOKEN', '8796430997:AAHXLpWug1AxqQRbLwhWch_cA9Mp45cx-Dg')
CHAT_ID = os.environ.get('CHAT_ID', '1347278058')

inventario = [
    {"nombre": "Papas con Sal", "precio": 20, "disponible": True},
    {"nombre": "Mazapán Gigante", "precio": 12, "disponible": True},
    {"nombre": "Gomitas Enchilosas", "precio": 15, "disponible": True},
    {"nombre": "Refresco 600ml", "precio": 18, "disponible": False}
]

@app.route('/')
def index():
    return render_template('index.html', productos=inventario)

@app.route('/enviar_pedido', methods=['POST'])
def enviar_pedido():
    datos = request.json
    mensaje = (f"🍭 *¡NUEVO PEDIDO!*\n\n"
               f"👤 *Cliente:* {datos['nombre_cliente']}\n"
               f"📦 *Producto:* {datos['dulce']}\n"
               f"📍 *Punto:* {datos['punto']}\n"
               f"💰 *Total:* ${datos['precio']}")

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    requests.post(url, json=payload)
    return jsonify({"success": True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
