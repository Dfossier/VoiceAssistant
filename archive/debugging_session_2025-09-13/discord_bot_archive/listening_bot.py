#!/usr/bin/env python3
"""
WSL2 Discord Bot with Real Voice Recording using py-cord features
"""

import asyncio
import discord
import discord.opus
import logging
import sys
import os
import tempfile
import wave
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from backend_client import BackendClient
from config import Config
from clean_logger import setup_clean_logging

# Setup clean logging
setup_clean_logging()
logger = logging.getLogger(__name__)

# Suppress Discord logs
for logger_name in ['discord', 'discord.gateway', 'discord.client', 'discord.voice_client']:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# Force load Opus
logger.info("[SETUP] Loading Opus library...")
try:
    discord.opus._load_default()
    opus_status = "[OK] Loaded" if discord.opus.is_loaded() else "[ERROR] Failed"
    logger.info(f"Opus status: {opus_status}")
except Exception as e:
    logger.error(f"[ERROR] Opus error: {e}")

class VoiceRecorder:
    """Records and processes user voice"""
    
    def __init__(self, bot, guild_id: int, backend_client: BackendClient):
        self.bot = bot
        self.guild_id = guild_id
        self.backend_client = backend_client
        self.user_recordings = {}  # user_id -> audio_data
        self.is_active = True
        
    def process_voice_data(self, user, voice_data):
        """Process voice data from a user"""
        if not user or user.bot or not voice_data:
            return
            
        user_id = user.id
        user_name = user.display_name
        
        # Initialize user recording buffer
        if user_id not in self.user_recordings:
            self.user_recordings[user_id] = {
                'name': user_name,
                'audio_chunks': []
            }
        
        # Add voice data
        self.user_recordings[user_id]['audio_chunks'].append(voice_data)
        
        # If we have enough data (about 3 seconds), process it
        if len(self.user_recordings[user_id]['audio_chunks']) >= 150:  # ~3 seconds at 20ms chunks
            asyncio.create_task(self.process_user_speech(user_id))
    
    async def process_user_speech(self, user_id: int):
        """Process accumulated speech from a user"""
        if user_id not in self.user_recordings:
            return
            
        user_data = self.user_recordings[user_id]
        user_name = user_data['name']
        chunks = user_data['audio_chunks']
        
        # Clear the buffer
        self.user_recordings[user_id]['audio_chunks'] = []
        
        if len(chunks) < 50:  # Too short
            return
            
        logger.info(f"[VOICE] Processing {len(chunks)} chunks from {user_name}")
        
        try:
            # Convert chunks to audio file
            audio_data = self.create_audio_file(chunks)
            if audio_data:
                # Send to backend for processing
                await self.handle_voice_message(audio_data, user_name)
        except Exception as e:
            logger.error(f"[ERROR] Failed to process speech from {user_name}: {e}")
    
    def create_audio_file(self, chunks) -> Optional[bytes]:
        """Create WAV file from voice chunks"""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Discord audio: 48kHz, 2 channels, 16-bit
            with wave.open(temp_path, 'wb') as wav_file:
                wav_file.setnchannels(2)
                wav_file.setsampwidth(2)
                wav_file.setframerate(48000)
                
                for chunk in chunks:
                    wav_file.writeframes(chunk)
            
            # Read back the audio data
            with open(temp_path, 'rb') as f:
                audio_data = f.read()
            
            os.unlink(temp_path)  # Clean up
            
            logger.info(f"[AUDIO] Created {len(audio_data)} byte audio file")
            return audio_data
            
        except Exception as e:
            logger.error(f"[ERROR] Audio file creation failed: {e}")
            return None
    
    async def handle_voice_message(self, audio_data: bytes, user_name: str):
        """Handle complete voice message"""
        try:
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                return
                
            # Find text channel to send updates
            channel = guild.system_channel or next(
                (ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), 
                None
            )
            
            if channel:
                # Send confirmation that we heard them
                embed = discord.Embed(
                    title="Voice Message Received!",
                    description=f"Processing {len(audio_data)} bytes of audio from **{user_name}**",
                    color=0x00ff00
                )
                msg = await channel.send(embed=embed)
            
            # Transcribe through backend
            logger.info(f"[TRANSCRIBE] Sending {len(audio_data)} bytes to backend...")
            text = await self.backend_client.transcribe_audio(audio_data)
            
            if text and text.strip():
                logger.info(f"[TEXT] Transcribed: '{text}'")
                
                if channel:
                    await msg.edit(embed=discord.Embed(
                        title="Voice Transcribed!",
                        description=f"**{user_name}** said: '{text}'",
                        color=0x0099ff
                    ))
                
                # Get AI response
                response = await self.backend_client.send_message(
                    user_id=user_name,
                    message=text,
                    context={"source": "voice", "guild_id": str(self.guild_id)}
                )
                
                if response:
                    logger.info(f"[AI] Response: {response[:100]}...")
                    
                    # Send text response
                    if channel:
                        embed = discord.Embed(
                            title="AI Response",
                            color=0x00ff00
                        )
                        embed.add_field(name=f"You said:", value=text, inline=False)
                        embed.add_field(name="AI replied:", value=response, inline=False)
                        await channel.send(embed=embed)
                    
                    # Convert to speech and play
                    audio_response = await self.backend_client.text_to_speech(response)
                    if audio_response and self.guild_id in self.bot.my_voice_clients:
                        await self.play_response(audio_response)
            else:
                logger.warning("[WARN] No transcription received")
                if channel:
                    await msg.edit(embed=discord.Embed(
                        title="No Speech Detected",
                        description=f"Could not transcribe audio from **{user_name}**",
                        color=0xff9900
                    ))
        
        except Exception as e:
            logger.error(f"[ERROR] Voice message handling failed: {e}")
    
    async def play_response(self, audio_data: bytes):
        """Play AI response in voice channel"""
        try:
            voice_client = self.bot.my_voice_clients.get(self.guild_id)
            if not voice_client or not voice_client.is_connected():
                return
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                audio_source = discord.FFmpegPCMAudio(temp_path, options='-loglevel error')
                voice_client.play(audio_source)
                
                while voice_client.is_playing():
                    await asyncio.sleep(0.1)
                    
                logger.info("[AUDIO] Response played successfully")
            finally:
                await asyncio.sleep(0.5)
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"[ERROR] Response playback failed: {e}")

