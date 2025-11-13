# cogs/moderacion/report.py
import os
import discord
from discord.ext import commands
from discord import app_commands
from discord import ui # ¡Importamos ui para Modals y TextInputs!

# --- Cargar el ID del canal de Logs ---
try:
    LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID"))
except (TypeError, ValueError):
    print("Error: MOD_LOG_CHANNEL_ID no está definido o no es válido en .env (para report.py)")
    LOG_CHANNEL_ID = None

# -----------------------------------------------------------------
# --- Clase 1: El Formulario Emergente (Modal) ---
# -----------------------------------------------------------------
class ReportModal(ui.Modal):
    def __init__(self, reported_member: discord.Member):
        super().__init__(title=f"Reportar a {reported_member.display_name}")
        self.reported_member = reported_member

        # --- Campo 1: Razón (Texto corto) ---
        self.reason_input = ui.TextInput(
            label="Motivo del reporte",
            style=discord.TextStyle.short,
            placeholder="Ej: Spam, acoso, saltarse reglas...",
            required=True,
            max_length=100
        )
        self.add_item(self.reason_input)

        # --- Campo 2: Detalles (Texto largo) ---
        self.details_input = ui.TextInput(
            label="Detalles adicionales",
            style=discord.TextStyle.paragraph,
            placeholder="Proporciona más contexto, enlaces a mensajes, etc.",
            required=False,
            max_length=1000
        )
        self.add_item(self.details_input)

    async def on_submit(self, interaction: discord.Interaction):
        """
        Se ejecuta cuando el usuario pulsa 'Enviar' en el modal.
        """
        # 1. Recuperamos los valores de los inputs
        razon = self.reason_input.value
        detalles = self.details_input.value or "No se dieron detalles."

        # 2. Buscamos el canal de logs
        if not LOG_CHANNEL_ID:
            await interaction.response.send_message("Error: El bot no tiene un canal de logs configurado.", ephemeral=True)
            return
            
        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            await interaction.response.send_message("Error: No se pudo encontrar el canal de logs.", ephemeral=True)
            return

        # 3. Creamos el Embed para los moderadores
        embed = discord.Embed(
            title="Nuevo Reporte de Miembro 🚩",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(
            name=f"Reportado por: {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )
        embed.set_thumbnail(url=self.reported_member.display_avatar.url)
        
        embed.add_field(name="Miembro Reportado:", value=f"{self.reported_member.mention} (`{self.reported_member.id}`)", inline=False)
        embed.add_field(name="Motivo:", value=razon, inline=False)
        embed.add_field(name="Detalles:", value=detalles, inline=False)
        
        # 4. Enviamos el Embed al canal de logs
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print("Error: El bot no puede enviar el reporte al canal de logs.")
            
        # 5. Damos confirmación al usuario que reportó
        await interaction.response.send_message(
            f"✅ ¡Gracias! Tu reporte sobre **{self.reported_member.display_name}** ha sido enviado a los moderadores.",
            ephemeral=True
        )

# -----------------------------------------------------------------
# --- Clase 2: El Cog (El comando que abre el Modal) ---
# -----------------------------------------------------------------
class Report(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="reportar",
        description="Reporta a un miembro a los moderadores de forma privada."
    )
    @app_commands.describe(miembro="El miembro que quieres reportar.")
    async def report(self, interaction: discord.Interaction, miembro: discord.Member):
        """Abre el modal de reporte para el usuario."""
        
        # Comprobación de seguridad: No te puedes reportar a ti mismo
        if miembro == interaction.user:
            await interaction.response.send_message("No puedes reportarte a ti mismo.", ephemeral=True)
            return
            
        # Comprobación de seguridad: No puedes reportar a un bot
        if miembro.bot:
            await interaction.response.send_message("No puedes reportar a un bot.", ephemeral=True)
            return
            
        # --- Aquí está la magia ---
        # 1. Creamos una instancia de nuestro Modal
        #    Le pasamos el miembro reportado para que el modal lo conozca
        modal = ReportModal(reported_member=miembro)
        
        # 2. Enviamos el modal al usuario
        await interaction.response.send_modal(modal)

# --- Función Setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Report(bot))