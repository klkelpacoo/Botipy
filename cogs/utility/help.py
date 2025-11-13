# cogs/utility/help.py
import os
import discord
from discord.ext import commands
from discord import app_commands

# --- ¡NUEVO! Lista de Comandos de Moderador ---
# Para que el /help sepa qué comandos son "restringidos"
# Tenemos que mantener esta lista manualmente
MOD_COMMANDS = [
    "userinfo", "panel_rol", "additem", "delitem",
    "kick", "ban", "limpiar", "timeout",
    "warn", "warnings", "delwarn", "poll",
    "reportar" # Reportar es de usuario, pero el /report SÍ era de mod
]
# ¡Error en la lógica de arriba! reportar ES de usuario.
# Lo quito.
MOD_COMMANDS = [
    "userinfo", "panel_rol", "additem", "delitem",
    "kick", "ban", "limpiar", "timeout",
    "warn", "warnings", "delwarn", "poll"
    # El menú contextual 'Mostrar UserInfo' también es de mod,
    # pero no es un comando /
]


# --- Clase del Cog ---
class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="Muestra la lista de comandos o la ayuda de uno específico."
    )
    @app_commands.describe(
        comando="El comando específico del que quieres detalles (ej: warn)."
    )
    async def help(self, interaction: discord.Interaction, comando: str = None):
        
        # Hacemos la respuesta efímera para no molestar en el chat
        await interaction.response.defer(ephemeral=True)
        
        # --- CASO 1: /help (General) ---
        if comando is None:
            embed = discord.Embed(
                title=f"Manual de Ayuda de {self.bot.user.name} 🤖",
                description=(
                    "¡Hola! Soy un bot lleno de estilo, listo para ayudarte.\n"
                    "Aquí tienes un resumen de mis habilidades.\n"
                    "Usa `/help [comando]` para más detalles (ej: `/help apostar`)."
                ),
                color=discord.Color.blurple() # Color de Discord
            )
            
            # Categorías (las definimos manualmente para máximo estilo)
            embed.add_field(
                name="🛡️ Moderación (Para Moderadores)",
                value="`/kick`, `/ban`, `/timeout`, `/limpiar`, `/warn`, `/warnings`, `/delwarn`, `/userinfo`, `/poll`, `/panel_rol`",
                inline=False
            )
            embed.add_field(
                name="🪙 Economía (¡Tu Dinero!)",
                value="`/daily`, `/balance`, `/pagar`, `/leaderboard`, `/apostar`",
                inline=False
            )
            embed.add_field(
                name="🏪 Tienda (¡Gasta tus Nocoins!)",
                value="`/tienda`, `/comprar`\n*(Mods: `/additem`, `/delitem`)*",
                inline=False
            )
            embed.add_field(
                name="🚀 Social & Utilidad (Para Todos)",
                value="`/rank`, `/reportar`, `/hola`",
                inline=False
            )
            embed.add_field(
                name="😂 Diversión (Para Todos)",
                value="`/meme`, `/gif`",
                inline=False
            )
            embed.add_field(
                name="🔒 Auto-Mod (Siempre Activo)",
                value="Estoy vigilando 24/7 los enlaces de invitación, mensajes borrados y mensajes editados, reportándolos en los logs.",
                inline=False
            )
            
            embed.set_footer(text="Gracias por usarme. ¡Eres genial!")
            
            await interaction.followup.send(embed=embed, ephemeral=True)

        # --- CASO 2: /help [comando] (Específico) ---
        else:
            comando_nombre = comando.lower().strip("/") # Limpiamos por si ponen "/warn"
            
            # Buscamos el comando en el "árbol" del bot
            cmd_obj = self.bot.tree.get_command(comando_nombre)
            
            if cmd_obj is None:
                await interaction.followup.send(
                    f"No pude encontrar el comando `{comando_nombre}`. ¿Estás seguro de que existe?",
                    ephemeral=True
                )
                return

            # --- Si encontramos el comando, creamos la ficha ---
            embed = discord.Embed(
                title=f"Ayuda: `/{cmd_obj.name}`",
                description=cmd_obj.description or "Este comando no tiene descripción.",
                color=discord.Color.green()
            )
            
            # 1. Construir el "Uso"
            uso_str = f"/{cmd_obj.name}"
            for param in cmd_obj.parameters:
                # [nombre_parametro] (si es opcional)
                if not param.required:
                    uso_str += f" *[{param.name}]*"
                # <nombre_parametro> (si es requerido)
                else:
                    uso_str += f" **<{param.name}>**"
                    
            embed.add_field(name="Uso:", value=f"`{uso_str}`", inline=False)
            
            # 2. Construir los "Argumentos"
            args_str = ""
            for param in cmd_obj.parameters:
                desc = param.description or "Sin descripción."
                args_str += f"**{param.name}**: {desc}\n"
            
            if args_str:
                embed.add_field(name="Argumentos:", value=args_str, inline=False)
            
            # 3. Comprobar Permisos (usando nuestra lista manual)
            if cmd_obj.name in MOD_COMMANDS:
                permiso_str = "🛡️ **Moderador**"
            else:
                permiso_str = "✅ **Todos los miembros**"
            
            embed.add_field(name="Permiso Requerido:", value=permiso_str, inline=False)
                
            await interaction.followup.send(embed=embed, ephemeral=True)


# --- Función Setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))