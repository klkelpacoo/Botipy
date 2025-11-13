# cogs/music/music.py
import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord import ui
import asyncio
import yt_dlp
import functools
from pathlib import Path # Importación clave para rutas seguras [cite: 1]

# --- CONFIGURACIÓN DE RUTA ABSOLUTA (TU CÓDIGO) ---
# RUTA DEL ARCHIVO ACTUAL (cogs/music/music.py)
RUTA_ACTUAL = Path(__file__).resolve() [cite: 1]
# Navegamos 3 niveles arriba para llegar a la raíz 'Botipy/'
RUTA_PRINCIPAL = RUTA_ACTUAL.parent.parent.parent [cite: 1]
# Construye la ruta ABSOLUTA al archivo de cookies
RUTA_COOKIES_ABSOLUTA = RUTA_PRINCIPAL / "config" / "youtube_cookies.txt" [cite: 1]

# Verificación de existencia y creación (si no existe) para evitar Errno 2
if not RUTA_COOKIES_ABSOLUTA.exists(): [cite: 1]
    print(f"Advertencia: El archivo de cookies no existe en {RUTA_COOKIES_ABSOLUTA}. Creando archivo vacío.") [cite: 1]
    # Aseguramos que la carpeta exista antes de crear el archivo
    RUTA_COOKIES_ABSOLUTA.parent.mkdir(parents=True, exist_ok=True) [cite: 2]
    RUTA_COOKIES_ABSOLUTA.touch() [cite: 2]


# --- Opciones de YTDL/FFMPEG (MODIFICADO) ---
YTDL_OPTIONS = {
    # FORMATO: bestaudio (más rápido)
    'format': 'bestaudio',
    'extractaudio': True,
    # 'audioformat': 'mp3', # <<< ELIMINADO: Esta era la causa de la lentitud
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s', 'restrictfilenames': True,
    'noplaylist': True, 'nocheckcertificate': True, 'ignoreerrors': False,
    'logtostderr': False, 'quiet': True, 'no_warnings': True,
    'default_search': 'auto', 'source_address': '0.0.0.0',
    # Usamos tu ruta absoluta (¡bien hecho!)
    'cookiefile': str(RUTA_COOKIES_ABSOLUTA), [cite: 3]
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', [cite: 3]
    'options': '-vn -loglevel quiet', # Añadido -loglevel quiet para limpiar logs
}

# --- Clase 1: YTDLSource (El "Traductor") ---
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5): [cite: 4]
        super().__init__(source, volume) [cite: 4]
        self.data = data [cite: 4]
        self.title = data.get('title') [cite: 4]
        self.url = data.get('webpage_url') [cite: 4]
        self.thumbnail = data.get('thumbnail') [cite: 4]
        self.duration = data.get('duration') [cite: 4]
        self.uploader = data.get('uploader') [cite: 4]

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True): [cite: 4]
        loop = loop or asyncio.get_event_loop() [cite: 4]
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl: [cite: 4]
            partial_data = functools.partial(ydl.extract_info, url, download=not stream) [cite: 4]
            data = await loop.run_in_executor(None, partial_data) [cite: 4]
        if 'entries' in data: [cite: 4]
            data = data['entries'][0] [cite: 4]
        filename = data['url'] if stream else ydl.prepare_filename(data) [cite: 5]
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data) [cite: 5]
        
    @classmethod
    async def search(cls, query: str, *, loop=None): [cite: 5]
        loop = loop or asyncio.get_event_loop() [cite: 5]
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl: [cite: 5]
            partial_search = functools.partial(ydl.extract_info, f"ytsearch1:{query}", download=False) [cite: 5]
            data = await loop.run_in_executor(None, partial_search) [cite: 5, 6]
        if not data or 'entries' not in data or not data['entries']: [cite: 6]
            raise Exception("No se encontró la canción.") [cite: 6]
        return data['entries'][0] [cite: 6]

