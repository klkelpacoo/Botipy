# cogs/moderacion/timeout.py
import os
import discord
from discord.ext import commands
from discord import app_commands
import datetime

# --- LÓGICA DE CONFIGURACIÓN ---
try:
    MOD_ROLE_ID = int(os.getenv("MODERATOR_ROLE_ID"))
except (TypeError, ValueError):
    MOD_ROLE_ID = None
try:
    LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID"))
except (TypeError, ValueError):
    LOG_CHANNEL_ID = None

# --- CHECK DE PERMISOS ---
def is_moderator():
    """Comprueba si el usuario tiene el ROL ID de Moderador del .env"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not MOD_ROLE_ID:
            return False 
        role = interaction.user.get_role(MOD_ROLE_ID)
        return role is not None
    return app_commands.check(predicate)

# --- Clase del Cog ---
class Timeout(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="timeout",
        description="Aplica un 'timeout' (silencio) a un miembro."
    )
    @app_commands.describe(
        miembro="La persona que quieres silenciar.",
        razon="El motivo del silencio.",
        minutos="Minutos para silenciar (ej: 30).",
        horas="Horas para silenciar (ej: 1).",
        dias="Días para silenciar (ej: 1)."
    )
    @is_moderator()
    @app_commands.checks.bot_has_permissions(moderate_members=True) # Permiso clave
    async def timeout(
        self, 
        interaction: discord.Interaction, 
        miembro: discord.Member, 
        razon: str,
        minutos: app_commands.Range[int, 0, 59] = 0,
        horas: app_commands.Range[int, 0, 23] = 0,
        dias: app_commands.Range[int, 0, 27] = 0 # Discord permite max 28 días
    ):
        """Silencia a un miembro usando la función de Timeout de Discord."""

        # --- Comprobaciones de Seguridad ---
        if miembro == interaction.user:
            await interaction.response.send_message("No puedes silenciarte a ti mismo.", ephemeral=True)
            return
        if miembro.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message(f"No puedo silenciar a {miembro.mention}. Tienen un rol superior al mío.", ephemeral=True)
            return
        
        # --- Cálculo del Tiempo ---
        # Creamos el objeto 'timedelta' que la API necesita
        delta = datetime.timedelta(days=dias, hours=horas, minutes=minutos)
        
        # Si no se da tiempo, es un error
        if delta.total_seconds() == 0:
            await interaction.response.send_message("Debes especificar una duración (mínimo 1 minuto).", ephemeral=True)
            return
            
        # Límite de Discord (28 días)
        if delta.days > 27:
            await interaction.response.send_message("El 'timeout' no puede ser mayor a 28 días.", ephemeral=True)
            return

        # --- 1. Crear el Embed para el DM ---
        embed_dm = discord.Embed(
            title="Has sido silenciado 🤫",
            description=f"Has recibido un 'timeout' en el servidor **{interaction.guild.name}**.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed_dm.add_field(name="Duración:", value=f"{dias}d {horas}h {minutos}m", inline=False)
        embed_dm.add_field(name="Razón:", value=razon, inline=False)
        
        # --- 2. Intentar enviar el DM ---
        try:
            await miembro.send(embed=embed_dm)
        except discord.Forbidden:
            print(f"No se pudo enviar DM a {miembro.name}. DMs cerrados.")
        
        # --- 3. Aplicar el Timeout ---
        try:
            # Esta es la función mágica:
            await miembro.timeout(delta, reason=f"Por: {interaction.user.name}. Razón: {razon}")
        except discord.Forbidden:
            await interaction.response.send_message("Error: No tengo el permiso 'Moderar Miembros' para hacer esto.", ephemeral=True)
            return
        except Exception as e:
            await interaction.response.send_message(f"Ocurrió un error inesperado: {e}", ephemeral=True)
            return

        # --- 4. Confirmación al Moderador (Efímera) ---
        embed_confirm = discord.Embed(
            title="✅ Acción Completada: Timeout",
            description=f"**Miembro:** {miembro.mention}\n**Duración:** {dias}d {horas}h {minutos}m\n**Razón:** {razon}",
            color=discord.Color.green()
        )
        embed_confirm.set_footer(text=f"Silenciado por {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed_confirm, ephemeral=True)

        # --- 5. Enviar Log al Canal ---
        if LOG_CHANNEL_ID:
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(embed=embed_confirm) # Enviamos el mismo embed al log

    # --- Manejador de Errores ---
    @timeout.error
    async def on_timeout_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("⛔ ¡Acceso Denegado! ⛔ No tienes permisos.", ephemeral=True)
        elif isinstance(error, app_commands.BotMissingPermissions):
            await interaction.response.send_message("¡Error! Necesito el permiso de 'Moderar Miembros'.", ephemeral=True)
        elif isinstance(error, app_commands.MissingRequiredArgument):
            await interaction.response.send_message("Faltan argumentos. Debes especificar un miembro y una razón.", ephemeral=True)
        else:
            print(f"Error inesperado en /timeout: {error}")
            await interaction.response.send_message("Algo salió mal.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Timeout(bot))