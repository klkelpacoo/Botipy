# cogs/welcome.py
import os # Importamos 'os' para leer las variables de entorno
import discord
from discord.ext import commands

# Ya NO definimos el ID aquí. Lo leemos del .env

class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Se activa automáticamente cuando un nuevo miembro entra al servidor.
        Lee la configuración del canal desde el archivo .env
        """
        
        # --- Lógica de Configuración Segura ---
        try:
            # Leemos el ID desde las variables de entorno
            # os.getenv() devuelve un STRING, hay que convertirlo a INT
            channel_id_str = os.getenv("WELCOME_CHANNEL_ID")
            
            if not channel_id_str:
                print("Error: WELCOME_CHANNEL_ID no está definida en el .env")
                return

            channel_id = int(channel_id_str)
            channel = self.bot.get_channel(channel_id)
            
            if not channel:
                print(f"Error: No se encontró el canal (ID: {channel_id}). ¿Está el bot en él?")
                return

        except ValueError:
            print("Error: WELCOME_CHANNEL_ID en el .env no es un número (ID) válido.")
            return
        except Exception as e:
            print(f"Error inesperado al buscar el canal: {e}")
            return

        # --- Creación del Embed Estilizado (sin cambios) ---
        embed = discord.Embed(
            title=f"¡Bienvenido, {member.display_name}! 🥳",
            description=(
                f"¡{member.mention} se ha unido a la tripulación! \n"
                "Esperamos que hayas traído snacks. 🍿"
            ),
            color=discord.Color.green() 
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name="Consejo de la casa:",
            value="No hagas enfadar al bot (o sea, a mí).",
            inline=False
        )
        embed.set_footer(
            text=f"Ahora somos {member.guild.member_count} miembros en el servidor."
        )

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Error: El bot no tiene permisos para hablar en el canal {channel_id}.")
        except Exception as e:
            print(f"Error inesperado en on_member_join: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))