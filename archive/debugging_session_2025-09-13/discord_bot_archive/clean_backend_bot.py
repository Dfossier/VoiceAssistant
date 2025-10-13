#!/usr/bin/env python3
"""
WSL2 Discord Bot using Backend API - Clean Version (No Emojis)
Parakeet ASR, Phi-3/Kokoro through backend server
"""

import asyncio
import discord
import discord.opus
import logging
import sys
import os
import tempfile
import base64
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from backend_client import BackendClient
from config import Config
from clean_logger import setup_clean_logging, clean_emojis

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

class BackendVoiceHandler:
    """Voice handler using backend API for all processing"""
    
    def __init__(self, bot, guild_id: int, backend_client: BackendClient):
        self.bot = bot
        self.guild_id = guild_id
        self.backend_client = backend_client
        self.recording = False
        self.voice_client = None
        
        logger.info(f"[OK] Backend voice handler initialized for guild {guild_id}")
    
    async def start_listening(self, voice_client):
        """Start voice processing"""
        self.voice_client = voice_client
        self.recording = True
        logger.info("[VOICE] Voice pipeline started (backend mode)")
        
        # Start recording task
        self.record_task = asyncio.create_task(self._record_loop())
    
    async def stop_listening(self):
        """Stop voice processing"""
        self.recording = False
        if hasattr(self, 'record_task'):
            self.record_task.cancel()
            try:
                await self.record_task
            except asyncio.CancelledError:
                pass
        logger.info("[MUTE] Voice pipeline stopped")
    
    async def _record_loop(self):
        """Recording loop - simplified for testing"""
        try:
            logger.info("[VOICE] Backend voice recording active")
            
            # For testing, we'll use periodic checks
            # In production, this would capture actual audio from Discord
            while self.recording:
                await asyncio.sleep(3)
                # Real implementation would process captured audio here
                
        except Exception as e:
            logger.error(f"[ERROR] Recording loop error: {e}")
    
    async def process_audio(self, audio_data: bytes, user_name: str):
        """Process audio through backend"""
        try:
            if not audio_data or len(audio_data) < 1000:
                return
            
            logger.info(f"[VOICE] Processing {len(audio_data)} bytes from {user_name}")
            
            # Transcribe through backend
            text = await self.backend_client.transcribe_audio(audio_data)
            if not text or text.strip() == "":
                logger.warning("[WARN] Empty transcription")
                return
            
            logger.info(f"[TEXT] Transcribed: {text}")
            
            # Get AI response through backend
            response = await self.backend_client.send_message(
                user_id=user_name,
                message=text,
                context={"source": "voice", "guild_id": str(self.guild_id)}
            )
            
            if not response:
                logger.warning("[WARN] Empty AI response")
                return
            
            logger.info(f"[BOT] AI Response: {response[:100]}...")
            
            # Convert to speech through backend
            audio_response = await self.backend_client.text_to_speech(response)
            if audio_response:
                await self.play_audio(audio_response)
            
            # Send text response to channel
            guild = self.bot.get_guild(self.guild_id)
            if guild:
                # Find a text channel to send to
                channel = guild.system_channel or next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
                if channel:
                    embed = discord.Embed(
                        title="Voice Conversation",
                        color=0x00ff00
                    )
                    embed.add_field(name=f"User: {user_name}", value=text, inline=False)
                    embed.add_field(name="Assistant", value=response, inline=False)
                    await channel.send(embed=embed)
                    
        except Exception as e:
            logger.error(f"[ERROR] Audio processing error: {e}")
    
    async def speak_text(self, text: str):
        """Convert text to speech and play"""
        try:
            if not self.voice_client or not self.voice_client.is_connected():
                logger.warning("[WARN] No voice connection")
                return False
            
            # Get TTS from backend
            logger.info(f"[SPEAK] Generating speech: {text[:50]}...")
            audio_data = await self.backend_client.text_to_speech(text)
            
            if not audio_data:
                logger.warning("[WARN] No audio generated")
                return False
            
            logger.info(f"[OK] Generated {len(audio_data)} bytes of audio")
            
            # Play the audio
            success = await self.play_audio(audio_data)
            return success
            
        except Exception as e:
            logger.error(f"[ERROR] TTS error: {e}")
            return False
    
    async def play_audio(self, audio_data: bytes) -> bool:
        """Play audio through Discord voice"""
        try:
            if not self.voice_client or not self.voice_client.is_connected():
                return False
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                # Convert MP3 to Discord-compatible format with FFmpeg
                audio_source = discord.FFmpegPCMAudio(
                    temp_path,
                    options='-loglevel error'
                )
                
                # Play audio
                self.voice_client.play(audio_source)
                
                # Wait for playback
                while self.voice_client.is_playing():
                    await asyncio.sleep(0.1)
                
                logger.info("[OK] Audio playback complete")
                return True
                
            finally:
                # Clean up
                await asyncio.sleep(0.5)  # Small delay before deletion
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"[ERROR] Audio playback error: {e}")
            return False

