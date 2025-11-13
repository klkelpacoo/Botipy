# cogs/community/giveaways.py
import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord import ui
import datetime
import sqlite3
import random
import re # Para leer el tiempo

# --- Cargar Configuración de Mod ---
try:
    MOD_ROLE_ID = int(os.getenv("MODERATOR_ROLE_ID"))
except Exception:
    MOD_ROLE_ID = None

# --- Helper 1: Check de Permisos ---
def is_moderator():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not MOD_ROLE_ID: return False 
        role = interaction.user.get_role(MOD_ROLE_ID)
        return role is not None
    return app_commands.check(predicate)

# --- Helper 2: Parseador de Duración (¡Magia!) ---
def parse_duration(duration_str: str) -> datetime.timedelta:
    """Convierte un string como '1d10h30m' en un timedelta."""
    regex = re.compile(r"(\d+)(d|h|m|s)")
    total_seconds = 0
    matches = regex.findall(duration_str.lower())
    
    if not matches:
        return None # Formato inválido

    for value, unit in matches:
        value = int(value)
        if unit == 'd':
            total_seconds += value * 86400
        elif unit == 'h':
            total_seconds += value * 3600
        elif unit == 'm':
            total_seconds += value * 60
        elif unit == 's':
            total_seconds += value
            
    return datetime.timedelta(seconds=total_seconds)

# -----------------------------------------------------------------
# --- Clase 1: La Vista del Botón (Persistente) ---
# -----------------------------------------------------------------
class GiveawayButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None) # ¡Persistente!

    @ui.button(label="Participar", style=discord.ButtonStyle.success, emoji="🎉", custom_id="giveaway_join_button")
    async def join_giveaway(self, interaction: discord.Interaction, button: ui.Button):
        """Callback: Se ejecuta cuando un usuario pulsa el botón."""
        
        # Conectamos a la BBDD para registrar al participante
        db = sqlite3.connect('data/community.db')
        cursor = db.cursor()
        
        try:
            # Comprobar si el sorteo sigue activo
            cursor.execute("SELECT * FROM giveaways WHERE message_id = ?", (interaction.message.id,))
            giveaway_data = cursor.fetchone()
            
            if not giveaway_data:
                await interaction.response.send_message("Este sorteo ya ha finalizado.", ephemeral=True)
                db.close()
                return

            # ¡Registrar al participante!
            # INSERT OR IGNORE previene que un usuario se registre dos veces
            cursor.execute(
                "INSERT OR IGNORE INTO giveaway_participants (message_id, user_id) VALUES (?, ?)",
                (interaction.message.id, interaction.user.id)
            )
            db.commit()
            
            if cursor.rowcount > 0:
                await interaction.response.send_message("¡Mucha suerte! Has entrado al sorteo. 🤞", ephemeral=True)
            else:
                await interaction.response.send_message("Ya estabas participando en este sorteo.", ephemeral=True)
                
        except Exception as e:
            print(f"Error de BBDD en botón de giveaway: {e}")
            await interaction.response.send_message("Error al registrarte. Inténtalo de nuevo.", ephemeral=True)
        finally:
            db.close()

