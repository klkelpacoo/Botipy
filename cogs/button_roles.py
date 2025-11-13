# cogs/button_roles.py
import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, button

# --- Lógica de Configuración (Rol Autorol) ---
try:
    ROL_ID = int(os.getenv("ROLE_ID_AUTOROL"))
except (TypeError, ValueError):
    print("Error: ROLE_ID_AUTOROL no está definido o no es válido en .env")
    ROL_ID = None

# --- LÓGICA DE CONFIGURACIÓN DEL ROL DE MOD ---
try:
    MOD_ROLE_ID = int(os.getenv("MODERATOR_ROLE_ID"))
except (TypeError, ValueError):
    print("Error: MODERATOR_ROLE_ID no está definido o no es válido en .env")
    MOD_ROLE_ID = None

# -----------------------------------------------------------------
# --- NUESTRO CHECK DE PERMISOS PERSONALIZADO (BASADO EN ID) ---
# -----------------------------------------------------------------
def is_moderator():
    """
    Función de check personalizada que comprueba si el usuario
    que ejecuta el comando tiene el ROL ID especificado en el .env
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        if not MOD_ROLE_ID:
            print("Check 'is_moderator' falló: MODERATOR_ROLE_ID no configurado en .env")
            return False # Falla si el .env no está configurado
        
        # get_role() busca el rol por ID en la lista de roles del miembro
        role = interaction.user.get_role(MOD_ROLE_ID)
        
        # Devuelve True solo si el usuario tiene el rol
        return role is not None

    return app_commands.check(predicate)

# --- Definición de la Vista (El Contenedor de Botones) ---
class RoleButtonView(View):
    def __init__(self, bot):
        super().__init__(timeout=None) # Vista persistente
        self.bot = bot

    @button(
        label="¡Quiero ese rol!",
        style=discord.ButtonStyle.primary,
        emoji="✨",
        custom_id="persistent_view:role_button" # ID único
    )
    async def role_button_callback(self, interaction: discord.Interaction, button: Button):
        """Callback del botón de rol."""
        
        if not ROL_ID:
            await interaction.response.send_message("El bot no está configurado (ROL_ID). Avisa a un admin.", ephemeral=True)
            return

        role = interaction.guild.get_role(ROL_ID)
        if not role:
            await interaction.response.send_message("El rol a asignar no existe. Avisa a un admin.", ephemeral=True)
            return

        user = interaction.user
        
        try:
            if role in user.roles:
                # Quitar rol
                await user.remove_roles(role)
                await interaction.response.send_message(f"¡Rol {role.name} eliminado! 😢", ephemeral=True)
            else:
                # Añadir rol
                await user.add_roles(role)
                await interaction.response.send_message(f"¡Rol {role.name} añadido! 🥳", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("No tengo permisos para darte ese rol. (Mi rol debe estar por encima)", ephemeral=True)
        except Exception as e:
            print(f"Error en el botón de rol: {e}")
            await interaction.response.send_message("Algo salió mal.", ephemeral=True)

# --- Definición del Cog ---
class ButtonRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Registramos la vista persistente para que funcione tras reinicios
        bot.add_view(RoleButtonView(bot))

    @app_commands.command(
        name="panel_rol",
        description="Publica el panel para auto-asignarse un rol."
    )
    # --- CHECK DE PERMISOS MEJORADO ---
    @is_moderator()
    async def publish_role_panel(self, interaction: discord.Interaction):
        """Envía el Embed con el botón de rol."""
        
        if not ROL_ID or not interaction.guild.get_role(ROL_ID):
            await interaction.response.send_message("El `ROLE_ID_AUTOROL` no está configurado o no existe.", ephemeral=True)
            return

        embed = discord.Embed(
            title="¡Obtén tu Rol de Fan!",
            description="Haz clic en el botón de abajo para conseguir tu rol exclusivo.",
            color=discord.Color.magenta()
        )
        embed.set_footer(text="Puedes hacer clic de nuevo para quitarte el rol.")

        await interaction.channel.send(embed=embed, view=RoleButtonView(self.bot))
        await interaction.response.send_message("¡Panel de rol publicado!", ephemeral=True)
        
    # --- MANEJADOR DE ERRORES MEJORADO ---
    @publish_role_panel.error
    async def on_panel_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Manejador de error para el comando /panel_rol"""
        
        # Comprobamos el error 'CheckFailure'
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("⛔ ¡Acceso Denegado! ⛔\nNo tienes el rol de moderador para usar esto.", ephemeral=True)
        else:
            print(f"Error inesperado en /panel_rol: {error}")
            await interaction.response.send_message("Algo falló al crear el panel.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ButtonRoles(bot))