class BackendDiscordBot(discord.Client):
    """Discord bot using backend API for all AI operations"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.voice_handlers: Dict[int, BackendVoiceHandler] = {}
        self.backend_client = None
    
    async def on_ready(self):
        """Bot ready event"""
        logger.info(f"[BOT] {self.user} connected to Discord!")
        logger.info(f"[INFO] Bot in {len(self.guilds)} guilds")
        
        # Initialize backend client
        try:
            self.backend_client = BackendClient(
                base_url=Config.BACKEND_API_URL,
                api_key=Config.BACKEND_API_KEY
            )
            
            # Test backend connection
            if await self.backend_client.health_check():
                logger.info("[OK] Backend API connected")
                
                # Test API status
                status = await self.backend_client.get_api_status()
                logger.info(f"[INFO] Backend status: {status}")
            else:
                logger.warning("[WARN] Backend health check failed")
                
        except Exception as e:
            logger.error(f"[ERROR] Backend initialization error: {e}")
            self.backend_client = None
        
        # Show component status
        opus_status = "[OK]" if discord.opus.is_loaded() else "[ERROR]"
        backend_status = "[OK]" if self.backend_client else "[ERROR]"
        
        logger.info(f"[STATUS] Components: Opus: {opus_status} | Backend: {backend_status}")
    
    async def on_message(self, message):
        """Handle messages"""
        if message.author == self.user:
            return
        
        content = message.content.lower().strip()
        
        if content == '!join':
            await self._join_voice(message)
        elif content == '!leave':
            await self._leave_voice(message)
        elif content.startswith('!speak '):
            await self._speak_text(message, content[7:])
        elif content.startswith('!ask '):
            await self._ask_question(message, content[5:])
        elif content == '!status':
            await self._show_status(message)
        elif content == '!models':
            await self._show_models(message)
        elif content == '!help':
            await self._show_help(message)
    
    async def _join_voice(self, message):
        """Join voice channel"""
        if not message.author.voice:
            await message.reply("You need to be in a voice channel!")
            return
        
        if not self.backend_client:
            await message.reply("Backend API not connected!")
            return
        
        channel = message.author.voice.channel
        guild_id = message.guild.id
        
        try:
            # Disconnect if already connected
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect(force=True)
                await asyncio.sleep(1)
            
            # Connect
            voice_client = await channel.connect(timeout=20.0, reconnect=False)
            await asyncio.sleep(1)
            
            if voice_client and voice_client.is_connected():
                # Initialize handler
                handler = BackendVoiceHandler(self, guild_id, self.backend_client)
                self.voice_handlers[guild_id] = handler
                await handler.start_listening(voice_client)
                
                embed = discord.Embed(
                    title="Backend Voice Bot Connected",
                    description=f"Connected to **{channel.name}** with backend AI models!",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Backend Models",
                    value="• **ASR**: Parakeet (local)\n• **LLM**: Phi-3 (local)\n• **TTS**: Kokoro (local)",
                    inline=False
                )
                embed.add_field(
                    name="Features",
                    value="• Voice processing through backend\n• Local model inference\n• Low latency responses",
                    inline=False
                )
                
                await message.reply(embed=embed)
                logger.info(f"[OK] Connected to {channel.name} with backend")
            else:
                raise Exception("Connection failed")
                
        except Exception as e:
            await message.reply(f"Failed to join: {str(e)}")
            logger.error(f"[ERROR] Join error: {e}")
    
    async def _leave_voice(self, message):
        """Leave voice channel"""
        guild_id = message.guild.id
        
        try:
            if guild_id in self.voice_handlers:
                await self.voice_handlers[guild_id].stop_listening()
                del self.voice_handlers[guild_id]
            
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect(force=True)
                await message.reply("Left voice channel!")
            else:
                await message.reply("Not in voice!")
                
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _speak_text(self, message, text: str):
        """Speak text using backend TTS"""
        guild_id = message.guild.id
        
        if guild_id not in self.voice_handlers:
            await message.reply("Not in voice! Use `!join` first.")
            return
        
        if not text.strip():
            await message.reply("Provide text to speak!")
            return
        
        try:
            handler = self.voice_handlers[guild_id]
            text_preview = text[:100] + "..." if len(text) > 100 else text
            await message.reply(f"Speaking (Kokoro TTS): *{text_preview}*")
            
            success = await handler.speak_text(text)
            if not success:
                await message.reply("TTS playback issue - check logs")
                
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _ask_question(self, message, question: str):
        """Ask AI through backend"""
        if not self.backend_client:
            await message.reply("Backend not connected!")
            return
        
        if not question.strip():
            await message.reply("Ask a question!")
            return
        
        try:
            await message.reply("Processing with Phi-3...")
            
            response = await self.backend_client.send_message(
                user_id=str(message.author.id),
                message=question,
                context={
                    "source": "text",
                    "channel_id": str(message.channel.id),
                    "guild_id": str(message.guild.id)
                }
            )
            
            if len(response) > 1900:
                response = response[:1900] + "..."
            
            await message.reply(response)
            
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _show_status(self, message):
        """Show system status"""
        embed = discord.Embed(title="Backend Bot Status", color=0x0099ff)
        
        # Bot status
        opus_status = "OK" if discord.opus.is_loaded() else "ERROR"
        backend_status = "OK" if self.backend_client else "ERROR"
        
        embed.add_field(
            name="Bot Status",
            value=f"Latency: {round(self.latency * 1000)}ms\nGuilds: {len(self.guilds)}\nVoice: {len(self.voice_handlers)} active",
            inline=True
        )
        
        embed.add_field(
            name="Components",
            value=f"Opus: {opus_status}\nBackend API: {backend_status}",
            inline=True
        )
        
        # Backend status
        if self.backend_client:
            try:
                status = await self.backend_client.get_api_status()
                embed.add_field(
                    name="Backend API",
                    value=f"Status: {status.get('status', 'unknown')}\nModels: {status.get('models', 'unknown')}",
                    inline=False
                )
            except:
                pass
        
        await message.reply(embed=embed)
    
    async def _show_models(self, message):
        """Show backend model information"""
        if not self.backend_client:
            await message.reply("Backend not connected!")
            return
        
        try:
            embed = discord.Embed(
                title="Backend AI Models",
                color=0x0099ff
            )
            
            embed.add_field(
                name="Speech Recognition",
                value="**Parakeet-TDT-0.6B**\nNVIDIA ASR model\nLocal inference",
                inline=True
            )
            
            embed.add_field(
                name="Language Model", 
                value="**Phi-3-mini-4k**\nMicrosoft LLM\nLocal inference",
                inline=True
            )
            
            embed.add_field(
                name="Text-to-Speech",
                value="**Kokoro-82M**\n54 voice options\nLocal inference",
                inline=True
            )
            
            await message.reply(embed=embed)
            
        except Exception as e:
            await message.reply(f"Error getting model info: {str(e)}")
    
    async def _show_help(self, message):
        """Show help"""
        embed = discord.Embed(
            title="Backend AI Voice Bot",
            description="WSL2 Discord bot using backend API for local models",
            color=0x0099ff
        )
        
        embed.add_field(
            name="Voice Commands",
            value="`!join` - Connect with backend models\n"
                  "`!leave` - Disconnect from voice\n"
                  "`!speak <text>` - Kokoro TTS synthesis",
            inline=False
        )
        
        embed.add_field(
            name="Chat Commands",
            value="`!ask <question>` - Phi-3 chat\n"
                  "`!status` - System status\n"
                  "`!models` - Show AI models\n"
                  "`!help` - This help message",
            inline=False
        )
        
        embed.add_field(
            name="Backend Models",
            value="All processing through local models:\n"
                  "• Parakeet ASR\n"
                  "• Phi-3 LLM\n"
                  "• Kokoro TTS (54 voices)",
            inline=False
        )
        
        await message.reply(embed=embed)

def main():
    """Main entry point"""
    # Validate config
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"[ERROR] Configuration error: {e}")
        sys.exit(1)
    
    # Initialize bot
    bot = BackendDiscordBot()
    
    try:
        logger.info("[START] Starting Backend WSL2 Discord Bot...")
        logger.info(f"[API] Backend URL: {Config.BACKEND_API_URL}")
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("[BYE] Bot stopped")
    except Exception as e:
        logger.error(f"[CRASH] Fatal error: {e}")

if __name__ == "__main__":
    main()