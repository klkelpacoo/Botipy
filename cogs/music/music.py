# cogs/music/music.py
import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord import ui
import asyncio
import yt_dlp
import functools
from pathlib import Path # Importación clave para rutas seguras

# --- CONFIGURACIÓN DE RUTA ABSOLUTA (TU CÓDIGO) ---
# RUTA DEL ARCHIVO ACTUAL (cogs/music/music.py)
RUTA_ACTUAL = Path(__file__).resolve()
# Navegamos 3 niveles arriba para llegar a la raíz 'Botipy/'
RUTA_PRINCIPAL = RUTA_ACTUAL.parent.parent.parent
# Construye la ruta ABSOLUTA al archivo de cookies
RUTA_COOKIES_ABSOLUTA = RUTA_PRINCIPAL / "config" / "youtube_cookies.txt"

# Verificación de existencia y creación (si no existe) para evitar Errno 2
if not RUTA_COOKIES_ABSOLUTA.exists():
    print(f"Advertencia: El archivo de cookies no existe en {RUTA_COOKIES_ABSOLUTA}. Creando archivo vacío.")
    # Aseguramos que la carpeta exista antes de crear el archivo
    RUTA_COOKIES_ABSOLUTA.parent.mkdir(parents=True, exist_ok=True)
    RUTA_COOKIES_ABSOLUTA.touch()


# --- Opciones de YTDL/FFMPEG (CORREGIDO) ---
YTDL_OPTIONS = {
    # *** ¡¡ESTA ES LA CORRECCIÓN!! ***
    # 'bestaudio' es la opción correcta para STREAMING de solo audio.
    # Opciones como 'bestvideo+bestaudio' son para DESCARGAR y causan "error formato".
    'format': 'bestaudio', 
    'extractaudio': True,
    # 'audioformat': 'mp3', # ELIMINADO: Causa lentitud
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s', 'restrictfilenames': True,
    'noplaylist': True, 'nocheckcertificate': True, 'ignoreerrors': False,
    'logtostderr': False, 'quiet': True, 'no_warnings': True,
    'default_search': 'auto', 'source_address': '0.0.0.0',
    # Usamos tu ruta absoluta
    'cookiefile': str(RUTA_COOKIES_ABSOLUTA),
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -loglevel quiet', 
}