# -----------------------------------------------------------------
# --- Clase 2: La "Mesa de Mezclas" (Los Botones) ---
# -----------------------------------------------------------------
class MusicControlView(ui.View):
    def __init__(self, bot, player): [cite: 7]
        super().__init__(timeout=1800) [cite: 7]
        self.bot = bot [cite: 7]
        self.player = player [cite: 7]
        self.update_buttons() [cite: 7]

    def update_buttons(self): [cite: 7]
        """Actualiza el estado de los botones (label, emoji, style)"""
        
        # Botón Play/Pause
        if self.player.is_paused: [cite: 7]
            self.play_pause_button.label = "Reanudar" [cite: 7]
            self.play_pause_button.emoji = "▶️" [cite: 7]
            self.play_pause_button.style = discord.ButtonStyle.green [cite: 7]
        else: [cite: 8]
            self.play_pause_button.label = "Pausa" [cite: 8]
            self.play_pause_button.emoji = "⏸️" [cite: 8]
            self.play_pause_button.style = discord.ButtonStyle.secondary [cite: 8]

        # Botón Loop
        if self.player.loop_mode == "none": [cite: 8]
            self.loop_button.style = discord.ButtonStyle.secondary [cite: 8]
            self.loop_button.emoji = "➡️" [cite: 8]
        elif self.player.loop_mode == "song": [cite: 9]
            self.loop_button.style = discord.ButtonStyle.primary [cite: 9]
            self.loop_button.emoji = "🔂" [cite: 9]
        elif self.player.loop_mode == "queue": [cite: 9]
            self.loop_button.style = discord.ButtonStyle.primary [cite: 9]
            self.loop_button.emoji = "🔁" [cite: 9]
            
        # Deshabilitar botones si no hay nada sonando
        # (Se usa hasattr por si los botones aún no se han inicializado)
        if hasattr(self, 'play_pause_button'): [cite: 10]
            if not self.player.current_song: [cite: 10]
                self.play_pause_button.disabled = True [cite: 10]
                self.skip_button.disabled = True [cite: 10]

    async def check_permissions(self, interaction: discord.Interaction) -> bool: [cite: 10]
        """Comprueba si el usuario puede usar los botones."""
        if not interaction.user.voice or not interaction.user.voice.channel: [cite: 10]
            await interaction.response.send_message("Debes estar en un canal de voz.", ephemeral=True, delete_after=5) [cite: 11]
            return False [cite: 11]
        if not self.player.voice_client: [cite: 11]
             await interaction.response.send_message("El bot no está conectado.", ephemeral=True, delete_after=5) [cite: 11]
             return False [cite: 11]
        if interaction.user.voice.channel != self.player.voice_client.channel: [cite: 11]
            await interaction.response.send_message("Debes estar en el *mismo* canal de voz que yo.", ephemeral=True, delete_after=5) [cite: 11, 12]
            return False [cite: 12]
        return True [cite: 12]

    @ui.button(label="Pausa", style=discord.ButtonStyle.secondary, emoji="⏸️") [cite: 12]
    async def play_pause_button(self, interaction: discord.Interaction, button: ui.Button): [cite: 12]
        if not await self.check_permissions(interaction): [cite: 12]
            return [cite: 12]
            
        if self.player.is_paused: [cite: 12]
            await self.player.resume() [cite: 13]
        else: [cite: 13]
            await self.player.pause() [cite: 13]
        
        await self.player.update_panel() [cite: 13]
        await interaction.response.defer() [cite: 13]

    @ui.button(label="Saltar", style=discord.ButtonStyle.secondary, emoji="⏭️") [cite: 13]
    async def skip_button(self, interaction: discord.Interaction, button: ui.Button): [cite: 13]
        if not await self.check_permissions(interaction): [cite: 13]
            return [cite: 13]
            
        if self.player.voice_client and self.player.voice_client.is_playing(): [cite: 14]
            self.player.voice_client.stop() [cite: 14]
            await interaction.response.send_message("¡Canción saltada!", ephemeral=True, delete_after=5) [cite: 14]
        else: [cite: 14]
            await interaction.response.send_message("No hay nada que saltar.", ephemeral=True, delete_after=5) [cite: 14]

    @ui.button(label="Repetir", style=discord.ButtonStyle.secondary, emoji="➡️") [cite: 14]
    async def loop_button(self, interaction: discord.Interaction, button: ui.Button): [cite: 14]
        if not await self.check_permissions(interaction): [cite: 14]
            return [cite: 15]
            
        new_mode = await self.player.toggle_loop() [cite: 15]
        await self.player.update_panel() [cite: 15]
        await interaction.response.send_message(f"Modo de repetición: **{new_mode}**", ephemeral=True, delete_after=5) [cite: 15]

    @ui.button(label="Detener", style=discord.ButtonStyle.danger, emoji="⏹️") [cite: 15]
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button): [cite: 15]
        if not await self.check_permissions(interaction): [cite: 15]
            return [cite: 15]

        # Sacamos el player del diccionario ANTES de desconectar [cite: 16]
        player_to_stop = self.bot.get_cog("Music").players.pop(interaction.guild.id, None) [cite: 16]
        
        if player_to_stop: [cite: 16]
            await player_to_stop.disconnect() [cite: 16]
        
        await interaction.response.send_message("¡Música detenida! Me voy. 👋", ephemeral=True, delete_after=5) [cite: 16, 17]

