# cogs/userinfo.py
import os
import discord
from discord.ext import commands
from discord import app_commands
import datetime

# --- LÓGICA DE CONFIGURACIÓN Y CHECK DE PERMISOS (Sin cambios) ---
try:
    MOD_ROLE_ID = int(os.getenv("MODERATOR_ROLE_ID"))
except (TypeError, ValueError):
    print("Error: MODERATOR_ROLE_ID no está definido o no es válido en .env")
    MOD_ROLE_ID = None

def is_moderator():
    """Comprueba si el usuario tiene el ROL ID de Moderador del .env"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not MOD_ROLE_ID:
            print("Check 'is_moderator' falló: MODERATOR_ROLE_ID no configurado.")
            return False 
        role = interaction.user.get_role(MOD_ROLE_ID)
        return role is not None
    return app_commands.check(predicate)

# -----------------------------------------------------------------
# --- ¡NUEVO! MENÚ CONTEXTUAL (DEFINIDO FUERA DE LA CLASE) ---
# -----------------------------------------------------------------
@app_commands.context_menu(name="Mostrar UserInfo")
@is_moderator() # Aplicamos el check de seguridad
async def userinfo_context_menu(interaction: discord.Interaction, miembro: discord.Member):
    """
    Este comando se activa al hacer clic derecho en un usuario y 
    seleccionar 'Mostrar UserInfo' desde el menú 'Apps'.
    """
    
    # Para mantener el código limpio (DRY), buscamos el Cog "UserInfo"
    # y llamamos a su función helper 'enviar_info_embed'
    # interaction.client es el 'bot'
    cog = interaction.client.get_cog("UserInfo")
    
    if cog:
        # Llamamos a la función que está DENTRO del Cog
        await cog.enviar_info_embed(interaction, miembro)
    else:
        # Fallback por si el Cog no se cargase por algún motivo
        await interaction.response.send_message("Error: El Cog 'UserInfo' no está cargado.", ephemeral=True)

@userinfo_context_menu.error
async def on_userinfo_context_menu_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Manejador de errores para el menú contextual"""
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("⛔ ¡Acceso Denegado! ⛔", ephemeral=True)
    else:
        print(f"Error inesperado en el menú UserInfo: {error}")
        await interaction.response.send_message("Algo salió mal.", ephemeral=True)


# --- Clase del Cog (Contiene el comando /userinfo y la lógica del Embed) ---
class UserInfo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Comando /userinfo (Slash) ---
    @app_commands.command(
        name="userinfo",
        description="Muestra información detallada de un miembro del servidor."
    )
    @is_moderator()
    async def userinfo_slash(self, interaction: discord.Interaction, miembro: discord.Member = None):
        """Muestra un Embed con la información de un usuario."""
        
        if miembro is None:
            miembro = interaction.user
        
        # Llamamos a nuestra función de lógica interna
        await self.enviar_info_embed(interaction, miembro)

    @userinfo_slash.error
    async def on_userinfo_slash_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Manejador de errores para el comando /userinfo"""
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("⛔ ¡Acceso Denegado! ⛔", ephemeral=True)
        else:
            print(f"Error inesperado en /userinfo: {error}")
            await interaction.response.send_message("Algo salió mal.", ephemeral=True)

    # --- Función de Lógica Centralizada (Helper) ---
    async def enviar_info_embed(self, interaction: discord.Interaction, miembro: discord.Member):
        """
        Función interna que construye y envía el Embed de /userinfo.
        Ahora es llamada tanto por el comando slash como por el menú contextual.
        """
        
        embed_color = miembro.top_role.color if miembro.roles else discord.Color.default()
        embed = discord.Embed(
            title=f"Perfil de {miembro.display_name} 🕵️‍♂️",
            color=embed_color,
            timestamp=datetime.datetime.now()
        )
        embed.set_thumbnail(url=miembro.display_avatar.url)
        embed.add_field(name="Nombre Completo:", value=f"`{miembro.name}`", inline=True)
        embed.add_field(name="Mención:", value=miembro.mention, inline=True)
        
        embed.add_field(
            name="Se unió a Discord:", 
            value=f"{discord.utils.format_dt(miembro.created_at, style='F')} ({discord.utils.format_dt(miembro.created_at, style='R')})",
            inline=False
        )
        embed.add_field(
            name="Se unió a este Servidor:", 
            value=f"{discord.utils.format_dt(miembro.joined_at, style='F')} ({discord.utils.format_dt(miembro.joined_at, style='R')})",
            inline=False
        )
        
        roles = [role.mention for role in reversed(miembro.roles) if role.name != "@everyone"]
        rol_str = " ".join(roles) if roles else "No tiene roles."
        embed.add_field(name=f"Roles ({len(roles)}):", value=rol_str, inline=False)
        
        embed.set_footer(text=f"ID del Usuario: {miembro.id}")

        await interaction.response.send_message(embed=embed, ephemeral=True)


# --- FUNCIÓN SETUP ACTUALIZADA ---
async def setup(bot: commands.Bot):
    # 1. Añadimos el Cog (que contiene el /userinfo slash y la lógica del embed)
    await bot.add_cog(UserInfo(bot))
    
    # 2. ¡NUEVO! Registramos el comando de menú contextual (que está fuera de la clase)
    bot.tree.add_command(userinfo_context_menu)