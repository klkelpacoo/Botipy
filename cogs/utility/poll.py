# cogs/utility/poll.py
import os
import discord
from discord.ext import commands
from discord import app_commands

# --- LÓGICA DE CONFIGURACIÓN DEL ROL DE MOD ---
try:
    MOD_ROLE_ID = int(os.getenv("MODERATOR_ROLE_ID"))
except (TypeError, ValueError):
    print("Error: MODERATOR_ROLE_ID no está definido o no es válido en .env (para poll.py)")
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
class Poll(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="poll",
        description="Crea una encuesta/sondeo con reacciones automáticas."
    )
    @app_commands.describe(
        pregunta="La pregunta que quieres hacer.",
        opcion_1="Opción 1 (Requerida)",
        opcion_2="Opción 2 (Requerida)",
        opcion_3="Opción 3",
        opcion_4="Opción 4",
        opcion_5="Opción 5",
        opcion_6="Opción 6",
        opcion_7="Opción 7",
        opcion_8="Opción 8",
        opcion_9="Opción 9",
        opcion_10="Opción 10"
    )
    @is_moderator()
    async def poll(
        self, 
        interaction: discord.Interaction, 
        pregunta: str, 
        opcion_1: str, 
        opcion_2: str,
        opcion_3: str = None, 
        opcion_4: str = None, 
        opcion_5: str = None,
        opcion_6: str = None, 
        opcion_7: str = None, 
        opcion_8: str = None,
        opcion_9: str = None, 
        opcion_10: str = None
    ):
        """Crea un Embed de sondeo y añade reacciones."""

        # 1. Creamos una lista con todas las opciones que SÍ fueron dadas
        opciones_raw = [
            opcion_1, opcion_2, opcion_3, opcion_4, opcion_5,
            opcion_6, opcion_7, opcion_8, opcion_9, opcion_10
        ]
        
        # Filtramos las que son 'None'
        opciones_validas = [opt for opt in opciones_raw if opt is not None]
        
        # 2. Definimos los emojis que usaremos
        #    (Letras Regionales 🇦, 🇧, 🇨...)
        emojis_reaccion = [
            '\U0001F1E6', '\U0001F1E7', '\U0001F1E8', '\U0001F1E9', '\U0001F1EA',
            '\U0001F1EB', '\U0001F1EC', '\U0001F1ED', '\U0001F1EE', '\U0001F1EF'
        ]

        # 3. Construimos el Embed
        embed = discord.Embed(
            title=f"📊 ENCUESTA: {pregunta}",
            description="Reacciona abajo para votar:",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        # 4. Añadimos las opciones al Embed
        #    Usamos zip() para emparejar cada opción con su emoji
        descripcion_opciones = ""
        for i, (emoji, opcion) in enumerate(zip(emojis_reaccion, opciones_validas)):
            descripcion_opciones += f"{emoji} {opcion}\n\n"
        
        embed.add_field(name="Opciones:", value=descripcion_opciones, inline=False)
        embed.set_footer(text=f"Encuesta creada por {interaction.user.display_name}")

        # 5. Enviamos la confirmación efímera al moderador
        await interaction.response.send_message("¡Encuesta creada!", ephemeral=True)

        # 6. Enviamos el mensaje de la encuesta al canal
        #    Usamos interaction.channel.send() para enviar un mensaje nuevo
        #    y guardamos la referencia al mensaje (poll_message)
        try:
            poll_message = await interaction.channel.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send("Error: No tengo permisos para enviar mensajes en este canal.", ephemeral=True)
            return

        # 7. Añadimos las reacciones al mensaje de la encuesta
        try:
            for i in range(len(opciones_validas)):
                await poll_message.add_reaction(emojis_reaccion[i])
        except discord.Forbidden:
            # Si no puede añadir reacciones, se lo decimos al mod (aunque es raro si pudo enviar el mensaje)
            await interaction.followup.send("Pude enviar la encuesta, pero no tengo permisos para 'Añadir Reacciones'.", ephemeral=True)

    # --- Manejador de Errores ---
    @poll.error
    async def on_poll_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("⛔ ¡Acceso Denegado! ⛔ No tienes permisos.", ephemeral=True)
        elif isinstance(error, app_commands.MissingRequiredArgument):
            await interaction.response.send_message("Faltan argumentos. Debes especificar al menos una pregunta y 2 opciones.", ephemeral=True)
        else:
            print(f"Error inesperado en /poll: {error}")
            await interaction.response.send_message("Algo salió mal.", ephemeral=True)

# --- Función Setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Poll(bot))