# -----------------------------------------------------------------
# --- Clase 3: El "Reproductor" (CON EL FIX DEL BUFFER) ---
# -----------------------------------------------------------------
class MusicPlayer:
    def __init__(self, bot, interaction: discord.Interaction): [cite: 17]
        self.bot = bot [cite: 17]
        self.guild = interaction.guild [cite: 17]
        self.text_channel = interaction.channel [cite: 17]
        self.voice_client = None [cite: 17]
        self.queue = asyncio.Queue() [cite: 17]
        self.next_song = asyncio.Event() [cite: 17]
        self.current_song = None [cite: 17]
        self.player_loop_task = None [cite: 17, 18]
        self.panel_message = None [cite: 18]
        self.is_paused = False [cite: 18]
        self.loop_mode = "none" [cite: 18]

    async def connect_vc(self, channel: discord.VoiceChannel): [cite: 18]
        if self.voice_client: [cite: 18]
            await self.voice_client.move_to(channel) [cite: 18]
        else: [cite: 18]
            self.voice_client = await channel.connect() [cite: 18]

    async def start_player_loop(self): [cite: 18]
        if self.player_loop_task and not self.player_loop_task.done(): [cite: 19]
            return [cite: 19]
        self.player_loop_task = self.bot.loop.create_task(self.player_loop()) [cite: 19]

    async def player_loop(self): [cite: 19]
        await self.bot.wait_until_ready() [cite: 19]
        
        while True: [cite: 19]
            try: [cite: 19]
                song_data = await asyncio.wait_for(self.queue.get(), timeout=300.0) [cite: 19]
                
                self.current_song = song_data [cite: 20]
                source = await YTDLSource.from_url(song_data['webpage_url'], loop=self.bot.loop, stream=True) [cite: 20]
                
                # --- INICIO DE LA LÓGICA DE PRE-BUFFER ---
                # 1. Inicia la reproducción
                self.voice_client.play(source, after=lambda e: self.bot.loop.call_soon_threadsafe(self.next_song.set)) [cite: 20]
                
                # 2. Pausa interna para que FFMPEG conecte y llene el buffer
                self.voice_client.pause()
                
                # 3. El estado deseado es 'reproduciendo', actualizamos el panel
                self.is_paused = False [cite: 20]
                await self.update_panel(source=source) [cite: 21]
                
                # 4. Espera (1.0s es un buen punto de partida para Render)
                await asyncio.sleep(1.0) 
                
                # 5. Reanuda, *solo si* el usuario no ha pausado/detenido mientras tanto
                if self.voice_client and self.voice_client.is_paused() and not self.is_paused:
                     self.voice_client.resume()
                # --- FIN DE LA LÓGICA DE PRE-BUFFER ---
                
                await self.next_song.wait() [cite: 21]
                
            except asyncio.TimeoutError: [cite: 21]
                await self.disconnect() [cite: 22]
                try: [cite: 22]
                    await self.text_channel.send("Me voy, la cola está vacía. 😴", delete_after=30) [cite: 22, 23]
                except discord.HTTPException: [cite: 23]
                    pass [cite: 23]
                break [cite: 23]
            except Exception as e: [cite: 23]
                print(f"Error en el player_loop: {e}") [cite: 23]
                try: [cite: 23, 24]
                    await self.text_channel.send(f"Error al reproducir: {e}", embed=None, delete_after=10) [cite: 24]
                except discord.HTTPException: [cite: 24]
                    pass [cite: 24]
                continue [cite: 24]
            finally: [cite: 24]
                if self.loop_mode == "song" and self.current_song: [cite: 25]
                    self.queue._queue.appendleft(self.current_song) [cite: 25]
                elif self.loop_mode == "queue" and self.current_song: [cite: 25]
                    await self.queue.put(self.current_song) [cite: 25]
                
                self.current_song = None [cite: 26]
                self.next_song.clear() [cite: 26]
                
    async def disconnect(self): [cite: 26]
        """Detiene todo, borra el panel y se desconecta."""
        if self.player_loop_task: [cite: 26]
            self.player_loop_task.cancel() [cite: 26]
            self.player_loop_task = None [cite: 26, 27]
            
        self.queue = asyncio.Queue() [cite: 27]
        
        if self.panel_message: [cite: 27]
            try: [cite: 27]
                await self.panel_message.edit(content="Reproductor detenido. 👋", embed=None, view=None, delete_after=10) [cite: 27, 28]
            except discord.NotFound: [cite: 28]
                pass [cite: 28]
            self.panel_message = None [cite: 28]
            
        if self.voice_client: [cite: 28]
            await self.voice_client.disconnect() [cite: 28]
            self.voice_client = None [cite: 28]

    async def update_panel(self, source=None): [cite: 28, 29]
        """Crea o edita el panel de control."""
        if not source and self.current_song: [cite: 29]
            try: [cite: 29]
                # Intenta buscar de nuevo si no hay 'source' (para botones)
                song_data = await YTDLSource.search(self.current_song['title'], loop=self.bot.loop) [cite: 29]
                source = YTDLSource(None, data=song_data) # Crea un 'source' falso solo con datos [cite: 29]
            except Exception: [cite: 29]
                 source = None [cite: 30]
        
        view = MusicControlView(self.bot, self) [cite: 30]
        
        if not source: [cite: 30]
            # Si sigue sin haber source, solo actualiza la vista (botones)
            if self.panel_message: [cite: 30]
                try: [cite: 30]
                    await self.panel_message.edit(view=view) [cite: 30]
                except discord.NotFound: [cite: 31]
                    self.panel_message = None [cite: 31]
            return [cite: 31]

        embed = discord.Embed( [cite: 31]
            title="Reproduciendo Ahora 🎶", [cite: 31]
            description=f"**[{source.title}]({source.url})**\nPor: {source.uploader}", [cite: 31]
            color=discord.Color.random() [cite: 31]
        ) [cite: 32]
        embed.set_thumbnail(url=source.thumbnail) [cite: 32]
        embed.set_footer(text=f"Loop: {self.loop_mode.capitalize()} | {'Pausado' if self.is_paused else 'Reproduciendo'}") [cite: 32, 33]
        
        if self.panel_message: [cite: 33]
            try: [cite: 33]
                await self.panel_message.edit(embed=embed, view=view) [cite: 33]
            except discord.NotFound: [cite: 33]
                self.panel_message = await self.text_channel.send(embed=embed, view=view) [cite: 33]
        else: [cite: 33]
            self.panel_message = await self.text_channel.send(embed=embed, view=view) [cite: 34]

    async def pause(self): [cite: 34]
        if self.voice_client and self.voice_client.is_playing(): [cite: 34]
            self.voice_client.pause() [cite: 34]
            self.is_paused = True [cite: 34]

    async def resume(self): [cite: 34]
        if self.voice_client and self.voice_client.is_paused(): [cite: 34]
            self.voice_client.resume() [cite: 34]
            self.is_paused = False [cite: 34]
            
    async def toggle_loop(self) -> str: [cite: 35]
        if self.loop_mode == "none": [cite: 35]
            self.loop_mode = "song" [cite: 35]
        elif self.loop_mode == "song": [cite: 35]
            self.loop_mode = "queue" [cite: 35]
        elif self.loop_mode == "queue": [cite: 35]
            self.loop_mode = "none" [cite: 35]
        return self.loop_mode.capitalize() [cite: 35]

