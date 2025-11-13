# cogs/automod/anti_links.py
import os
import discord
from discord.ext import commands
import re # ¡NUEVO! Importamos la librería de Expresiones Regulares
import datetime

# --- LÓGICA DE CONFIGURACIÓN ---
try:
    MOD_ROLE_ID = int(os.getenv("MODERATOR_ROLE_ID"))
except (TypeError, ValueError):
    print("Error: MODERATOR_ROLE_ID no está definido o no es válido en .env (para anti_links.py)")
    MOD_ROLE_ID = None
try:
    LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID"))
except (TypeError, ValueError):
    print("Error: MOD_LOG_CHANNEL_ID no está definido o no es válido en .env (para anti_links.py)")
    LOG_CHANNEL_ID = None

# --- Compilamos la Regex para eficiencia ---
# Esto busca "discord.gg/" o "discord.com/invite/" seguido de cualquier código
INVITE_REGEX = re.compile(r"(discord\.(gg|com/invite)/[a-zA-Z0-9]+)")

# --- Clase del Cog ---
class AntiLinks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Se activa CADA VEZ que se envía un mensaje."""
        
        # 1. Ignorar DMs (solo queremos mensajes en el servidor)
        if not message.guild:
            return
            
        # 2. Ignorar al propio bot y a otros bots
        if message.author.bot:
            return
            
        # 3. Ignorar si los logs no están configurados (necesarios para esta función)
        if not LOG_CHANNEL_ID or not MOD_ROLE_ID:
            return

        # 4. Comprobar si el autor es Moderador (ellos tienen permiso)
        try:
            # Obtenemos el objeto 'Member' del autor
            author_member = message.guild.get_member(message.author.id)
            if author_member:
                # Comprobamos si tiene el rol de moderador
                if author_member.get_role(MOD_ROLE_ID):
                    return # Es un mod, no hacemos nada
        except Exception as e:
            print(f"Error comprobando roles en anti-links: {e}")
            return # Fallo seguro, no hacer nada

        # 5. La comprobación clave: Buscar la invitación
        if INVITE_REGEX.search(message.content):
            # ¡Invitación encontrada!
            
            # --- Acción 1: Borrar el mensaje ---
            try:
                await message.delete()
            except discord.Forbidden:
                print("Error: Anti-Links no pudo borrar el mensaje (¡necesito 'Gestionar Mensajes'!).")
                return # Si no podemos borrar, no continuamos
            except Exception as e:
                print(f"Error inesperado al borrar mensaje en anti-links: {e}")
                
            # --- Acción 2: Enviar DM al infractor ---
            try:
                embed_dm = discord.Embed(
                    title="⛔ Enlace No Permitido",
                    description=f"¡Hola! Tu mensaje en **{message.guild.name}** fue borrado porque contenía un enlace de invitación de Discord, lo cual no está permitido.",
                    color=discord.Color.red()
                )
                embed_dm.add_field(name="Contenido de tu mensaje:", value=f"```{message.content[:500]}...```")
                await message.author.send(embed=embed_dm)
            except discord.Forbidden:
                print(f"No se pudo enviar DM a {message.author.name} (DMs cerrados).")
            
            # --- Acción 3: Enviar Log a Moderadores ---
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                embed_log = discord.Embed(
                    title="🛡️ Auto-Mod: Invitación Borrada",
                    color=discord.Color.orange(),
                    timestamp=datetime.datetime.now()
                )
                embed_log.add_field(name="Autor:", value=message.author.mention, inline=True)
                embed_log.add_field(name="Canal:", value=message.channel.mention, inline=True)
                embed_log.add_field(name="Contenido:", value=f"```{message.content}```", inline=False)
                
                try:
                    await log_channel.send(embed=embed_log)
                except Exception as e:
                    print(f"Error al enviar log de anti-links: {e}")

# --- Función Setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(AntiLinks(bot))