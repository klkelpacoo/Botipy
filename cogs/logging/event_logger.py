# cogs/logging/event_logger.py
import os
import discord
from discord.ext import commands
import datetime
import asyncio # ¡NUEVO! Necesario para el retardo

# --- Cargar el ID del canal de Logs ---
try:
    LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID"))
except (TypeError, ValueError):
    LOG_CHANNEL_ID = None

# --- Clase del Cog ---
class EventLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Evento 1: Mensaje Borrado (Sin cambios) ---
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not LOG_CHANNEL_ID or message.author.bot:
            return
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        content = message.content or "No se pudo recuperar el contenido (probablemente una imagen)."
        if len(content) > 1020:
            content = content[:1020] + "..."

        embed = discord.Embed(title="🗑️ Mensaje Borrado", color=discord.Color.red(), timestamp=datetime.datetime.now())
        embed.add_field(name="Autor:", value=message.author.mention, inline=True)
        embed.add_field(name="Canal:", value=message.channel.mention, inline=True)
        embed.add_field(name="Contenido:", value=f"```{content}```", inline=False)
        embed.set_footer(text=f"ID de Usuario: {message.author.id}")
        
        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"Error inesperado en on_message_delete: {e}")

    # --- Evento 2: Mensaje Editado (Sin cambios) ---
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not LOG_CHANNEL_ID or before.author.bot or before.content == after.content:
            return
            
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
            
        content_before = before.content or "Vacío"
        content_after = after.content or "Vacío"

        if len(content_before) > 500: content_before = content_before[:500] + "..."
        if len(content_after) > 500: content_after = content_after[:500] + "..."

        embed = discord.Embed(title="✏️ Mensaje Editado", description=f"[Ir al mensaje]({after.jump_url})", color=discord.Color.blue(), timestamp=datetime.datetime.now())
        embed.add_field(name="Autor:", value=after.author.mention, inline=True)
        embed.add_field(name="Canal:", value=after.channel.mention, inline=True)
        embed.add_field(name="Antes:", value=f"```{content_before}```", inline=False)
        embed.add_field(name="Después:", value=f"```{content_after}```", inline=False)
        embed.set_footer(text=f"ID de Usuario: {after.author.id}")
        
        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"Error inesperado en on_message_edit: {e}")

    # -----------------------------------------------------------------
    # --- ¡NUEVO! Evento 3: Miembro se va/es expulsado/baneado ---
    # -----------------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Se activa cuando un miembro sale del servidor."""
        
        # 1. Ignorar si el canal de log no está configurado o si es un bot
        if not LOG_CHANNEL_ID or member.bot:
            return
            
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
            
        # 2. Esperar 3 segundos.
        #    Esto es CRUCIAL. El Log de Auditoría puede tardar en actualizarse.
        #    Si preguntamos demasiado rápido, no veremos el 'ban' o 'kick'.
        await asyncio.sleep(3) 

        # 3. Preparar el Embed (por defecto, asumimos que "salió")
        embed = discord.Embed(
            title="⬅️ Miembro Salió",
            description=f"{member.mention} (`{member.name}`) ha abandonado el servidor.",
            color=discord.Color.greyple(), # Color gris
            timestamp=datetime.datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID de Usuario: {member.id}")
        
        # 4. Comprobar el Log de Auditoría por un BAN
        try:
            # Buscamos la última entrada de BAN en el log
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                # Si el baneo es de HACE MENOS de 10 segundos Y es para ESTE usuario
                if entry.target == member and (discord.utils.utcnow() - entry.created_at).total_seconds() < 10:
                    embed.title = "🔨 Miembro Baneado"
                    embed.color = discord.Color.brand_red()
                    embed.description = f"{member.mention} (`{member.name}`) fue **baneado**."
                    embed.add_field(name="Baneado por:", value=entry.user.mention)
                    if entry.reason:
                        embed.add_field(name="Razón:", value=entry.reason, inline=False)
                    break # Encontramos el log, paramos de buscar

            # 5. Si no fue un ban, comprobar por un KICK
            #    (Us 'else' en el 'for' significa "si el bucle NO se rompió con break")
            else: 
                async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                    if entry.target == member and (discord.utils.utcnow() - entry.created_at).total_seconds() < 10:
                        embed.title = "👢 Miembro Expulsado"
                        embed.color = discord.Color.orange()
                        embed.description = f"{member.mention} (`{member.name}`) fue **expulsado**."
                        embed.add_field(name="Expulsado por:", value=entry.user.mention)
                        if entry.reason:
                            embed.add_field(name="Razón:", value=entry.reason, inline=False)
                        break
                        
        except discord.Forbidden:
            # ¡El bot no tiene el permiso "Ver el Registro de Auditoría"!
            embed.add_field(name="Error de Log", value="No tengo permisos para ver el Registro de Auditoría.")
        except Exception as e:
            print(f"Error inesperado en on_member_remove: {e}")

        # 6. Enviar el Embed (sea cual sea el resultado)
        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"Error final al enviar log de on_member_remove: {e}")

# --- Función Setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(EventLogger(bot))