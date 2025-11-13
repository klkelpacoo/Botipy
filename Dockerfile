# Dockerfile
# Usamos una imagen base de Python oficial
FROM python:3.12-slim

# 1. Instalar FFmpeg (el software de audio) con permisos de root
RUN apt-get update && apt-get install -y ffmpeg

# 2. Establecer la carpeta de trabajo
WORKDIR /app

# 3. Copiar los archivos de requisitos e instalar las dependencias de Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiar el resto del proyecto (cogs, bot.py, Procfile)
COPY . /app

# 5. Comando de Arranque
CMD ["python", "bot.py"]