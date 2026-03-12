import os
from flask import Flask, render_template, request, jsonify
import requests

# Inicialización de la App
app = Flask(__name__)

# Credenciales de Telegram (Obtenidas de Render o valores por defecto)
TOKEN = os.environ.get('TOKEN', '8796430997:AAHXLpWug1AxqQRbLwhWch_cA9Mp45cx-Dg')
CHAT_ID = os.environ.get('CHAT_ID', '1347278058')

# Inventario actualizado para Biomédica
inventario = [
    {"nombre": "Cacahuetes", "precio": 9, "disponible": True},
    {"nombre": "Cheetos de queso (Sol)", "precio": 15, "disponible": True},
    {"nombre": "Paleta de sandía", "precio": 3, "disponible": True},
    {"nombre": "Pelón mini", "precio": 5, "disponible": True},
    {"nombre": "Mini Mamut", "precio": 4, "disponible": True},
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
    """Ruta principal que muestra la tienda"""
    return render_template('index.html', productos=inventario)

@app.route('/enviar_pedido', methods=['POST'])
def enviar_pedido():
    """Ruta que recibe el JSON del pedido y lo manda a Telegram"""
    datos = request.json
    
    # IMPORTANTE: Usamos .get() para que si falta un dato, la app NO se caiga
    nombre = datos.get('nombre_cliente', 'Invitado')
    dulce = datos.get('dulce', 'Producto')
    punto = datos.get('punto', 'No especificado')
    metodo = datos.get('metodo_pago', 'Efectivo 💵')
    precio = datos.get('precio', 0)

    # Construcción del mensaje para tu celular
    mensaje = (f"🍭 *¡NUEVO PEDIDO!*\n\n"
               f"👤 *Cliente:* {nombre}\n"
               f"📦 *Producto:* {dulce}\n"
               f"📍 *Punto:* {punto}\n"
               f"💳 *Pago:* {metodo}\n"
               f"💰 *Total:* ${precio}")

    # Enviar a Telegram
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": mensaje, 
        "parse_mode": "Markdown"
    }
    
    try:
        # Enviamos la petición y verificamos si funcionó
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            return jsonify({"success": True}), 200
        else:
            return jsonify({"success": False, "error": "Telegram no respondió"}), 500
    except Exception as e:
        print(f"Error crítico: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    # Render asigna un puerto automáticamente
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
