# cogs/greetings.py
import discord
from discord.ext import commands
from discord import app_commands # Para Slash Commands

# Todos los Cogs deben heredar de commands.Cog
class Greetings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Definimos un Comando Slash (/)
    # Es más moderno que los comandos de prefijo (!)
    @app_commands.command(
        name="hola",
        description="¡Un saludo con mucho estilo del bot!"
    )
    async def hello_slash(self, interaction: discord.Interaction):
        """Responde a /hola con un Embed profesional y cómico."""
        
        # interaction.response.send_message() es la forma de responder
        # a un comando slash.
        
        # --- Creación del Embed Estilizado ---
        
        # Creamos el Embed. El color "blurple" es el clásico de Discord.
        embed = discord.Embed(
            title=f"¡Hola, {interaction.user.display_name}! ✨",
            description=(
                "Has invocado mi presencia. \n"
                "Actualmente estoy operando con un 110% de estilo."
            ),
            color=discord.Color.blurple()
        )
        
        # Añadimos campos (opcional, pero da estructura)
        embed.add_field(
            name="Estado Actual:", 
            value="✅ Cafetera: Llena.\n🤖 Código: Compilando.", 
            inline=False
        )
        
        # Añadimos una imagen "thumbnail" (la fotito de la esquina)
        # Usaremos el avatar del bot
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        # Añadimos un pie de página (footer)
        embed.set_footer(
            text=f"Solicitado con elegancia por: {interaction.user.name}",
            icon_url=interaction.user.display_avatar.url # Avatar del usuario
        )
        
        # 'ephemeral=True' hace que el mensaje solo sea visible
        # para quien usó el comando. ¡Quítalo si quieres que todos lo vean!
        await interaction.response.send_message(embed=embed, ephemeral=True)


# Esta función 'setup' es OBLIGATORIA al final de cada archivo Cog
# Permite que el 'bot.py' cargue este módulo.
async def setup(bot: commands.Bot):
    await bot.add_cog(Greetings(bot))