# -----------------------------------------------------------------
# --- Clase 4: El "Control Remoto" (CON EL FIX DEL DEFER) ---
# -----------------------------------------------------------------
class Music(commands.Cog): [cite: 36]
    def __init__(self, bot: commands.Bot): [cite: 36]
        self.bot = bot [cite: 36]
        self.players = {} [cite: 36]

    def get_player(self, interaction: discord.Interaction) -> MusicPlayer: [cite: 36]
        """Obtiene el reproductor del servidor, o crea uno nuevo."""
        if interaction.guild.id in self.players: [cite: 36]
            player = self.players[interaction.guild.id] [cite: 36]
            player.text_channel = interaction.channel [cite: 36, 37]
            return player [cite: 37]
        else: [cite: 37]
            player = MusicPlayer(self.bot, interaction) [cite: 37]
            self.players[interaction.guild.id] = player [cite: 37]
            return player [cite: 37]

    @app_commands.command(name="play", description="Reproduce una canción de YouTube (búsqueda o URL).") [cite: 37]
    @app_commands.describe(busqueda="El nombre o URL de la canción.") [cite: 37]
    async def play(self, interaction: discord.Interaction, busqueda: str): [cite: 37]
        
        # *** 1. FIX DEFER: Se difiere ANTES de cualquier lógica ***
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            print("Error 10062: La interacción expiró incluso antes de poder hacer defer(). Plataforma demasiado lenta.")
            return

        # *** 2. Comprobaciones (ahora con followup) ***
        if not interaction.user.voice or not interaction.user.voice.channel: [cite: 38]
            await interaction.followup.send("¡Debes estar en un canal de voz para pedir música!", ephemeral=True)
            return
            
        player = self.get_player(interaction) [cite: 39]
        
        try:
            # *** 3. Resto de la lógica ***
            await player.connect_vc(interaction.user.voice.channel) [cite: 39]
            song_data = await YTDLSource.search(busqueda, loop=self.bot.loop) [cite: 39]
            
            await player.queue.put(song_data) [cite: 39]
            await player.start_player_loop() [cite: 39]
            
            embed = discord.Embed( [cite: 40]
                title="Añadido a la Cola 🎶", [cite: 40]
                description=f"**[{song_data['title']}]({song_data['webpage_url']})**", [cite: 40]
                color=discord.Color.green() [cite: 40]
            )
            embed.set_thumbnail(url=song_data['thumbnail']) [cite: 40]
            
            await interaction.followup.send(embed=embed, ephemeral=True) [cite: 41]
            
        except Exception as e: [cite: 41]
            await interaction.followup.send(f"❌ Error al buscar o añadir la canción: {e}", ephemeral=True) [cite: 41]
            return [cite: 41]
            
    @app_commands.command(name="queue", description="Muestra la cola de reproducción.") [cite: 41]
    async def queue(self, interaction: discord.Interaction): [cite: 41, 42]
        if interaction.guild.id not in self.players: [cite: 42]
            await interaction.response.send_message("La cola está vacía.", ephemeral=True) [cite: 42]
            return [cite: 42]
        player = self.players[interaction.guild.id] [cite: 42]
        embed = discord.Embed(title="Cola de Reproducción 🎶", color=discord.Color.blue()) [cite: 42]
        if player.current_song: [cite: 42]
            embed.add_field(name="Sonando Ahora:", value=f"**[{player.current_song['title']}]({player.current_song['webpage_url']})**", inline=False) [cite: 42]
        
        if player.queue.empty(): [cite: 43]
            embed.description = "No hay más canciones en la cola." [cite: 43]
        else: [cite: 43]
            queue_list_str = "" [cite: 43]
            for i, song in enumerate(list(player.queue._queue)): [cite: 43]
                queue_list_str += f"**{i+1}.** [{song['title']}]({song['webpage_url']})\n" [cite: 43]
                if i >= 9 and player.queue.qsize() > 10: [cite: 43, 44]
                    queue_list_str += f"...y {player.queue.qsize() - (i+1)} más." [cite: 44]
                    break [cite: 44]
            embed.add_field(name="A Continuación:", value=queue_list_str, inline=False) [cite: 44]
        await interaction.response.send_message(embed=embed, ephemeral=True) [cite: 44]

    # --- Evento de limpieza ---
    @commands.Cog.listener() [cite: 44]
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState): [cite: 44]
        """Limpia el reproductor si el bot es desconectado manualmente.""" [cite: 45]
        if member.id != self.bot.user.id: [cite: 45]
            return [cite: 45]
            
        if before.channel is not None and after.channel is None: [cite: 5]
            if member.guild.id in self.players: [cite: 45]
                player = self.players.pop(member.guild.id) [cite: 45]
                await player.disconnect() [cite: 46]


# --- Función Setup ---
async def setup(bot: commands.Bot): [cite: 46]
    await bot.add_cog(Music(bot)) [cite: 46]
