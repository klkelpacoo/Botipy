# cogs/fun/gif.py
import os
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp 
import random 

# --- Cargar las API Keys (v2) ---
try:
    API_KEY = os.getenv("TENOR_API_KEY")
    CLIENT_KEY = os.getenv("TENOR_CLIENT_KEY") # ¡NUEVO!
except Exception:
    API_KEY = None
    CLIENT_KEY = None

# --- Clase del Cog ---
class GIF(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.http_session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.http_session.close()

    @app_commands.command(
        name="gif",
        description="Busca un GIF con mucho estilo en Tenor (v2)."
    )
    @app_commands.describe(busqueda="¿Qué GIF quieres buscar?")
    async def gif(self, interaction: discord.Interaction, busqueda: str):
        """Busca un GIF en Tenor y lo envía."""
        
        # 1. Comprobar si AMBAS llaves están configuradas
        if not API_KEY or not CLIENT_KEY:
            print("Error: TENOR_API_KEY o TENOR_CLIENT_KEY no están configuradas en el .env")
            await interaction.response.send_message("Error: El comando GIF no está configurado. Avisa a un admin.", ephemeral=True)
            return

        await interaction.response.defer()

        # 2. Construir la URL de la API (¡NUEVA URL v2!)
        url = "https://tenor.googleapis.com/v2/search"
        
        # ¡NUEVOS PARÁMETROS!
        params = {
            "key": API_KEY,
            "client_key": CLIENT_KEY,
            "q": busqueda,
            "limit": 10,
            "media_filter": "basic",
            "content_filter": "medium"
        }

        try:
            # 3. Hacer la petición a la API
            async with self.http_session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if not data.get('results'):
                        await interaction.followup.send(f"No se encontraron GIFs para `{busqueda}`. 😥")
                        return
                        
                    # 5. Elegir un GIF al azar
                    gif = random.choice(data['results'])
                    
                    # ¡NUEVA RUTA AL GIF!
                    gif_url = gif['media_formats']['gif']['url']

                    # 6. Crear el Embed con estilo
                    embed = discord.Embed(color=discord.Color.random())
                    embed.set_image(url=gif_url)
                    embed.set_footer(
                        text=f"Resultado para: \"{busqueda}\" | Powered by Tenor",
                        icon_url="https://tenor.com/assets/img/tenor-logo.svg"
                    )
                    
                    await interaction.followup.send(embed=embed)
                    
                else:
                    # El 401 debería desaparecer. Si no, es la llave 100%.
                    await interaction.followup.send(f"Error: La API de Tenor devolvió un error ({response.status}).", ephemeral=True)

        except Exception as e:
            print(f"Error en el comando /gif: {e}")
            await interaction.followup.send("¡Uy! Algo se rompió tratando de buscar un GIF.", ephemeral=True)

# --- Función Setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(GIF(bot))