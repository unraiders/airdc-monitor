FROM --platform=$TARGETPLATFORM python:3.11-alpine

WORKDIR /app

# Instalar dependencias del sistema si fueran necesarias
RUN apk add --no-cache tzdata

# Copiar solo los archivos necesarios
COPY requirements.txt .
COPY monitor_uploads.py .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Configurar zona horaria para España
ENV TZ=Europe/Madrid

# Variables de entorno con valores por defecto
ENV DEBUG_MODE=0 \
    AIRDC_IP="" \
    AIRDC_PORT="" \
    AIRDC_USER="" \
    AIRDC_PASSWORD="" \
    TELEGRAM_BOT_TOKEN="" \
    TELEGRAM_CHAT_ID=""

CMD ["python", "monitor_uploads.py"]
