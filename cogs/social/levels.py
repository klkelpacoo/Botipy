# cogs/social/levels.py
import os
import discord
from discord.ext import commands
from discord import app_commands
import datetime
import sqlite3
import random
import math # Para la fórmula de nivel

# --- CONSTANTES DEL SISTEMA DE NIVELES ---
XP_COOLDOWN = 60 # Segundos de cooldown para ganar XP
XP_MIN = 15      # Mínimo XP por mensaje
XP_MAX = 25      # Máximo XP por mensaje

# --- Clase del Cog ---
class Levels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Creamos una BBDD separada para la economía
        self.init_database()
        # Un diccionario para manejar los cooldowns en memoria (más rápido)
        self.user_cooldowns = {} # {user_id: last_message_time}

    def init_database(self):
        """Crea el archivo .db y la tabla 'levels' si no existen."""
        os.makedirs('data', exist_ok=True) 
        db = sqlite3.connect('data/social.db') # Nueva BBDD
        cursor = db.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS levels (
            user_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id)
        )
        """)
        db.commit()
        db.close()

    # --- Función Helper: Obtener/Crear Usuario ---
    def get_or_create_user(self, user_id: int, guild_id: int) -> dict:
        """Obtiene el perfil de nivel de un usuario. Si no existe, lo crea."""
        db = sqlite3.connect('data/social.db')
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cursor.execute("SELECT * FROM levels WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        data = cursor.fetchone()
        
        if data is None:
            # Si no existe, lo insertamos
            cursor.execute("INSERT INTO levels (user_id, guild_id) VALUES (?, ?)", (user_id, guild_id))
            db.commit()
            
            cursor.execute("SELECT * FROM levels WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
            data = cursor.fetchone()
            
        db.close()
        return data

    # --- Función Helper: Fórmula de Nivel ---
    def xp_para_nivel(self, level: int) -> int:
        """Calcula el XP total necesario para alcanzar un nivel."""
        # Fórmula popular: 5 * (lvl^2) + 50 * lvl + 100
        # XP para Nivel 1: 155
        # XP para Nivel 2: 320
        # XP para Nivel 3: 505
        return 5 * (level ** 2) + 50 * level + 100

    # -----------------------------------------------------------------
    # --- Evento 1: Ganar XP con cada mensaje ---
    # -----------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Se activa CADA VEZ que se envía un mensaje."""
        
        # 1. Ignorar DMs y bots
        if not message.guild or message.author.bot:
            return
            
        # 2. Comprobar Cooldown (usando el dict en memoria)
        user_id = message.author.id
        guild_id = message.guild.id
        current_time = datetime.datetime.now()
        
        if user_id in self.user_cooldowns:
            last_time = self.user_cooldowns[user_id]
            if (current_time - last_time).total_seconds() < XP_COOLDOWN:
                return # Aún en cooldown, no hacer nada
        
        # 3. Actualizar Cooldown en memoria
        self.user_cooldowns[user_id] = current_time
        
        # 4. Dar XP
        xp_ganado = random.randint(XP_MIN, XP_MAX)
        
        try:
            db = sqlite3.connect('data/social.db')
            db.row_factory = sqlite3.Row
            cursor = db.cursor()
            
            # Obtenemos los datos (o creamos el usuario)
            cursor.execute("SELECT * FROM levels WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
            user_data = cursor.fetchone()
            
            if user_data is None:
                cursor.execute("INSERT INTO levels (user_id, guild_id, xp, level) VALUES (?, ?, ?, ?)", (user_id, guild_id, xp_ganado, 0))
                db.commit()
                user_xp = xp_ganado
                user_level = 0
            else:
                user_xp = user_data['xp'] + xp_ganado
                user_level = user_data['level']
                cursor.execute("UPDATE levels SET xp = ? WHERE user_id = ? AND guild_id = ?", (user_xp, user_id, guild_id))
                db.commit()
            
            # 5. Comprobar si sube de nivel
            xp_necesario = self.xp_para_nivel(user_level)
            
            if user_xp >= xp_necesario:
                # ¡SUBE DE NIVEL!
                nuevo_nivel = user_level + 1
                cursor.execute("UPDATE levels SET level = ? WHERE user_id = ? AND guild_id = ?", (nuevo_nivel, user_id, guild_id))
                db.commit()
                
                # ¡Enviar mensaje de felicitación!
                embed = discord.Embed(
                    title="¡Subiste de Nivel! 🚀",
                    description=f"¡Felicidades, {message.author.mention}! Has alcanzado el **Nivel {nuevo_nivel}**.",
                    color=discord.Color.random()
                )
                
                # Enviarlo al canal donde subió de nivel
                await message.channel.send(embed=embed)
            
            db.close()
            
        except Exception as e:
            print(f"Error de DB en on_message (levels): {e}")

    # -----------------------------------------------------------------
    # --- Comando 2: /rank ---
    # -----------------------------------------------------------------
    @app_commands.command(
        name="rank",
        description="Muestra tu nivel y XP actual."
    )
    @app_commands.describe(miembro="La persona cuyo rango quieres ver (opcional).")
    async def rank(self, interaction: discord.Interaction, miembro: discord.Member = None):
        """Muestra una tarjeta de rango con barra de progreso."""
        
        await interaction.response.defer()
        
        target_user = miembro or interaction.user
        
        # Obtenemos los datos
        user_data = self.get_or_create_user(target_user.id, interaction.guild.id)
        
        user_level = user_data['level']
        user_xp = user_data['xp']
        
        # --- Cálculo de la Barra de Progreso ---
        # 1. XP necesario para el nivel *anterior* (inicio de la barra)
        xp_nivel_actual = self.xp_para_nivel(user_level - 1) if user_level > 0 else 0
        # 2. XP necesario para el nivel *siguiente* (fin de la barra)
        xp_nivel_siguiente = self.xp_para_nivel(user_level)
        
        # 3. XP que el usuario tiene EN ESTE NIVEL
        xp_en_nivel = user_xp - xp_nivel_actual
        # 4. XP total que necesita para pasar de nivel
        xp_total_del_nivel = xp_nivel_siguiente - xp_nivel_actual
        
        # 5. Calcular porcentaje
        try:
            porcentaje = int((xp_en_nivel / xp_total_del_nivel) * 100)
        except ZeroDivisionError:
            porcentaje = 0
            
        # 6. Crear la barra de texto (10 bloques)
        bloques_llenos = int(porcentaje / 10)
        bloques_vacios = 10 - bloques_llenos
        barra_progreso = "█" * bloques_llenos + "░" * bloques_vacios
        
        # --- Crear el Embed ---
        embed = discord.Embed(
            title=f"Rango de {target_user.display_name}",
            color=target_user.color
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        embed.add_field(name="Nivel", value=f"**{user_level}**", inline=True)
        embed.add_field(name="XP Total", value=f"**{user_xp}**", inline=True)
        
        embed.add_field(
            name="Progreso",
            value=f"`[{barra_progreso}]`\n({xp_en_nivel} / {xp_total_del_nivel} XP)",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
        
# --- Función Setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Levels(bot))