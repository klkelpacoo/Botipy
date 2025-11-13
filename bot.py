# bot.py
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import pathlib
import threading 
from flask import Flask 

# --- Configuración Inicial ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Configuración de Intents (Permisos)
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True # Necesario para el bot de música

bot = commands.Bot(command_prefix='!', intents=intents)

# -----------------------------------------------------------------
# --- SERVIDOR WEB PARA UPTIMEROBOT ---
# -----------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    """Responde con 200 OK cuando UptimeRobot pida el estado."""
    # Render espera una respuesta 200 OK en el path raíz
    return "Bot is running!", 200

def run_webserver():
    """Función que corre el servidor Flask en un hilo separado."""
    # Usamos el puerto que Render nos da (o el 10000 por defecto)
    app.run(host='0.0.0.0', port=os.getenv('PORT', 10000))
# -----------------------------------------------------------------


# --- Evento 'on_ready' ---
@bot.event
async def on_ready():
    """Confirma la conexión en la consola."""
    print(f'¡Conectado como {bot.user} (ID: {bot.user.id})!')
    print('Bot listo y operativo. ¡A la carga!')

# --- Carga de Cogs (MÓDULO RECURSIVO MEJORADO) ---
@bot.event
async def setup_hook():
    """
    Carga automáticamente todos los Cogs de la carpeta /cogs
    y de todas sus sub-carpetas.
    """
    print("Cargando Cogs...")
    
    cogs_path = pathlib.Path('./cogs')
    
    # Usamos .rglob('*.py') para buscar RECURSIVAMENTE
    for file_path in cogs_path.rglob('*.py'):
        if file_path.name == '__init__.py':
            continue

        # Convertimos la ruta del archivo al formato de módulo de Python
        parts = list(file_path.parts)
        parts[-1] = parts[-1][:-3]
        cog_name = ".".join(parts)
        
        try:
            await bot.load_extension(cog_name)
            print(f'  [+] Cog cargado: {cog_name}')
        except Exception as e:
            print(f'  [!] Error al cargar {cog_name}: {e}')
    
    # Sincronizamos los comandos (/) con Discord
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizados {len(synced)} comandos (/) globalmente.")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")


# --- Ejecución del Bot ---
if __name__ == "__main__":
    if TOKEN:
        # ¡CRUCIAL! Iniciamos el servidor web en un hilo separado
        threading.Thread(target=run_webserver).start()
        
        # Luego, el bot de Discord arranca en el hilo principal (Asyncio)
        bot.run(TOKEN)
    else:
        print("Error: No se encontró el DISCORD_TOKEN en el archivo .env")