# Custom callback for voice data
def voice_callback(user, voice_data):
    """Global callback for voice data"""
    if hasattr(voice_callback, 'recorder') and voice_callback.recorder:
        voice_callback.recorder.process_voice_data(user, voice_data)

class ListeningBot(discord.Client):
    """Discord bot that actually listens to voice"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.my_voice_clients = {}
        self.backend_client = None
        self.voice_recorders = {}
    
    async def on_ready(self):
        """Bot ready"""
        logger.info(f"[BOT] {self.user} connected to Discord!")
        logger.info(f"[INFO] Bot in {len(self.guilds)} guilds")
        
        # Initialize backend
        try:
            self.backend_client = BackendClient(
                base_url=Config.BACKEND_API_URL,
                api_key=Config.BACKEND_API_KEY
            )
            
            if await self.backend_client.health_check():
                logger.info("[OK] Backend API connected")
            else:
                logger.warning("[WARN] Backend not available")
                
        except Exception as e:
            logger.error(f"[ERROR] Backend error: {e}")
        
        # Show status
        opus_status = "[OK]" if discord.opus.is_loaded() else "[ERROR]"
        backend_status = "[OK]" if self.backend_client else "[ERROR]"
        logger.info(f"[STATUS] Components: Opus: {opus_status} | Backend: {backend_status}")
    
    async def on_message(self, message):
        """Handle messages"""
        if message.author == self.user:
            return
        
        content = message.content.lower().strip()
        
        if content == '!listen':
            await self._start_listening(message)
        elif content == '!stop':
            await self._stop_listening(message)
        elif content.startswith('!speak '):
            await self._speak_text(message, content[7:])
        elif content.startswith('!ask '):
            await self._ask_question(message, content[5:])
        elif content == '!status':
            await self._show_status(message)
        elif content == '!help':
            await self._show_help(message)
    
    async def _start_listening(self, message):
        """Start real voice listening"""
        if not message.author.voice:
            await message.reply("Join a voice channel first!")
            return
        
        if not self.backend_client:
            await message.reply("Backend not connected!")
            return
        
        channel = message.author.voice.channel
        guild_id = message.guild.id
        
        try:
            # Disconnect if already connected
            if guild_id in self.my_voice_clients:
                await self.my_voice_clients[guild_id].disconnect()
                del self.my_voice_clients[guild_id]
            
            # Stop existing recorder
            if guild_id in self.voice_recorders:
                self.voice_recorders[guild_id].is_active = False
                del self.voice_recorders[guild_id]
            
            # Connect to voice
            voice_client = await channel.connect(timeout=20.0)
            self.my_voice_clients[guild_id] = voice_client
            
            # Create voice recorder
            recorder = VoiceRecorder(self, guild_id, self.backend_client)
            self.voice_recorders[guild_id] = recorder
            
            # Set global callback
            voice_callback.recorder = recorder
            
            # Try to start recording (this might not work in all Discord.py versions)
            try:
                voice_client.listen(discord.CallbackSink(voice_callback))
                logger.info("[RECORDING] Started voice recording")
            except AttributeError:
                logger.warning("[WARN] Voice recording not available in this Discord.py version")
            
            embed = discord.Embed(
                title="Voice Listening Active!",
                description=f"Connected to **{channel.name}** and listening for your voice!",
                color=0x00ff00
            )
            embed.add_field(
                name="What to Do",
                value="• **Speak into your microphone**\n• Bot will transcribe your speech\n• AI will respond with voice + text",
                inline=False
            )
            embed.add_field(
                name="Test Commands",
                value="`!speak <text>` - Test TTS\n`!ask <question>` - Text chat\n`!stop` - Stop listening",
                inline=False
            )
            
            await message.reply(embed=embed)
            logger.info(f"[OK] Voice listening started in {channel.name}")
            
        except Exception as e:
            await message.reply(f"Failed to start listening: {str(e)}")
            logger.error(f"[ERROR] Listen error: {e}")
    
    async def _stop_listening(self, message):
        """Stop listening"""
        guild_id = message.guild.id
        
        try:
            # Stop recorder
            if guild_id in self.voice_recorders:
                self.voice_recorders[guild_id].is_active = False
                del self.voice_recorders[guild_id]
            
            # Disconnect voice
            if guild_id in self.my_voice_clients:
                await self.my_voice_clients[guild_id].disconnect()
                del self.my_voice_clients[guild_id]
            
            await message.reply("Stopped listening and disconnected from voice!")
            logger.info("[STOP] Voice listening stopped")
            
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _speak_text(self, message, text: str):
        """Speak text"""
        guild_id = message.guild.id
        
        if guild_id not in self.my_voice_clients:
            await message.reply("Not listening! Use `!listen` first.")
            return
        
        if not text.strip():
            await message.reply("Provide text to speak!")
            return
        
        try:
            await message.reply(f"Speaking: *{text[:100]}...*")
            
            if self.backend_client:
                audio_data = await self.backend_client.text_to_speech(text)
                if audio_data and guild_id in self.voice_recorders:
                    await self.voice_recorders[guild_id].play_response(audio_data)
            else:
                await message.reply("Backend not available")
                
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _ask_question(self, message, question: str):
        """Ask AI a question"""
        if not self.backend_client:
            await message.reply("Backend not connected!")
            return
        
        if not question.strip():
            await message.reply("Ask a question!")
            return
        
        try:
            response = await self.backend_client.send_message(
                user_id=str(message.author.id),
                message=question,
                context={"source": "text", "guild_id": str(message.guild.id)}
            )
            
            if len(response) > 1500:
                response = response[:1500] + "..."
            
            await message.reply(response)
            
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _show_status(self, message):
        """Show status"""
        embed = discord.Embed(title="Voice Listening Bot Status", color=0x0099ff)
        
        opus_status = "OK" if discord.opus.is_loaded() else "ERROR"
        backend_status = "OK" if self.backend_client else "ERROR"
        
        embed.add_field(
            name="Components",
            value=f"Opus: {opus_status}\nBackend: {backend_status}",
            inline=True
        )
        
        embed.add_field(
            name="Voice Status",
            value=f"Connected: {len(self.my_voice_clients)}\nListening: {len(self.voice_recorders)}",
            inline=True
        )
        
        await message.reply(embed=embed)
    
    async def _show_help(self, message):
        """Show help"""
        embed = discord.Embed(
            title="Voice Listening Bot",
            description="Real voice input with transcription and AI response",
            color=0x0099ff
        )
        
        embed.add_field(
            name="Voice Commands",
            value="`!listen` - Start listening to your voice\n"
                  "`!stop` - Stop listening\n"
                  "`!speak <text>` - Test TTS output",
            inline=False
        )
        
        embed.add_field(
            name="Chat Commands",
            value="`!ask <question>` - Text chat with AI\n"
                  "`!status` - Show system status\n"
                  "`!help` - Show this help",
            inline=False
        )
        
        embed.add_field(
            name="How It Works",
            value="1. Use `!listen` in a voice channel\n"
                  "2. **Speak into your microphone**\n"
                  "3. Bot transcribes with Parakeet\n"
                  "4. AI responds with Phi-3\n"
                  "5. Bot speaks back with Kokoro",
            inline=False
        )
        
        await message.reply(embed=embed)

def main():
    """Main entry point"""
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"[ERROR] Configuration error: {e}")
        sys.exit(1)
    
    bot = ListeningBot()
    
    try:
        logger.info("[START] Starting Voice Listening Bot...")
        logger.info("[INFO] This bot can actually hear and respond to your voice!")
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("[BYE] Bot stopped")
    except Exception as e:
        logger.error(f"[CRASH] Fatal error: {e}")

if __name__ == "__main__":
    main()