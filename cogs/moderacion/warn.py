# cogs/moderacion/warn.py
import os
import discord
from discord.ext import commands
from discord import app_commands
import datetime
import sqlite3

# --- LÓGICA DE CONFIGURACIÓN Y CHECKS (Sin cambios) ---
try:
    MOD_ROLE_ID = int(os.getenv("MODERATOR_ROLE_ID"))
except (TypeError, ValueError):
    MOD_ROLE_ID = None
try:
    LOG_CHANNEL_ID = int(os.getenv("MOD_LOG_CHANNEL_ID"))
except (TypeError, ValueError):
    LOG_CHANNEL_ID = None

def is_moderator():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not MOD_ROLE_ID:
            return False 
        role = interaction.user.get_role(MOD_ROLE_ID)
        return role is not None
    return app_commands.check(predicate)

# --- Clase del Cog ---
class Warn(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.init_database()

    def init_database(self):
        os.makedirs('data', exist_ok=True)
        db = sqlite3.connect('data/moderation.db')
        cursor = db.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        db.commit()
        db.close()

    # --- Comando /warn (Sin cambios) ---
    @app_commands.command(name="warn", description="Añade una advertencia a un miembro.")
    @app_commands.describe(miembro="La persona que quieres advertir.", razon="El motivo.")
    @is_moderator()
    async def warn(self, interaction: discord.Interaction, miembro: discord.Member, razon: str):
        # (El código de /warn se mantiene igual)
        if miembro == interaction.user or miembro.bot:
            await interaction.response.send_message("No puedes advertirte a ti mismo ni a un bot.", ephemeral=True)
            return
        try:
            db = sqlite3.connect('data/moderation.db')
            cursor = db.cursor()
            cursor.execute("INSERT INTO warnings (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
                           (interaction.guild.id, miembro.id, interaction.user.id, razon))
            db.commit()
            warn_id = cursor.lastrowid
            db.close()
        except Exception as e:
            await interaction.response.send_message(f"Error de DB: {e}", ephemeral=True)
            return
        try:
            embed_dm = discord.Embed(title="Has recibido una advertencia ⚠️", description=f"En **{interaction.guild.name}**.\nRazón: {razon}", color=discord.Color.gold())
            embed_dm.set_footer(text=f"ID de Advertencia: {warn_id}")
            await miembro.send(embed=embed_dm)
        except discord.Forbidden:
            pass
        embed_confirm = discord.Embed(title=f"✅ Advertencia #{warn_id} Registrada", description=f"**Miembro:** {miembro.mention}\n**Razón:** {razon}", color=discord.Color.green())
        embed_confirm.set_footer(text=f"Advertido por {interaction.user.name}")
        await interaction.response.send_message(embed=embed_confirm, ephemeral=True)
        if LOG_CHANNEL_ID:
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(embed=embed_confirm)

    @warn.error
    async def on_warn_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # (El manejador de error de /warn se mantiene igual)
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("⛔ ¡Acceso Denegado! ⛔", ephemeral=True)
        else:
            await interaction.response.send_message("Algo salió mal.", ephemeral=True)

    # --- Comando /warnings (Sin cambios) ---
    @app_commands.command(name="warnings", description="Muestra el historial de advertencias de un miembro.")
    @app_commands.describe(miembro="El miembro cuyo historial quieres ver.")
    @is_moderator()
    async def warnings(self, interaction: discord.Interaction, miembro: discord.Member):
        # (El código de /warnings se mantiene igual)
        await interaction.response.defer(ephemeral=True)
        try:
            db = sqlite3.connect('data/moderation.db')
            db.row_factory = sqlite3.Row
            cursor = db.cursor()
            cursor.execute("SELECT id, moderator_id, reason, timestamp FROM warnings WHERE user_id = ? AND guild_id = ? ORDER BY timestamp DESC",
                           (miembro.id, interaction.guild.id))
            results = cursor.fetchall()
            db.close()
        except Exception as e:
            await interaction.followup.send(f"Error de DB: {e}", ephemeral=True)
            return
        embed = discord.Embed(title=f"Historial de {miembro.display_name}", color=miembro.color)
        embed.set_thumbnail(url=miembro.display_avatar.url)
        if not results:
            embed.description = "¡Este miembro está limpio! No se encontraron advertencias. ✨"
        else:
            embed.description = f"Se encontraron **{len(results)}** advertencia(s):"
            for warning in results:
                mod = await self.bot.fetch_user(warning['moderator_id'])
                mod_name = mod.name if mod else "ID Desconocido"
                warn_time = datetime.datetime.fromisoformat(warning['timestamp'])
                embed.add_field(name=f"⚠️ Advertencia #{warning['id']} - {discord.utils.format_dt(warn_time, 'D')}",
                                value=f"**Razón:** {warning['reason']}\n**Moderador:** {mod_name}",
                                inline=False)
                if len(embed.fields) >= 25:
                    embed.add_field(name="...", value="Se han omitido más advertencias.", inline=False)
                    break
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    @warnings.error
    async def on_warnings_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # (El manejador de error de /warnings se mantiene igual)
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("⛔ ¡Acceso Denegado! ⛔", ephemeral=True)
        else:
            await interaction.response.send_message("Algo salió mal.", ephemeral=True)

    # -----------------------------------------------------------------
    # --- ¡NUEVO! Comando /delwarn ---
    # -----------------------------------------------------------------
    @app_commands.command(
        name="delwarn",
        description="Borra una advertencia específica por su ID."
    )
    @app_commands.describe(
        id_advertencia="El ID de la advertencia que quieres borrar (lo ves con /warnings).",
        razon="El motivo por el que borras la advertencia."
    )
    @is_moderator()
    async def delwarn(self, interaction: discord.Interaction, id_advertencia: int, razon: str):
        """Busca y elimina una advertencia de la base de datos por su ID."""

        await interaction.response.defer(ephemeral=True)

        try:
            db = sqlite3.connect('data/moderation.db')
            db.row_factory = sqlite3.Row # Para poder leer los datos que borramos
            cursor = db.cursor()
            
            # 1. Primero, buscamos el warning para poder informar qué borramos
            cursor.execute(
                "SELECT * FROM warnings WHERE id = ? AND guild_id = ?",
                (id_advertencia, interaction.guild.id)
            )
            warning_data = cursor.fetchone()
            
            if not warning_data:
                await interaction.followup.send(f"No se encontró ninguna advertencia con el ID #{id_advertencia} en este servidor.", ephemeral=True)
                db.close()
                return

            # 2. Si lo encontramos, lo borramos
            cursor.execute("DELETE FROM warnings WHERE id = ?", (id_advertencia,))
            db.commit()
            db.close()
            
        except Exception as e:
            print(f"Error de Base de Datos en /delwarn: {e}")
            await interaction.followup.send("Error al consultar o borrar en la base de datos.", ephemeral=True)
            return

        # --- 3. Confirmación al Moderador (Efímera) ---
        # Obtenemos el usuario que fue advertido
        user_warned = await self.bot.fetch_user(warning_data['user_id'])
        
        embed_confirm = discord.Embed(
            title="🗑️ Advertencia Eliminada",
            description=f"La advertencia #{id_advertencia} ha sido eliminada.",
            color=discord.Color.greyple()
        )
        embed_confirm.add_field(name="Razón de borrado:", value=razon, inline=False)
        embed_confirm.add_field(name="Miembro (original):", value=user_warned.mention if user_warned else "ID: " + str(warning_data['user_id']), inline=False)
        embed_confirm.add_field(name="Razón (original):", value=warning_data['reason'], inline=False)
        embed_confirm.set_footer(text=f"Eliminada por {interaction.user.name}")
        
        await interaction.followup.send(embed=embed_confirm, ephemeral=True)

        # --- 4. Enviar Log al Canal ---
        if LOG_CHANNEL_ID:
            log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(embed=embed_confirm) # Enviamos el mismo embed al log

    @delwarn.error
    async def on_delwarn_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Manejador de errores para /delwarn"""
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("⛔ ¡Acceso Denegado! ⛔", ephemeral=True)
        elif isinstance(error, app_commands.MissingRequiredArgument):
            await interaction.response.send_message("Faltan argumentos. Debes especificar un ID y una razón.", ephemeral=True)
        else:
            print(f"Error inesperado en /delwarn: {error}")
            await interaction.response.send_message("Algo salió mal.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Warn(bot))