# --- Clase 1: YTDLSource (El "Traductor") ---
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('webpage_url')
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration')
        self.uploader = data.get('uploader')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            partial_data = functools.partial(ydl.extract_info, url, download=not stream)
            data = await loop.run_in_executor(None, partial_data)
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ydl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)
        
    @classmethod
    async def search(cls, query: str, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            partial_search = functools.partial(ydl.extract_info, f"ytsearch1:{query}", download=False)
            data = await loop.run_in_executor(None, partial_search)
        if not data or 'entries' not in data or not data['entries']:
            raise Exception("No se encontró la canción.")
        return data['entries'][0]

# -----------------------------------------------------------------
# --- Clase 2: La "Mesa de Mezclas" (CON EL FIX 'hasattr') ---
# -----------------------------------------------------------------
class MusicControlView(ui.View):
    def __init__(self, bot, player):
        super().__init__(timeout=1800)
        self.bot = bot
        self.player = player
        self.update_buttons()

    def update_buttons(self):
        """Actualiza el estado de los botones (label, emoji, style)"""
        
        # FIX: 'hasattr' evita el crash al cargar el Cog
        if not hasattr(self, 'play_pause_button'):
            return # Salimos si los botones no están listos

        # Botón Play/Pause
        if self.player.is_paused:
            self.play_pause_button.label = "Reanudar"
            self.play_pause_button.emoji = "▶️"
            self.play_pause_button.style = discord.ButtonStyle.green
        else:
            self.play_pause_button.label = "Pausa"
            self.play_pause_button.emoji = "⏸️"
            self.play_pause_button.style = discord.ButtonStyle.secondary

        # Botón Loop
        if self.player.loop_mode == "none":
            self.loop_button.style = discord.ButtonStyle.secondary
            self.loop_button.emoji = "➡️"
        elif self.player.loop_mode == "song":
            self.loop_button.style = discord.ButtonStyle.primary
            self.loop_button.emoji = "🔂"
        elif self.player.loop_mode == "queue":
            self.loop_button.style = discord.ButtonStyle.primary
            self.loop_button.emoji = "🔁"
            
        # Deshabilitar botones si no hay nada sonando
        if not self.player.current_song:
            self.play_pause_button.disabled = True
            self.skip_button.disabled = True


    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        """Comprueba si el usuario puede usar los botones."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("Debes estar en un canal de voz.", ephemeral=True, delete_after=5)
            return False
        if not self.player.voice_client:
             await interaction.response.send_message("El bot no está conectado.", ephemeral=True, delete_after=5)
             return False
        if interaction.user.voice.channel != self.player.voice_client.channel:
            await interaction.response.send_message("Debes estar en el *mismo* canal de voz que yo.", ephemeral=True, delete_after=5)
            return False
        return True

    @ui.button(label="Pausa", style=discord.ButtonStyle.secondary, emoji="⏸️")
    async def play_pause_button(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_permissions(interaction):
            return
            
        if self.player.is_paused:
            await self.player.resume()
        else:
            await self.player.pause()
        
        await self.player.update_panel()
        await interaction.response.defer()

    @ui.button(label="Saltar", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def skip_button(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_permissions(interaction):
            return
            
        if self.player.voice_client and self.player.voice_client.is_playing():
            self.player.voice_client.stop()
            await interaction.response.send_message("¡Canción saltada!", ephemeral=True, delete_after=5)
        else:
            await interaction.response.send_message("No hay nada que saltar.", ephemeral=True, delete_after=5)

    @ui.button(label="Repetir", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def loop_button(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_permissions(interaction):
            return
            
        new_mode = await self.player.toggle_loop()
        await self.player.update_panel()
        await interaction.response.send_message(f"Modo de repetición: **{new_mode}**", ephemeral=True, delete_after=5)

    @ui.button(label="Detener", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_permissions(interaction):
            return

        # Sacamos el player del diccionario ANTES de desconectar
        player_to_stop = self.bot.get_cog("Music").players.pop(interaction.guild.id, None)
        
        if player_to_stop:
            await player_to_stop.disconnect()
        
        await interaction.response.send_message("¡Música detenida! Me voy. 👋", ephemeral=True, delete_after=5)

# -----------------------------------------------------------------
# --- Clase 3: El "Reproductor" (CON EL FIX DEL BUFFER) ---
# -----------------------------------------------------------------
class MusicPlayer:
    def __init__(self, bot, interaction: discord.Interaction):
        self.bot = bot
        self.guild = interaction.guild
        self.text_channel = interaction.channel
        self.voice_client = None
        self.queue = asyncio.Queue()
        self.next_song = asyncio.Event()
        self.current_song = None
        self.player_loop_task = None
        self.panel_message = None
        self.is_paused = False
        self.loop_mode = "none"

    async def connect_vc(self, channel: discord.VoiceChannel):
        if self.voice_client:
            await self.voice_client.move_to(channel)
        else:
            self.voice_client = await channel.connect()

    async def start_player_loop(self):
        if self.player_loop_task and not self.player_loop_task.done():
            return
        self.player_loop_task = self.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        await self.bot.wait_until_ready()
        
        while True:
            try:
                song_data = await asyncio.wait_for(self.queue.get(), timeout=300.0)
                
                self.current_song = song_data
                source = await YTDLSource.from_url(song_data['webpage_url'], loop=self.bot.loop, stream=True)
                
                # --- INICIO DE LA LÓGICA DE PRE-BUFFER ---
                self.voice_client.play(source, after=lambda e: self.bot.loop.call_soon_threadsafe(self.next_song.set))
                self.voice_client.pause()
                self.is_paused = False
                await self.update_panel(source=source)
                
                # Buffer de 1 segundo
                await asyncio.sleep(1.0) 
                
                if self.voice_client and self.voice_client.is_paused() and not self.is_paused:
                     self.voice_client.resume()
                # --- FIN DE LA LÓGICA DE PRE-BUFFER ---
                
                await self.next_song.wait()
                
            except asyncio.TimeoutError:
                await self.disconnect()
                try:
                    await self.text_channel.send("Me voy, la cola está vacía. 😴", delete_after=30)
                except discord.HTTPException:
                    pass
                break
            except Exception as e:
                print(f"Error en el player_loop: {e}")
                try:
                    await self.text_channel.send(f"Error al reproducir: {e}", embed=None, delete_after=10)
                except discord.HTTPException:
                    pass
                continue
            finally:
                if self.loop_mode == "song" and self.current_song:
                    self.queue._queue.appendleft(self.current_song)
                elif self.loop_mode == "queue" and self.current_song:
                    await self.queue.put(self.current_song)
                
                self.current_song = None
                self.next_song.clear()
                
    async def disconnect(self):
        """Detiene todo, borra el panel y se desconecta."""
        if self.player_loop_task:
            self.player_loop_task.cancel()
            self.player_loop_task = None
            
        self.queue = asyncio.Queue()
        
        if self.panel_message:
            try:
                await self.panel_message.edit(content="Reproductor detenido. 👋", embed=None, view=None, delete_after=10)
            except discord.NotFound:
                pass
            self.panel_message = None
            
        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None

    async def update_panel(self, source=None):
        """Crea o edita el panel de control."""
        if not source and self.current_song:
            try:
                # Intenta buscar de nuevo si no hay 'source' (para botones)
                song_data = await YTDLSource.search(self.current_song['title'], loop=self.bot.loop)
                source = YTDLSource(None, data=song_data) # Crea un 'source' falso solo con datos
            except Exception:
                 source = None
        
        view = MusicControlView(self.bot, self)
        
        if not source:
            # Si sigue sin haber source, solo actualiza la vista (botones)
            if self.panel_message:
                try:
                    await self.panel_message.edit(view=view)
                except discord.NotFound:
                    self.panel_message = None
            return

        embed = discord.Embed(
            title="Reproduciendo Ahora 🎶",
            description=f"**[{source.title}]({source.url})**\nPor: {source.uploader}",
            color=discord.Color.random()
        )
        embed.set_thumbnail(url=source.thumbnail)
        embed.set_footer(text=f"Loop: {self.loop_mode.capitalize()} | {'Pausado' if self.is_paused else 'Reproduciendo'}")
        
        if self.panel_message:
            try:
                await self.panel_message.edit(embed=embed, view=view)
            except discord.NotFound:
                self.panel_message = await self.text_channel.send(embed=embed, view=view)
        else:
            self.panel_message = await self.text_channel.send(embed=embed, view=view)

    async def pause(self):
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            self.is_paused = True

    async def resume(self):
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            self.is_paused = False
            
    async def toggle_loop(self) -> str:
        if self.loop_mode == "none":
            self.loop_mode = "song"
        elif self.loop_mode == "song":
            self.loop_mode = "queue"
        elif self.loop_mode == "queue":
            self.loop_mode = "none"
        return self.loop_mode.capitalize()

# -----------------------------------------------------------------
# --- Clase 4: El "Control Remoto" (CON EL FIX DEL DEFER) ---
# -----------------------------------------------------------------
class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players = {}

    def get_player(self, interaction: discord.Interaction) -> MusicPlayer:
        """Obtiene el reproductor del servidor, o crea uno nuevo."""
        if interaction.guild.id in self.players:
            player = self.players[interaction.guild.id]
            player.text_channel = interaction.channel
            return player
        else:
            player = MusicPlayer(self.bot, interaction)
            self.players[interaction.guild.id] = player
            return player

    @app_commands.command(name="play", description="Reproduce una canción de YouTube (búsqueda o URL).")
    @app_commands.describe(busqueda="El nombre o URL de la canción.")
    async def play(self, interaction: discord.Interaction, busqueda: str):
        
        # *** 1. FIX DEFER: Se difiere ANTES de cualquier lógica ***
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            print("Error 10062: La interacción expiró incluso antes de poder hacer defer(). Plataforma demasiado lenta.")
            return

        # *** 2. Comprobaciones (ahora con followup) ***
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("¡Debes estar en un canal de voz para pedir música!", ephemeral=True)
            return
            
        player = self.get_player(interaction)
        
        try:
            # *** 3. Resto de la lógica ***
            await player.connect_vc(interaction.user.voice.channel)
            song_data = await YTDLSource.search(busqueda, loop=self.bot.loop)
            
            await player.queue.put(song_data)
            await player.start_player_loop()
            
            embed = discord.Embed(
                title="Añadido a la Cola 🎶",
                description=f"**[{song_data['title']}]({song_data['webpage_url']})**",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=song_data['thumbnail'])
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error al buscar o añadir la canción: {e}", ephemeral=True)
            return
            
    @app_commands.command(name="queue", description="Muestra la cola de reproducción.")
    async def queue(self, interaction: discord.Interaction):
        if interaction.guild.id not in self.players:
            await interaction.response.send_message("La cola está vacía.", ephemeral=True)
            return
        player = self.players[interaction.guild.id]
        embed = discord.Embed(title="Cola de Reproducción 🎶", color=discord.Color.blue())
        if player.current_song:
            embed.add_field(name="Sonando Ahora:", value=f"**[{player.current_song['title']}]({player.current_song['webpage_url']})**", inline=False)
        
        if player.queue.empty():
            embed.description = "No hay más canciones en la cola."
        else:
            queue_list_str = ""
            for i, song in enumerate(list(player.queue._queue)):
                queue_list_str += f"**{i+1}.** [{song['title']}]({song['webpage_url']})\n"
                if i >= 9 and player.queue.qsize() > 10:
                    queue_list_str += f"...y {player.queue.qsize() - (i+1)} más."
                    break
            embed.add_field(name="A Continuación:", value=queue_list_str, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Evento de limpieza ---
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Limpia el reproductor si el bot es desconectado manualmente."""
        if member.id != self.bot.user.id:
            return
            
        if before.channel is not None and after.channel is None:
            if member.guild.id in self.players:
                player = self.players.pop(member.guild.id)
                await player.disconnect()


# --- Función Setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
