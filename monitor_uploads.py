import requests
import json
import time
from datetime import datetime
import logging
from dotenv import load_dotenv
import os

# Cargar variables de entorno desde .env
load_dotenv()

# Configuración de logging
DEBUG_MODE = int(os.getenv('DEBUG_MODE', '0'))
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Variables de configuración desde .env
AIRDC_IP = os.getenv('AIRDC_IP')
AIRDC_PORT = os.getenv('AIRDC_PORT')
AIRDC_USER = os.getenv('AIRDC_USER')
AIRDC_PASSWORD = os.getenv('AIRDC_PASSWORD')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Verificar que todas las variables necesarias estén definidas
required_vars = [
    'AIRDC_IP', 'AIRDC_PORT', 'AIRDC_USER', 'AIRDC_PASSWORD',
    'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'
]

for var in required_vars:
    if not globals()[var]:
        raise ValueError(f"La variable de entorno {var} no está definida en el archivo .env")

def send_telegram_message(message):
    """Envía un mensaje a través de Telegram"""
    try:
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        if DEBUG_MODE:
            logging.debug(f"Intentando enviar mensaje a Telegram URL: {telegram_url}")
            logging.debug(f"Datos del mensaje: {json.dumps(data, indent=2)}")
        
        response = requests.post(telegram_url, json=data)
        response.raise_for_status()
        
        if DEBUG_MODE:
            logging.debug(f"Respuesta de Telegram: {json.dumps(response.json(), indent=2)}")
        
        logging.info("Mensaje enviado correctamente a Telegram")
        return True
    except Exception as e:
        logging.error(f"Error al enviar mensaje a Telegram: {str(e)}")
        return False

def get_active_uploads():
    """Obtiene las subidas activas de AirDC++"""
    try:
        response = requests.get(
            f"http://{AIRDC_IP}:{AIRDC_PORT}/api/v1/transfers",
            auth=(AIRDC_USER, AIRDC_PASSWORD)
        )
        response.raise_for_status()
        data = response.json()
        if DEBUG_MODE:
            logging.debug(f"Datos recibidos de la API: {json.dumps(data, indent=2)}")
        return data if isinstance(data, list) else []
    except Exception as e:
        logging.error(f"Error al obtener uploads: {str(e)}")
        return []

