# cogs/utility/help.py
import os
import discord
from discord.ext import commands
from discord import app_commands

# --- ¡ACTUALIZADO! Lista de Comandos Restringidos ---
# Incluye comandos de Moderación, Tickets y Admin de Tienda/Economía
MOD_COMMANDS = [
    "userinfo", 
    "panel_rol", 
    "additem", 
    "delitem",
    "kick", 
    "ban", 
    "limpiar", 
    "timeout",
    "warn", 
    "warnings", 
    "delwarn", 
    "poll",
    "crear_panel_tickets" # ¡NUEVO!
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
        
        # Reconocimiento de la Interacción (CRÍTICO para la nube)
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
                color=discord.Color.blurple()
            )
            
            # --- ¡CATEGORÍAS ACTUALIZADAS! ---
            embed.add_field(
                name="🛡️ Moderación (Para Moderadores)",
                value="`/kick`, `/ban`, `/timeout`, `/limpiar`, `/warn`, `/warnings`, `/delwarn`, `/userinfo`, `/poll`",
                inline=False
            )
            embed.add_field(
                name="🏛️ Soporte y Admin",
                value="`/crear_panel_tickets`, `/panel_rol`\n*(Tickets usa `/additem` para roles)*",
                inline=False
            )
            embed.add_field(
                name="🪙 Economía y Casino",
                value="`/daily`, `/balance`, `/pagar`, `/leaderboard`, `/apostar`, `/tienda`, `/comprar`",
                inline=False
            )
            embed.add_field(
                name="🧠 IA (ChatGPT-like)",
                value="`/ia` (con historial y fotos), `/ia_reset`",
                inline=False
            )
            embed.add_field(
                name="🎶 Música y Diversión",
                value="`/play`, `/queue` (y el panel de botones), `/meme`, `/gif`",
                inline=False
            )
            embed.add_field(
                name="🔒 Auto-Mod & Logs",
                value="Vigilancia 24/7 de enlaces, mensajes borrados/editados, y logs de tickets.",
                inline=False
            )
            
            embed.set_footer(text="Gracias por usarme. ¡Eres genial!")
            
            await interaction.followup.send(embed=embed, ephemeral=True)

        # --- CASO 2: /help [comando] (Específico) ---
        else:
            comando_nombre = comando.lower().strip("/")
            
            cmd_obj = self.bot.tree.get_command(comando_nombre)
            
            if cmd_obj is None:
                await interaction.followup.send(
                    f"No pude encontrar el comando `{comando_nombre}`. ¿Estás seguro de que existe?",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"Ayuda: `/{cmd_obj.name}`",
                description=cmd_obj.description or "Este comando no tiene descripción.",
                color=discord.Color.green()
            )
            
            # 1. Construir el "Uso"
            uso_str = f"/{cmd_obj.name}"
            for param in cmd_obj.parameters:
                if not param.required:
                    uso_str += f" *[{param.name}]*"
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
