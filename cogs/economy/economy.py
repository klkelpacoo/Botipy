# cogs/economy/economy.py
import os
import discord
from discord.ext import commands
from discord import app_commands
import datetime
import sqlite3
import random

# --- CONSTANTES DE ECONOMÍA ---
DAILY_AMOUNT = 100 
DAILY_COOLDOWN = 23 

# --- ¡NUEVO! Cargar el ID de Moderador ---
try:
    MOD_ROLE_ID = int(os.getenv("MODERATOR_ROLE_ID"))
except (TypeError, ValueError):
    print("Error: MODERATOR_ROLE_ID no está definido o no es válido en .env (para economy.py admin)")
    MOD_ROLE_ID = None

# --- ¡NUEVO! CHECK DE PERMISOS DE MODERADOR ---
def is_moderator():
    """Comprueba si el usuario tiene el ROL ID de Moderador del .env"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not MOD_ROLE_ID:
            return False 
        role = interaction.user.get_role(MOD_ROLE_ID)
        return role is not None
    return app_commands.check(predicate)

# --- Clase del Cog ---
class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.init_database()

    def init_database(self):
        """Crea las tablas 'balances' y 'shop_items' si no existen."""
        os.makedirs('data', exist_ok=True) 
        db = sqlite3.connect('data/economy.db') 
        cursor = db.cursor()
        
        # Tabla de Balances
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS balances (
            user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL,
            balance INTEGER DEFAULT 0, last_daily DATETIME,
            PRIMARY KEY (user_id, guild_id)
        )
        """)
        
        # --- ¡NUEVA TABLA! Tienda ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            price INTEGER NOT NULL,
            role_id INTEGER NOT NULL UNIQUE
        )
        """)
        
        db.commit()
        db.close()

    # --- Función Helper: Obtener/Crear Balance (Sin cambios) ---
    async def get_or_create_balance(self, user_id: int, guild_id: int) -> dict:
        db = sqlite3.connect('data/economy.db')
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        cursor.execute("SELECT * FROM balances WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        data = cursor.fetchone()
        if data is None:
            cursor.execute("INSERT INTO balances (user_id, guild_id, balance) VALUES (?, ?, ?)", (user_id, guild_id, 0))
            db.commit()
            cursor.execute("SELECT * FROM balances WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
            data = cursor.fetchone()
        db.close()
        return data

    # --- Comandos Públicos (Sin cambios) ---
    # (/balance, /daily, /pagar, /leaderboard, /apostar)
    # ... (Omitidos por brevedad, están exactamente igual que antes) ...
    @app_commands.command(name="balance", description="Comprueba tu balance de Nocoins 🪙.")
    async def balance(self, interaction: discord.Interaction, miembro: discord.Member = None):
        # ... (código igual)
        target_user = miembro or interaction.user
        data = await self.get_or_create_balance(target_user.id, interaction.guild.id)
        embed = discord.Embed(title=f"Balance de {target_user.display_name}", color=discord.Color.gold())
        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.add_field(name="Saldo:", value=f"**{data['balance']}** Nocoins 🪙")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Recoge tu paga diaria de Nocoins.")
    async def daily(self, interaction: discord.Interaction):
        # ... (código igual)
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        data = await self.get_or_create_balance(user_id, guild_id)
        last_daily_str = data['last_daily']
        current_time = datetime.datetime.now()
        if last_daily_str:
            last_daily_time = datetime.datetime.fromisoformat(last_daily_str)
            cooldown_delta = datetime.timedelta(hours=DAILY_COOLDOWN)
            if (current_time - last_daily_time) < cooldown_delta:
                tiempo_restante = (last_daily_time + cooldown_delta) - current_time
                horas, rem = divmod(tiempo_restante.seconds, 3600)
                minutos, _ = divmod(rem, 60)
                await interaction.response.send_message(f"¡Calma, vaquero! 🤠 Aún debes esperar **{horas}h {minutos}m**.", ephemeral=True)
                return
        new_balance = data['balance'] + DAILY_AMOUNT
        db = sqlite3.connect('data/economy.db')
        cursor = db.cursor()
        cursor.execute("UPDATE balances SET balance = ?, last_daily = ? WHERE user_id = ? AND guild_id = ?", (new_balance, current_time.isoformat(), user_id, guild_id))
        db.commit()
        db.close()
        embed = discord.Embed(title="¡Día de Paga! 💸", description=f"¡Has recibido **{DAILY_AMOUNT}** Nocoins 🪙!", color=discord.Color.green())
        embed.add_field(name="Nuevo Saldo:", value=f"**{new_balance}** Nocoins 🪙")
        embed.set_footer(text=f"¡Vuelve en {DAILY_COOLDOWN} horas!")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pagar", description="Paga Nocoins 🪙 a otro miembro.")
    @app_commands.describe(receptor="El miembro al que quieres pagar.", cantidad="La cantidad de Nocoins a pagar.")
    async def pagar(self, interaction: discord.Interaction, receptor: discord.Member, cantidad: app_commands.Range[int, 1, None]):
        # ... (código igual)
        emisor_id = interaction.user.id
        receptor_id = receptor.id
        guild_id = interaction.guild.id
        if emisor_id == receptor_id or receptor.bot:
            await interaction.response.send_message("No puedes pagarte a ti mismo o a un bot.", ephemeral=True)
            return
        emisor_data = await self.get_or_create_balance(emisor_id, guild_id)
        if emisor_data['balance'] < cantidad:
            await interaction.response.send_message(f"No tienes fondos. Tu saldo es de **{emisor_data['balance']}** 🪙.", ephemeral=True)
            return
        receptor_data = await self.get_or_create_balance(receptor_id, guild_id)
        nuevo_saldo_emisor = emisor_data['balance'] - cantidad
        nuevo_saldo_receptor = receptor_data['balance'] + cantidad
        db = sqlite3.connect('data/economy.db')
        cursor = db.cursor()
        cursor.execute("UPDATE balances SET balance = ? WHERE user_id = ? AND guild_id = ?", (nuevo_saldo_emisor, emisor_id, guild_id))
        cursor.execute("UPDATE balances SET balance = ? WHERE user_id = ? AND guild_id = ?", (nuevo_saldo_receptor, receptor_id, guild_id))
        db.commit()
        db.close()
        await interaction.response.send_message(f"✅ ¡Transferencia completada! Has enviado **{cantidad}** Nocoins 🪙 a {receptor.mention}.", ephemeral=True)

    @app_commands.command(name="leaderboard", description="Muestra el top 10 de usuarios más ricos del servidor.")
    async def leaderboard(self, interaction: discord.Interaction):
        # ... (código igual)
        await interaction.response.defer()
        db = sqlite3.connect('data/economy.db')
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        cursor.execute("SELECT user_id, balance FROM balances WHERE guild_id = ? AND balance > 0 ORDER BY balance DESC LIMIT 10", (interaction.guild.id,))
        results = cursor.fetchall()
        db.close()
        embed = discord.Embed(title="🏆 Top 10 Ricos del Servidor 🏆", color=discord.Color.gold(), timestamp=datetime.datetime.now())
        embed.set_footer(text="¿Podrás entrar en el top?")
        if not results:
            embed.description = "Nadie tiene Nocoins todavía... ¡Usa `/daily` para empezar!"
            await interaction.followup.send(embed=embed)
            return
        description_list = ""
        medallas = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(results):
            try:
                user = await self.bot.fetch_user(row['user_id'])
                user_name = user.name
            except discord.NotFound:
                user_name = "Usuario Desconocido"
            rank_str = medallas[i] if i < len(medallas) else f"**#{i+1}**"
            description_list += f"{rank_str} {user_name} - **{row['balance']}** 🪙\n"
        embed.description = description_list
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="apostar", description="Apuesta Nocoins a un cara o cruz. ¡Doble o nada!")
    @app_commands.describe(cantidad="La cantidad de Nocoins que quieres apostar.", eleccion="Tu elección: ¿cara o cruz?")
    @app_commands.choices(eleccion=[app_commands.Choice(name="Cara", value="cara"), app_commands.Choice(name="Cruz", value="cruz"),])
    async def apostar(self, interaction: discord.Interaction, cantidad: app_commands.Range[int, 1, None], eleccion: app_commands.Choice[str]):
        # ... (código igual)
        await interaction.response.defer()
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        data = await self.get_or_create_balance(user_id, guild_id)
        if data['balance'] < cantidad:
            await interaction.followup.send(f"¡No puedes apostar tanto! Solo tienes **{data['balance']}** 🪙.", ephemeral=True)
            return
        resultado = random.choice(["cara", "cruz"])
        if eleccion.value == resultado:
            nuevo_saldo = data['balance'] + cantidad
            titulo, descripcion, color = "¡Has Ganado! 💸", f"¡Salió **{resultado.upper()}**! Has ganado **{cantidad}** 🪙.", discord.Color.green()
        else:
            nuevo_saldo = data['balance'] - cantidad
            titulo, descripcion, color = "¡Has Perdido! 😢", f"¡Salió **{resultado.upper()}**! Has perdido **{cantidad}** 🪙.", discord.Color.red()
        db = sqlite3.connect('data/economy.db')
        cursor = db.cursor()
        cursor.execute("UPDATE balances SET balance = ? WHERE user_id = ? AND guild_id = ?", (nuevo_saldo, user_id, guild_id))
        db.commit()
        db.close()
        embed = discord.Embed(title=titulo, description=descripcion, color=color)
        embed.set_footer(text=f"Tu nuevo saldo: {nuevo_saldo} 🪙")
        await interaction.followup.send(embed=embed)

    # -----------------------------------------------------------------
    # --- ¡NUEVO! Comandos de Tienda (Admin) ---
    # -----------------------------------------------------------------
    
    @app_commands.command(name="additem", description="[MOD] Añade un rol cosmético a la tienda.")
    @app_commands.describe(nombre="El nombre del item.", precio="El precio en Nocoins.", rol="El rol que se dará al comprar.")
    @is_moderator()
    async def additem(self, interaction: discord.Interaction, nombre: str, precio: app_commands.Range[int, 1, None], rol: discord.Role):
        
        # Comprobación de Jerarquía (¡MUY IMPORTANTE!)
        if interaction.guild.me.top_role <= rol:
            await interaction.response.send_message(
                f"Error: No puedo asignar el rol {rol.mention}. Mi rol debe estar por encima de él en la lista de roles.",
                ephemeral=True
            )
            return
            
        try:
            db = sqlite3.connect('data/economy.db')
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO shop_items (guild_id, name, description, price, role_id) VALUES (?, ?, ?, ?, ?)",
                (interaction.guild.id, nombre, f"Compra el rol {rol.name}", precio, rol.id)
            )
            db.commit()
            db.close()
        except sqlite3.IntegrityError:
            await interaction.response.send_message("Error: Ese rol ya está en la tienda.", ephemeral=True)
            return
        except Exception as e:
            await interaction.response.send_message(f"Error de base de datos: {e}", ephemeral=True)
            return
            
        await interaction.response.send_message(
            f"✅ ¡Item añadido! **{nombre}** ({rol.mention}) ha sido añadido a la tienda por **{precio}** 🪙.",
            ephemeral=True
        )

    @app_commands.command(name="delitem", description="[MOD] Elimina un item de la tienda por su ID de Rol.")
    @app_commands.describe(rol="El rol que quieres eliminar de la tienda.")
    @is_moderator()
    async def delitem(self, interaction: discord.Interaction, rol: discord.Role):
        try:
            db = sqlite3.connect('data/economy.db')
            cursor = db.cursor()
            cursor.execute("DELETE FROM shop_items WHERE role_id = ? AND guild_id = ?", (rol.id, interaction.guild.id))
            db.commit()
            
            if cursor.rowcount == 0:
                await interaction.response.send_message("Error: Ese rol no se encontraba en la tienda.", ephemeral=True)
            else:
                await interaction.response.send_message(f"✅ ¡Item eliminado! El rol {rol.name} ya no está en la tienda.", ephemeral=True)
            db.close()
        except Exception as e:
            await interaction.response.send_message(f"Error de base de datos: {e}", ephemeral=True)
            return

    # -----------------------------------------------------------------
    # --- ¡NUEVO! Comandos de Tienda (Usuario) ---
    # -----------------------------------------------------------------
    
    @app_commands.command(name="tienda", description="Muestra los roles que puedes comprar con Nocoins 🪙.")
    async def tienda(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        db = sqlite3.connect('data/economy.db')
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        cursor.execute("SELECT id, name, price, role_id FROM shop_items WHERE guild_id = ? ORDER BY price ASC", (interaction.guild.id,))
        items = cursor.fetchall()
        db.close()
        
        embed = discord.Embed(title="🛒 Tienda de Roles Cosméticos 🛒", color=discord.Color.blue())
        
        if not items:
            embed.description = "La tienda está vacía. ¡Avisa a un admin para que añada roles!"
        else:
            embed.description = "Usa `/comprar [ID]` para obtener un rol.\n\n"
            for item in items:
                # Buscamos el rol para mostrarlo
                role = interaction.guild.get_role(item['role_id'])
                if role:
                    embed.add_field(
                        name=f"{item['name']} - {role.mention}",
                        value=f"**Precio:** {item['price']} 🪙\n**ID:** `{item['id']}`",
                        inline=False
                    )
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="comprar", description="Compra un rol de la tienda.")
    @app_commands.describe(id_item="El ID del item que quieres comprar (lo ves en /tienda).")
    async def comprar(self, interaction: discord.Interaction, id_item: int):
        await interaction.response.defer(ephemeral=True)
        
        # 1. Buscar el item en la tienda
        db = sqlite3.connect('data/economy.db')
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        cursor.execute("SELECT * FROM shop_items WHERE id = ? AND guild_id = ?", (id_item, interaction.guild.id))
        item = cursor.fetchone()
        
        if not item:
            await interaction.followup.send("Error: No se encontró ningún item con ese ID.", ephemeral=True)
            db.close()
            return
            
        item_price = item['price']
        item_role_id = item['role_id']
        
        # 2. Buscar el rol en Discord
        role = interaction.guild.get_role(item_role_id)
        if not role:
            await interaction.followup.send("Error: El rol asociado a este item ya no existe. Avisa a un admin.", ephemeral=True)
            db.close()
            return
            
        # 3. Comprobar si el usuario ya lo tiene
        if role in interaction.user.roles:
            await interaction.followup.send("¡Ya tienes este rol!", ephemeral=True)
            db.close()
            return

        # 4. Comprobar fondos
        user_data = await self.get_or_create_balance(interaction.user.id, interaction.guild.id)
        if user_data['balance'] < item_price:
            await interaction.followup.send(f"¡No tienes fondos! Necesitas **{item_price}** 🪙 pero solo tienes **{user_data['balance']}** 🪙.", ephemeral=True)
            db.close()
            return
            
        # 5. ¡¡PROCEDER CON LA COMPRA!!
        try:
            # 5a. Quitar dinero
            nuevo_saldo = user_data['balance'] - item_price
            cursor.execute("UPDATE balances SET balance = ? WHERE user_id = ? AND guild_id = ?",
                           (nuevo_saldo, interaction.user.id, interaction.guild.id))
            db.commit()
            
            # 5b. Dar el rol
            await interaction.user.add_roles(role, reason=f"Comprado en la tienda por {item_price} Nocoins")
            
        except discord.Forbidden:
            # ¡Error de jerarquía!
            await interaction.followup.send("Error: No puedo asignar este rol. Asegúrate de que mi rol esté por encima del rol de la tienda.", ephemeral=True)
            db.rollback() # DESHACER la compra si no se pudo dar el rol
            db.close()
            return
        except Exception as e:
            await interaction.followup.send(f"Error de transacción: {e}", ephemeral=True)
            db.rollback()
            db.close()
            return
            
        db.close()
        
        # 6. Confirmación
        await interaction.followup.send(f"¡Felicidades! Has comprado el rol {role.mention} por **{item_price}** 🪙.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))