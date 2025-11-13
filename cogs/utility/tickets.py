# cogs/utility/tickets.py
import os
import discord
from discord.ext import commands
from discord import app_commands
from discord import ui
import datetime
import chat_exporter
import io

# --- CARGAR LA CONFIGURACIÓN PRO v4 ---
try:
    MOD_ROLE_ID = int(os.getenv("MODERATOR_ROLE_ID"))
    
    # --- ¡NUEVO! Mapa de Configuración Complejo (Trío de IDs) ---
    # Mapea el valor del Dropdown (ej. "Soporte") a un TUPLE de:
    # (ID_Categoría_Crear, ID_Rol_Soporte, ID_Canal_Log)
    TICKET_CONFIG_MAP = {
        "Soporte": (
            int(os.getenv("TICKET_CATEGORY_SOPORTE_ID")),
            int(os.getenv("TICKET_ROLE_SOPORTE_ID")),
            int(os.getenv("TICKET_LOG_SOPORTE_ID"))
        ),
        "Reporte": (
            int(os.getenv("TICKET_CATEGORY_REPORTE_ID")),
            int(os.getenv("TICKET_ROLE_REPORTE_ID")),
            int(os.getenv("TICKET_LOG_REPORTE_ID"))
        ),
        "Bug":     (
            int(os.getenv("TICKET_CATEGORY_BUG_ID")),
            int(os.getenv("TICKET_ROLE_BUG_ID")),
            int(os.getenv("TICKET_LOG_BUG_ID"))
        ),
        "Otro":    (
            int(os.getenv("TICKET_CATEGORY_OTRO_ID")),
            int(os.getenv("TICKET_ROLE_OTRO_ID")),
            int(os.getenv("TICKET_LOG_OTRO_ID"))
        ),
    }
    
    # Comprobar si todas las IDs se cargaron
    if not all(v[0] and v[1] and v[2] for v in TICKET_CONFIG_MAP.values()) or not MOD_ROLE_ID:
        raise TypeError("Una o más IDs de Ticket (Categorías, Roles o Logs) en el .env están vacías.")
        
except Exception as e:
    print(f"Error CRÍTICO al cargar la configuración de Tickets: {e}. Revisa tu .env.")

# --- CHECK DE PERMISOS DE MOD (Sin cambios) ---
def is_moderator():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not MOD_ROLE_ID: return False 
        role = interaction.user.get_role(MOD_ROLE_ID)
        return role is not None
    return app_commands.check(predicate)

# --- CHECK DE PERMISOS DE SOPORTE (Contextual) (Sin cambios) ---
def is_ticket_handler(interaction: discord.Interaction) -> bool:
    if interaction.user.get_role(MOD_ROLE_ID):
        return True
    
    current_category_id = interaction.channel.category_id
    
    allowed_role_id = None
    for category_name, (cat_id, role_id, log_id) in TICKET_CONFIG_MAP.items():
        if cat_id == current_category_id:
            allowed_role_id = role_id
            break
            
    if not allowed_role_id:
        return False 
    
    if interaction.user.get_role(allowed_role_id):
        return True
        
    return False

