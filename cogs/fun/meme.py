# cogs/fun/meme.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp

# Apuntamos a un subreddit en español
MEME_API_URL = "https://meme-api.com/gimme/memesenespanol" 

class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.http_session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.http_session.close()

    @app_commands.command(
        name="meme",
        description="¡Muestra un meme aleatorio en español!"
    )
    async def meme(self, interaction: discord.Interaction):
        """Envía un meme aleatorio usando una API externa."""

        await interaction.response.defer()

        try:
            async with self.http_session.get(MEME_API_URL) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # --- ¡FILTRO DE CALIDAD CORREGIDO! ---
                    # Comprobamos que la 'url' exista y termine en una extensión de imagen
                    meme_url = data.get('url')
                    if not meme_url or not meme_url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                         await interaction.followup.send(
                            "La API devolvió un post que no era una imagen. ¡Inténtalo de nuevo!", 
                            ephemeral=True
                         )
                         return

                    embed = discord.Embed(
                        title=data['title'], 
                        url=data['postLink'], 
                        color=discord.Color.random() 
                    )
                    embed.set_image(url=meme_url) # Usamos la variable que ya comprobamos
                    embed.set_footer(
                        text=f"Subido en r/{data['subreddit']} por {data['author']}"
                    )
                    
                    await interaction.followup.send(embed=embed)
                    
                else:
                    await interaction.followup.send(
                        f"Error: La API de memes devolvió un error ({response.status}). 😢",
                        ephemeral=True
                    )
                    
        except Exception as e:
            print(f"Error en el comando /meme: {e}")
            await interaction.followup.send(
                "¡Uy! Algo se rompió tratando de buscar un meme.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))