def format_size(size_bytes):
    """Convierte bytes a formato legible"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0

def main():
    logging.info("Iniciando monitoreo de uploads en AirDC++")
    active_uploads = {}  # Para trackear uploads activos y su estado
    notified_files = set()  # Para trackear nombres de archivos ya notificados
    initial_scan = True  # Flag para la primera ejecución
    last_cleanup = time.time()  # Para limpiar notificaciones antiguas
    CLEANUP_INTERVAL = 3600  # Limpiar notificaciones cada hora

    while True:
        try:
            transfers = get_active_uploads()
            current_transfer_keys = set()
            current_files = set()  # Para trackear archivos activos
            
            if not transfers:
                if DEBUG_MODE:
                    logging.debug("No hay transferencias activas")
                initial_scan = False
                time.sleep(10)
                continue

            for transfer in transfers:
                if DEBUG_MODE:
                    logging.debug(f"Procesando transferencia: {json.dumps(transfer, indent=2)}")
                
                # Es un upload si download es False
                if transfer.get('download', True):  # Si es True o no existe, no es un upload
                    if DEBUG_MODE:
                        logging.debug("No es un upload, ignorando")
                    continue
                    
                transfer_id = transfer.get('id')
                transfer_name = transfer.get('name', '').strip()

                # Ignorar 'file list partial' y transferencias sin nombre/id
                if not transfer_id or not transfer_name or 'file list' in transfer_name.lower():
                    if DEBUG_MODE:
                        logging.debug(f"Ignorando transferencia: {transfer_name}")
                    continue

                # Crear una clave única usando ID y nombre
                transfer_key = f"{transfer_id}_{transfer_name}"
                current_transfer_keys.add(transfer_key)
                current_files.add(transfer_name)
                status = transfer.get('status', {}).get('id')
                
                # Si es el escaneo inicial y la transferencia está en progreso, la consideramos nueva
                if initial_scan:
                    if status == 'finished':
                        if DEBUG_MODE:
                            logging.debug(f"Ignorando transferencia ya completada en el escaneo inicial: {transfer_name}")
                        active_uploads[transfer_key] = status
                        notified_files.add(transfer_name)
                        continue
                    else:
                        logging.info(f"Transferencia en progreso detectada durante el escaneo inicial: {transfer_name}")

                # Es una nueva transferencia si no hemos notificado este archivo antes
                is_new_transfer = transfer_name not in notified_files

                # Actualizar el estado de la transferencia
                active_uploads[transfer_key] = status

                if is_new_transfer:
                    logging.info(f"Nueva subida detectada: {transfer_name}")
                    
                    user_info = transfer.get('user', {})
                    user_nick = user_info.get('nicks', 'Desconocido') if isinstance(user_info, dict) else 'Desconocido'
                    hub_name = user_info.get('hub_names', 'Desconocido') if isinstance(user_info, dict) else 'Desconocido'
                    
                    # Calcular el progreso
                    total_size = transfer.get('size', 0)
                    bytes_transferred = transfer.get('bytes_transferred', 0)
                    progress = (bytes_transferred / total_size * 100) if total_size > 0 else 0
                    speed = transfer.get('speed', 0)
                    speed_str = f"{speed / 1024 / 1024:.2f} MB/s" if speed > 0 else "Desconocido"
                    
                    # Preparar mensaje para Telegram
                    message = (
                        f"🔼 <b>AirDC - Nueva subida detectada</b>\n\n"
                        f"📅 Fecha y hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                        f"📁 Archivo: {transfer_name}\n"
                        f"👤 Usuario: {user_nick}\n"
                        f"🌐 Hub: {hub_name}\n"
                       # f"📊 Tamaño: {format_size(total_size)}\n"
                        f"⚡ Velocidad: {speed_str}\n"
                       # f"📈 Progreso: {progress:.1f}%\n"
                        f"📋 Estado: {transfer.get('status', {}).get('str', 'Desconocido')}"
                    )
                    
                    if DEBUG_MODE:
                        logging.debug(f"Intentando enviar mensaje a Telegram para transferencia {transfer_name}")
                    if send_telegram_message(message):
                        logging.info(f"Mensaje enviado exitosamente para transferencia {transfer_name}")
                        notified_files.add(transfer_name)
                    else:
                        logging.error(f"Fallo al enviar mensaje para transferencia {transfer_name}")

            # Después del primer escaneo, marcar initial_scan como False
            if initial_scan:
                logging.info("Completado escaneo inicial")
                initial_scan = False

            # Limpiar transferencias que ya no están activas
            finished_transfers = set(active_uploads.keys()) - current_transfer_keys
            for transfer_key in finished_transfers:
                if active_uploads[transfer_key] != 'finished':
                    active_uploads[transfer_key] = 'finished'
                    logging.info(f"Transferencia {transfer_key} completada o cancelada")

            # Limpiar notificaciones antiguas cada hora
            current_time = time.time()
            if current_time - last_cleanup > CLEANUP_INTERVAL:
                notified_files = notified_files.intersection(current_files)
                last_cleanup = current_time
                if DEBUG_MODE:
                    logging.debug(f"Limpieza de notificaciones antiguas. Quedan {len(notified_files)} archivos en seguimiento")

            # Limpiar transferencias que ya no existen
            active_uploads = {k: v for k, v in active_uploads.items() if k in current_transfer_keys}
            
            time.sleep(10)  # Esperar 10 segundos antes de la siguiente comprobación
            
        except Exception as e:
            logging.error(f"Error en el bucle principal: {str(e)}")
            if DEBUG_MODE:
                logging.error("Detalles del error:", exc_info=True)
            time.sleep(30)  # Esperar más tiempo en caso de error

if __name__ == "__main__":
    main()
