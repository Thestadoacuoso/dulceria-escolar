import os
from flask import Flask, render_template, request, jsonify
import requests

# ESTA LÍNEA ES LA QUE RENDER ESTÁ BUSCANDO:
app = Flask(__name__)

TOKEN = os.environ.get('TOKEN', '8796430997:AAHXLpWug1AxqQRbLwhWch_cA9Mp45cx-Dg')
CHAT_ID = os.environ.get('CHAT_ID', '1347278058')

inventario = [
    {"nombre": "Cacahuetes", "precio": 9, "disponible": True},
    {"nombre": "Cheetos de queso (Sol)", "precio": 15, "disponible": True},
    {"nombre": "Paleta de sandía", "precio": 3, "disponible": True},
    {"nombre": "Pelón mini", "precio": 5, "disponible": True},
    {"nombre": "Mini Mamut", "precio": 4, "disponible": True},
    # Productos con opciones:
    {"nombre": "Boing 1/4", "precio": 13, "disponible": True, 
     "sabores": ["Mango", "Guayaba", "Uva", "Manzana"]},
    {"nombre": "PAPAS", "precio": 15, "disponible": True, 
     "sabores": ["Doritos Nacho", "Sabritas Sal", "Churrumais", "Cheetos Naranja", "Cheetos Flaming", "Chips Sal", "Chips Moradas", "Chips Jalapeño", "Takis Fuego", "Ruffles Queso", "Runners"]},
    {"nombre": "Galletas (4 pzs)", "precio": 9, "disponible": True, 
     "sabores": ["Emperador Choc", "Emperador Vain", "Chokis", "Arcoiris"]},
    {"nombre": "Halls", "precio": 10, "disponible": True, 
     "sabores": ["Menta", "Yerbabuena", "Cereza", "Boost", "Amarilla"]}
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

