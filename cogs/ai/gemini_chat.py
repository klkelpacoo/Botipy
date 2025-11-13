# cogs/ai/gemini_chat.py
import os
import discord
from discord.ext import commands
from discord import app_commands
from google import genai
from google.genai import types
import asyncio
import io               # ¡NUEVO! Para manejar bytes de imagen
from PIL import Image   # ¡NUEVO! Para procesar la imagen

# --- Cargar la API Key ---
try:
    GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("GOOGLE_GEMINI_API_KEY no encontrada en el .env")
    
    # --- Configuración del Cliente v10 ---
    GOOGLE_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
    
    # --- Nombre del Modelo ---
    MODEL_NAME = "gemini-2.5-flash"
    
    # --- Configuración de Seguridad ---
    GENERATION_CONFIG = types.GenerateContentConfig(
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
    )
    
    print(f"[DEBUG AI] Cliente de Google GenAI (v10) cargado. Modelo: {MODEL_NAME}")
    
except Exception as e:
    print(f"Error CRÍTICO al cargar el Cog de Gemini: {e}")
    print("El comando /ia NO funcionará. Revisa tu API Key y el .env.")
    GOOGLE_CLIENT = None

# -----------------------------------------------------------------
# --- Clase del Cog: El Cerebro del Bot ---
# -----------------------------------------------------------------
class GeminiChat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # { user_id: chat_session }
        self.chats = {}

    async def send_long_message(self, interaction: discord.Interaction, text: str):
        """Envía mensajes largos (más de 2000 caracteres) en trozos."""
        chunks = [text[i:i+1990] for i in range(0, len(text), 1990)]
        
        if chunks:
            await interaction.followup.send(f"```{chunks[0]}```")
            for chunk in chunks[1:]:
                await interaction.channel.send(f"```{chunk}```") 
        else:
            await interaction.followup.send("La IA no ha generado respuesta.")

    @app_commands.command(
        name="ia",
        description="Habla con la IA (Gemini). ¡Incluso puedes adjuntar una imagen!"
    )
    @app_commands.describe(
        pregunta="¿Qué quieres preguntarme?",
        imagen="[OPCIONAL] Adjunta una imagen para que la analice."
    )
    async def ia(self, interaction: discord.Interaction, pregunta: str, imagen: discord.Attachment = None):
        """Maneja una conversación de chat con historial, ahora multimodal."""
        
        if not GOOGLE_CLIENT:
            await interaction.response.send_message("Error: El módulo de IA no está configurado. Avisa a un admin.", ephemeral=True)
            return

        await interaction.response.defer()
        
        user_id = interaction.user.id
        
        # --- ¡NUEVA Lógica Multimodal (v10)! ---
        
        # 1. Preparar las "partes" del mensaje
        parts_list = [pregunta] # El texto siempre va
        
        # 2. Procesar la imagen (si existe)
        if imagen:
            # Comprobar si es una imagen (¡fiabilidad!)
            if not imagen.content_type or not imagen.content_type.startswith("image/"):
                await interaction.followup.send("Error: El archivo adjunto no es una imagen.", ephemeral=True)
                return
                
            try:
                # Descargar la imagen en memoria
                image_bytes = await imagen.read()
                # Abrirla con Pillow
                img = Image.open(io.BytesIO(image_bytes))
                
                # ¡Añadimos la imagen a nuestra lista de partes!
                parts_list.append(img)
                
            except Exception as e:
                print(f"Error al procesar la imagen: {e}")
                await interaction.followup.send("Error: No pude procesar la imagen adjunta.", ephemeral=True)
                return

        # 3. Obtener la sesión de chat
        if user_id not in self.chats:
            self.chats[user_id] = GOOGLE_CLIENT.chats.create(
                model=MODEL_NAME,
                history=[],
                config=GENERATION_CONFIG 
            )
            
        chat_session = self.chats[user_id]
        
        try:
            # 4. Enviar el mensaje (¡que ahora es una lista de partes!)
            def send_message_sync():
                # ¡Enviamos la lista! [pregunta, img]
                return chat_session.send_message(parts_list) 

            response = await asyncio.to_thread(send_message_sync)
            
            # 5. Enviar la respuesta
            await self.send_long_message(interaction, response.text)

        except Exception as e:
            print(f"Error en /ia (Gemini v10): {e}")
            self.chats.pop(user_id, None) # Reiniciar historial en error
            await interaction.followup.send(
                "Lo siento, ocurrió un error y no puedo generar una respuesta. 😥\n"
                "(Puede haber sido bloqueado por seguridad o la API falló. Tu historial de chat se ha reiniciado).",
                ephemeral=True
            )

    @app_commands.command(
        name="ia_reset",
        description="Reinicia tu historial de conversación con la IA."
    )
    async def ia_reset(self, interaction: discord.Interaction):
        """Borra el historial de chat de un usuario."""
        user_id = interaction.user.id
        
        self.chats.pop(user_id, None) 
            
        await interaction.response.send_message(
            "¡Memoria reiniciada! 🧠 La IA ha olvidado vuestra conversación anterior.",
            ephemeral=True
        )

# --- Función Setup ---
async def setup(bot: commands.Bot):
    if GOOGLE_CLIENT:
        await bot.add_cog(GeminiChat(bot))
    else:
        print("El Cog 'GeminiChat' NO se cargará debido a un error de configuración.")