# -----------------------------------------------------------------
# --- Clase 2: El Cog (Comando y Tarea de Fondo) ---
# -----------------------------------------------------------------
class Giveaways(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.init_database()
        # ¡Iniciamos la tarea en segundo plano!
        self.check_giveaways.start()

    def init_database(self):
        """Crea la BBDD y las tablas si no existen."""
        os.makedirs('data', exist_ok=True)
        db = sqlite3.connect('data/community.db') # Nueva BBDD
        cursor = db.cursor()
        
        # Tabla 1: Los sorteos activos
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS giveaways (
            message_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            end_time DATETIME NOT NULL,
            winner_count INTEGER NOT NULL,
            prize TEXT NOT NULL
        )
        """)
        
        # Tabla 2: Los participantes de cada sorteo
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS giveaway_participants (
            message_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (message_id) REFERENCES giveaways(message_id) ON DELETE CASCADE,
            PRIMARY KEY (message_id, user_id)
        )
        """)
        
        db.commit()
        db.close()

    def cog_unload(self):
        """Se llama si el Cog se recarga (para desarrollo)."""
        self.check_giveaways.cancel()

    @app_commands.command(
        name="giveaway",
        description="[MOD] Inicia un sorteo en el canal actual."
    )
    @app_commands.describe(
        duracion="Duración (ej: 1d, 12h, 30m, 1h30m).",
        ganadores="Número de ganadores (ej: 1).",
        premio="El premio que se sortea."
    )
    @is_moderator()
    async def giveaway(self, interaction: discord.Interaction, duracion: str, ganadores: app_commands.Range[int, 1, 20], premio: str):
        
        await interaction.response.defer(ephemeral=True)
        
        # 1. Parsear la duración
        delta = parse_duration(duracion)
        if not delta or delta.total_seconds() <= 0:
            await interaction.followup.send("Formato de duración inválido. Usa 'd', 'h', 'm', 's'. (Ej: 1d12h)", ephemeral=True)
            return
            
        end_time = datetime.datetime.now(datetime.UTC) + delta
        
        # 2. Crear el Embed del sorteo
        embed = discord.Embed(
            title=f"🎉 ¡SORTEO! 🎉",
            description=f"**Premio:** {premio}\n**Ganador(es):** {ganadores}\n\nReacciona con el botón **Participar** para entrar.",
            color=discord.Color.magenta(),
            timestamp=end_time
        )
        embed.set_footer(text="Finaliza") # El timestamp al lado lo hace automático

        # 3. Enviar el mensaje y registrarlo
        try:
            view = GiveawayButton()
            message = await interaction.channel.send(embed=embed, view=view)
            
            # 4. Guardar en la Base de Datos
            db = sqlite3.connect('data/community.db')
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO giveaways (message_id, guild_id, channel_id, end_time, winner_count, prize) VALUES (?, ?, ?, ?, ?, ?)",
                (message.id, interaction.guild.id, interaction.channel.id, end_time.isoformat(), ganadores, premio)
            )
            db.commit()
            db.close()
            
            await interaction.followup.send("¡Sorteo creado con éxito!", ephemeral=True)
            
        except Exception as e:
            print(f"Error al crear sorteo: {e}")
            await interaction.followup.send(f"Error al crear el sorteo: {e}", ephemeral=True)

    # -----------------------------------------------------------------
    # --- La Tarea en Segundo Plano (¡100% Fiable!) ---
    # -----------------------------------------------------------------
    @tasks.loop(seconds=30) # Comprueba cada 30 segundos
    async def check_giveaways(self):
        """Comprueba la BBDD por sorteos finalizados."""
        
        # Esperar a que el bot esté 100% conectado
        await self.bot.wait_until_ready()
        
        now = datetime.datetime.now(datetime.UTC)
        db = sqlite3.connect('data/community.db')
        db.row_factory = sqlite3.Row # Para leer como diccionario
        cursor = db.cursor()
        
        try:
            # 1. Buscar sorteos que hayan terminado
            cursor.execute("SELECT * FROM giveaways WHERE end_time <= ?", (now.isoformat(),))
            ended_giveaways = cursor.fetchall()
            
            if not ended_giveaways:
                db.close()
                return # No hay nada que hacer

            # 2. Procesar cada sorteo finalizado
            for giveaway in ended_giveaways:
                channel = self.bot.get_channel(giveaway['channel_id'])
                if not channel:
                    continue # El canal fue borrado

                try:
                    # 3. Buscar el mensaje original
                    message = await channel.fetch_message(giveaway['message_id'])
                except discord.NotFound:
                    continue # El mensaje fue borrado
                
                # 4. Obtener los participantes de la BBDD
                cursor.execute("SELECT user_id FROM giveaway_participants WHERE message_id = ?", (giveaway['message_id'],))
                participants_rows = cursor.fetchall()
                # Convertir [(123,), (456,)] en [123, 456]
                participants_list = [row['user_id'] for row in participants_rows]

                # 5. Elegir al ganador(es)
                winner_mentions = []
                if not participants_list:
                    winner_str = "¡Nadie participó! 😢"
                else:
                    winner_count = giveaway['winner_count']
                    # Usamos min() por si participaron menos personas que el número de ganadores
                    k = min(winner_count, len(participants_list)) 
                    winner_ids = random.sample(participants_list, k=k)
                    winner_mentions = [f"<@{user_id}>" for user_id in winner_ids]
                    winner_str = ", ".join(winner_mentions)
                
                # 6. Actualizar el Embed original
                new_embed = message.embeds[0]
                new_embed.description = f"**Premio:** {giveaway['prize']}\n\n**Sorteo finalizado.**\n**Ganador(es):** {winner_str}"
                new_embed.color = discord.Color.greyple()
                
                # Quitar el botón
                await message.edit(embed=new_embed, view=None) 
                
                # 7. Anunciar al ganador en un mensaje nuevo
                if winner_mentions:
                    await channel.send(f"¡Felicidades {winner_str}! Habéis ganado: **{giveaway['prize']}** 🎉")

                # 8. Limpiar la Base de Datos
                # Borrar el sorteo (esto borra a los participantes gracias a "ON DELETE CASCADE")
                cursor.execute("DELETE FROM giveaways WHERE message_id = ?", (giveaway['message_id'],))
                db.commit()

        except Exception as e:
            print(f"Error en el bucle check_giveaways: {e}")
        finally:
            db.close()
        
async def setup(bot: commands.Bot):
    # ¡Importante! Añadimos la vista persistente ANTES de añadir el Cog
    bot.add_view(GiveawayButton())
    await bot.add_cog(Giveaways(bot))