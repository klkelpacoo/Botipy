# cogs/moderacion/limpiar.py
import os
import discord
from discord.ext import commands
from discord import app_commands

# --- LÓGICA DE CONFIGURACIÓN DEL ROL DE MOD ---
try:
    MOD_ROLE_ID = int(os.getenv("MODERATOR_ROLE_ID"))
except (TypeError, ValueError):
    print("Error: MODERATOR_ROLE_ID no está definido o no es válido en .env (para limpiar.py)")
    MOD_ROLE_ID = None

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
class Limpiar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="limpiar",
        description="Borra una cantidad específica de mensajes en el canal actual."
    )
    @app_commands.describe(
        cantidad="El número de mensajes a borrar (entre 1 y 100)."
    )
    # --- ¡IMPORTANTE! Comprobamos los permisos del MODERADOR ---
    @is_moderator()
    # --- ¡IMPORTANTE! Comprobamos que el BOT tenga permisos ---
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    async def limpiar(self, interaction: discord.Interaction, cantidad: app_commands.Range[int, 1, 100]):
        """Borra los últimos 'cantidad' mensajes del canal."""

        # 1. Aplazamos la respuesta, porque 'purge' puede tardar un segundo
        #    Hacemos 'ephemeral=True' para que el "Pensando..." solo lo vea el mod.
        await interaction.response.defer(ephemeral=True)
        
        # 2. Obtenemos el canal actual
        channel = interaction.channel

        # 3. Hacemos el borrado
        try:
            # .purge() es la función mágica de discord.py
            # limit=cantidad+1 para incluir el propio comando (aunque en slash no suele ser necesario, es más seguro)
            # Pero como la respuesta es efímera, solo 'cantidad' es correcto.
            deleted_messages = await channel.purge(limit=cantidad)
            
            # 4. Enviamos la confirmación
            await interaction.followup.send(
                f"✅ ¡Éxito! Se han borrado **{len(deleted_messages)}** mensajes.",
                ephemeral=True
            )

        except discord.Forbidden:
            # Esto no debería pasar gracias a @app_commands.checks.bot_has_permissions
            await interaction.followup.send("Error: No tengo el permiso 'Gestionar Mensajes' en este canal.", ephemeral=True)
        except Exception as e:
            print(f"Error en /limpiar: {e}")
            await interaction.followup.send("Ocurrió un error inesperado al intentar borrar mensajes.", ephemeral=True)

    # --- Manejador de Errores ---
    @limpiar.error
    async def on_limpiar_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        
        if isinstance(error, app_commands.CheckFailure):
            # Esto captura CUALQUIER fallo de check, incluido @is_moderator
            await interaction.response.send_message("⛔ ¡Acceso Denegado! ⛔\nNo tienes permisos para usar esto.", ephemeral=True)
        elif isinstance(error, app_commands.BotMissingPermissions):
            # Específicamente si falla el check de bot_has_permissions
            await interaction.response.send_message("¡Error! Necesito el permiso de 'Gestionar Mensajes' para hacer esto.", ephemeral=True)
        elif isinstance(error, app_commands.RangeError):
            # Si el usuario pone un número fuera del rango 1-100
            await interaction.response.send_message("La cantidad debe ser un número entre 1 y 100.", ephemeral=True)
        else:
            print(f"Error inesperado en /limpiar: {error}")
            await interaction.response.send_message("Algo salió mal.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Limpiar(bot))