# -----------------------------------------------------------------
# --- Clase 1a: El Modal (Formulario de Ticket) ---
# -----------------------------------------------------------------
class TicketModal(ui.Modal, title="Crear un nuevo Ticket"):
    def __init__(self, bot, category_choice: str):
        super().__init__()
        self.bot = bot
        self.category_choice = category_choice

    asunto = ui.TextInput(label="Asunto del Ticket", placeholder="Ej: Problema con un usuario...", required=True, max_length=100)
    descripcion = ui.TextInput(label="Describe tu problema", style=discord.TextStyle.paragraph, placeholder="Por favor, da todos los detalles posibles.", required=True, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        """Se ejecuta al enviar el modal. ¡Aquí se crea el ticket!"""
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        guild = interaction.guild
        
        # --- Lógica de Categoría y Rol Dinámica v3 ---
        config = TICKET_CONFIG_MAP.get(self.category_choice)
        if not config:
            await interaction.followup.send("Error de configuración: Categoría no encontrada.", ephemeral=True)
            return
            
        category_id, role_id, log_id = config # ¡Ahora obtenemos 3 valores!
        category = guild.get_channel(category_id)
        support_role = guild.get_role(role_id) 
        
        if not category or not support_role:
            await interaction.followup.send(f"Error de configuración del bot (Categoría o Rol para '{self.category_choice}' no encontrados). Avisa a un admin.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.get_role(MOD_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }

        try:
            channel_name = f"ticket-{self.category_choice.lower()}-{interaction.user.name}"
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Ticket de: {interaction.user.name} (ID: {interaction.user.id}). Categoría: {self.category_choice}"
            )
        except discord.Forbidden:
            await interaction.followup.send("Error: No tengo permisos para crear canales en esa categoría.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Ticket: {self.asunto.value}",
            description=f"**Categoría:** {self.category_choice}\n\n**Problema:**\n{self.descripcion.value}",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name=f"Abierto por: {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
        
        await ticket_channel.send(
            f"¡Hola {interaction.user.mention}! El equipo de {support_role.mention} te atenderá pronto.",
            embed=embed,
            view=TicketControlView(self.bot) # Adjuntamos los botones de control
        )

        await interaction.followup.send(f"✅ ¡Ticket creado! Ve a {ticket_channel.mention} para continuar.", ephemeral=True)

# -----------------------------------------------------------------
# --- Clases 1b y 1c (Modals de Add/Remove) (Sin cambios) ---
# -----------------------------------------------------------------
class AddUserModal(ui.Modal, title="Añadir Usuario al Ticket"):
    user_id = ui.TextInput(label="ID del Usuario a AÑADIR", placeholder="Pega el ID del usuario aquí...", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        # (El código de esta clase no necesita cambios)
        try:
            user_to_add = await interaction.guild.fetch_member(int(self.user_id.value))
        except Exception:
            await interaction.response.send_message("ID de usuario no válido.", ephemeral=True)
            return
        try:
            await interaction.channel.set_permissions(user_to_add, view_channel=True, send_messages=True, read_message_history=True)
        except Exception:
             await interaction.response.send_message("No tengo permisos para gestionar permisos en este canal.", ephemeral=True)
             return
        await interaction.response.send_message(f"✅ {user_to_add.mention} ha sido **añadido** a este ticket.", ephemeral=False)

class RemoveUserModal(ui.Modal, title="Quitar Usuario del Ticket"):
    user_id = ui.TextInput(label="ID del Usuario a QUITAR", placeholder="Pega el ID del usuario aquí...", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        # (El código de esta clase no necesita cambios)
        try:
            user_to_remove = await interaction.guild.fetch_member(int(self.user_id.value))
        except Exception:
            await interaction.response.send_message("ID de usuario no válido.", ephemeral=True)
            return
        try:
            await interaction.channel.set_permissions(user_to_remove, overwrite=None)
        except Exception:
             await interaction.response.send_message("No tengo permisos para gestionar permisos en este canal.", ephemeral=True)
             return
        await interaction.response.send_message(f"✅ {user_to_remove.mention} ha sido **eliminado** de este ticket.", ephemeral=False)

# -----------------------------------------------------------------
# --- Clase 2: El Dropdown (Selección de Categoría) ---
# --- (Sin cambios) ---
# -----------------------------------------------------------------
class CategorySelect(ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="Soporte General", value="Soporte", emoji="ℹ️"),
            discord.SelectOption(label="Reportar un Usuario", value="Reporte", emoji="👤"),
            discord.SelectOption(label="Reportar un Bug", value="Bug", emoji="🐞"),
            discord.SelectOption(label="Otra Consulta", value="Otro", emoji="❓"),
        ]
        super().__init__(placeholder="Selecciona una categoría para tu ticket...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        modal = TicketModal(self.bot, category_choice=self.values[0])
        await interaction.response.send_modal(modal)

# -----------------------------------------------------------------
# --- Clase 3: El Panel de Control (¡LOGS ACTUALIZADOS!) ---
# -----------------------------------------------------------------
class TicketControlView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None) # Persistente
        self.bot = bot

    @ui.button(label="Cerrar Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if not is_ticket_handler(interaction):
            await interaction.response.send_message("No tienes permisos para cerrar este tipo de ticket.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("Cerrando y transcribiendo el ticket...", ephemeral=True)
        
        # --- ¡NUEVO! Lógica de Log Dinámica ---
        log_channel_id = None
        current_category_id = interaction.channel.category_id
        
        # 1. Buscar el canal de log que corresponde a esta categoría
        for category_name, (cat_id, role_id, log_id) in TICKET_CONFIG_MAP.items():
            if cat_id == current_category_id:
                log_channel_id = log_id
                break
        
        log_channel = self.bot.get_channel(log_channel_id) if log_channel_id else None
        
        if not isinstance(log_channel, discord.TextChannel):
            print(f"Error: El canal de log para la categoría (ID: {current_category_id}) no es un canal de texto. ¡Revisa tu .env!")
            await interaction.followup.send("Error de configuración: El canal de logs para esta categoría NO es un canal de texto.", ephemeral=True)
            # NO detenemos. Aún podemos borrar el canal.
        
        # --- Transcripción (sin cambios) ---
        if log_channel: # Solo transcribir si tenemos dónde enviarlo
            try:
                transcript = await chat_exporter.export(interaction.channel, bot=self.bot)
                if transcript is None: raise Exception("La transcripción devolvió None.")

                transcript_file = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{interaction.channel.name}.html")
                
                embed = discord.Embed(title=f"Transcripción de Ticket: {interaction.channel.name}", color=discord.Color.greyple(), timestamp=datetime.datetime.now())
                embed.add_field(name="Cerrado por:", value=interaction.user.mention, inline=True)
                
                topic = interaction.channel.topic
                if topic and "ID:" in topic:
                    try:
                        user_id_str = topic.split("ID:")[1].split(")")[0].strip()
                        user = await self.bot.fetch_user(int(user_id_str))
                        embed.add_field(name="Usuario del Ticket:", value=user.mention, inline=True)
                    except Exception: pass
                
                await log_channel.send(embed=embed, file=transcript_file)
                
            except Exception as e:
                print(f"Error al transcribir: {e}")
                await log_channel.send(f"Error al crear la transcripción para {interaction.channel.name}: {e}")
        
        # --- Borrar el canal (sin cambios) ---
        try:
            await interaction.channel.delete(reason="Ticket cerrado por moderador.")
        except discord.Forbidden:
            pass

    # --- Botones Add/Remove (Check de permisos actualizado) ---
    @ui.button(label="Añadir Usuario", style=discord.ButtonStyle.secondary, emoji="👤", custom_id="ticket_add_user")
    async def add_user(self, interaction: discord.Interaction, button: ui.Button):
        if not is_ticket_handler(interaction):
            await interaction.response.send_message("No tienes permisos para gestionar este tipo de ticket.", ephemeral=True)
            return
        await interaction.response.send_modal(AddUserModal())

    @ui.button(label="Quitar Usuario", style=discord.ButtonStyle.secondary, emoji="⛔", custom_id="ticket_remove_user")
    async def remove_user(self, interaction: discord.Interaction, button: ui.Button):
        if not is_ticket_handler(interaction):
            await interaction.response.send_message("No tienes permisos para gestionar este tipo de ticket.", ephemeral=True)
            return
        await interaction.response.send_modal(RemoveUserModal())

# -----------------------------------------------------------------
# --- Clase 4: La Vista del Panel (Sin cambios) ---
# -----------------------------------------------------------------
class TicketPanelView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None) # Persistente
        self.bot = bot

    @ui.button(label="Abrir un Ticket", style=discord.ButtonStyle.primary, emoji="🎟️", custom_id="create_ticket_button")
    async def create_ticket(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View(timeout=None)
        view.add_item(CategorySelect(self.bot))
        await interaction.response.send_message("Por favor, elige una categoría:", view=view, ephemeral=True)

# -----------------------------------------------------------------
# --- Clase 5: El Cog Principal (Comando Admin) ---
# -----------------------------------------------------------------
class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(TicketPanelView(bot))
        bot.add_view(TicketControlView(bot))

    @app_commands.command(name="crear_panel_tickets", description="[MOD] Publica el panel para crear tickets en este canal.")
    @is_moderator()
    async def create_ticket_panel(self, interaction: discord.Interaction):
        
        # --- ¡NUEVO! Comprobación de Configuración v3 ---
        if not all(v[0] and v[1] and v[2] for v in TICKET_CONFIG_MAP.values()) or not MOD_ROLE_ID:
            await interaction.response.send_message(
                "Error: Faltan IDs de configuración en el .env. Revisa que las 12 IDs de Tickets (Categoría, Rol y Log) estén completas.", 
                ephemeral=True
            )
            return
            
        embed = discord.Embed(
            title="Soporte del Servidor",
            description="¿Necesitas ayuda? ¿Quieres reportar a un usuario o un bug?\n\n¡Haz clic en el botón de abajo para **abrir un ticket** y un miembro del equipo de Soporte te atenderá en privado!",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Tu ticket será 100% privado.")
        
        await interaction.channel.send(embed=embed, view=TicketPanelView(self.bot))
        await interaction.response.send_message("¡Panel de tickets publicado!", ephemeral=True)
        
async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))