# cogs/moderacion/ban.py
import os
import discord
from discord.ext import commands
from discord import app_commands

# --- LÓGICA DE CONFIGURACIÓN ---
try:
    MOD_ROLE_ID = int(os.getenv("MODERATOR_ROLE_ID"))
except (TypeError, ValueError):
    print("Error: MODERATOR_ROLE_ID no está definido o no es válido en .env")
    MOD_ROLE_ID = None

# --- ¡NUEVO! Cargar el ID del canal de Logs ---
try:
    LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID"))
except (TypeError, ValueError):
    print("Error: MOD_LOG_CHANNEL_ID no está definido o no es válido en .env")
    LOG_CHANNEL_ID = None

# --- CHECK DE PERMISOS ---
def is_moderator():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not MOD_ROLE_ID:
            return False 
        role = interaction.user.get_role(MOD_ROLE_ID)
        return role is not None
    return app_commands.check(predicate)

# --- Clase del Cog ---
class Ban(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ban", description="Banea permanentemente a un miembro.")
    @app_commands.describe(
        miembro="La persona que quieres banear.",
        dias_mensajes="Días de mensajes a borrar (0-7). 0 por defecto.",
        razon="El motivo del baneo."
    )
    @is_moderator()
    async def ban(
        self, 
        interaction: discord.Interaction, 
        miembro: discord.Member, 
        dias_mensajes: app_commands.Range[int, 0, 7] = 0, 
        razon: str = None
    ):
        
        # --- (Secciones 1 a 3: Comprobaciones, DM y Baneo - Sin cambios) ---
        
        if miembro == interaction.user:
            await interaction.response.send_message("No puedes banearte a ti mismo.", ephemeral=True)
            return
        if miembro == interaction.guild.owner:
            await interaction.response.send_message("No puedes banear al Dueño.", ephemeral=True)
            return
        if miembro.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message(f"No puedo banear a {miembro.mention}. Rol superior.", ephemeral=True)
            return

        if razon is None:
            razon = "Razón no especificada."
        razon_log = f"Baneado por {interaction.user.name}. Razón: {razon}"

        try:
            embed_dm = discord.Embed(title="Has sido baneado 🔨", description=f"Has sido baneado de **{interaction.guild.name}**.\nRazón: {razon}", color=discord.Color.brand_red())
            await miembro.send(embed=embed_dm)
        except Exception:
            print(f"No se pudo enviar DM a {miembro.name}.")

        try:
            await miembro.ban(delete_message_days=dias_mensajes, reason=razon_log)
        except Exception as e:
            await interaction.response.send_message(f"Ocurrió un error inesperado al banear: {e}", ephemeral=True)
            return

        # --- 4. Confirmación al Moderador (Mensaje efímero) ---
        embed_confirm = discord.Embed(
            title="✅ Acción Completada: Baneo",
            description=f"**Miembro:** {miembro.mention} (`{miembro.id}`)\n**Razón:** {razon}",
            color=discord.Color.green()
        )
        embed_confirm.add_field(name="Historial Borrado:", value=f"{dias_mensajes} días de mensajes.")
        embed_confirm.set_footer(text=f"Baneado por {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed_confirm, ephemeral=True)

        # --- ¡NUEVO! 5. Enviar Log al Canal de Moderación ---
        if LOG_CHANNEL_ID:
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                try:
                    await log_channel.send(embed=embed_confirm)
                except discord.Forbidden:
                    print(f"Error: El bot no tiene permisos para hablar en el canal de logs (ID: {LOG_CHANNEL_ID})")
            else:
                print(f"Error: No se encontró el canal de logs (ID: {LOG_CHANNEL_ID})")
        else:
            print("Info: No se ha configurado MOD_LOG_CHANNEL_ID. Saltando envío de log.")

    # --- (Manejador de Errores - Sin cambios) ---
    @ban.error
    async def on_ban_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("⛔ ¡Acceso Denegado! ⛔", ephemeral=True)
        elif isinstance(error, app_commands.BotMissingPermissions):
            await interaction.response.send_message("¡Error! Necesito 'Banear Miembros'.", ephemeral=True)
        elif isinstance(error, app_commands.MissingRequiredArgument):
            await interaction.response.send_message("Debes especificar a quién banear.", ephemeral=True)
        else:
            print(f"Error inesperado en /ban: {error}")
            await interaction.response.send_message("Algo salió mal.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Ban(bot))