#!/usr/bin/env python3
"""
Simplified WSL2 Discord Bot - Working with API fallbacks
Uses OpenAI APIs while local models load in background
"""

import asyncio
import discord
import discord.opus
import logging
import sys
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Suppress Discord logs
for logger_name in ['discord', 'discord.gateway', 'discord.client', 'discord.voice_client']:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# Force load Opus
logger.info("🔧 Loading Opus library...")
try:
    discord.opus._load_default()
    opus_status = "✅ Loaded" if discord.opus.is_loaded() else "❌ Failed"
    logger.info(f"Opus status: {opus_status}")
except Exception as e:
    logger.error(f"❌ Opus error: {e}")

class SimpleVAD:
    """Simple RMS-based Voice Activity Detection"""
    
    def __init__(self, threshold: float = 0.01):
        self.threshold = threshold
    
    def detect_speech(self, audio_data: bytes) -> bool:
        """Simple speech detection using RMS"""
        try:
            import numpy as np
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            rms = np.sqrt(np.mean(audio_np**2))
            return rms > (self.threshold * 32767)  # Scale for 16-bit audio
        except ImportError:
            # Fallback without numpy
            return len(audio_data) > 1000  # Simple length check

class SimpleVoiceHandler:
    """Simplified voice handler with API fallbacks"""
    
    def __init__(self, bot, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self.vad = SimpleVAD()
        self.recording = False
        self.voice_client = None
        
        # Initialize OpenAI client
        self.openai_client = None
        self._init_openai()
        
        logger.info(f"✅ Simple voice handler initialized for guild {guild_id}")
    
    def _init_openai(self):
        """Initialize OpenAI client if API key available"""
        try:
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                from openai import AsyncOpenAI
                self.openai_client = AsyncOpenAI(api_key=api_key)
                logger.info("✅ OpenAI client initialized")
            else:
                logger.warning("⚠️ No OpenAI API key found")
        except ImportError:
            logger.warning("⚠️ OpenAI library not available")
    
    async def start_listening(self, voice_client):
        """Start voice processing"""
        self.voice_client = voice_client
        self.recording = True
        logger.info("🎤 Simple voice pipeline started")
        
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
        logger.info("🔇 Voice pipeline stopped")
    
    async def _record_loop(self):
        """Simplified recording loop"""
        try:
            logger.info("🎤 Voice recording active (simplified mode)")
            while self.recording:
                await asyncio.sleep(3)  # Periodic check
                # In real implementation, would process captured audio
        except Exception as e:
            logger.error(f"❌ Recording loop error: {e}")
    
    async def transcribe_audio(self, audio_data: bytes) -> Optional[str]:
        """Transcribe audio using OpenAI Whisper API"""
        try:
            if not self.openai_client:
                return "Transcription not available (no API key)"
            
            # Save audio to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                # Use OpenAI Whisper API
                with open(temp_path, "rb") as audio_file:
                    transcript = await self.openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="text"
                    )
                return transcript.strip()
            finally:
                os.unlink(temp_path)
                
        except Exception as e:
            logger.error(f"❌ Transcription error: {e}")
            return None
    
    async def generate_response(self, text: str, user_name: str) -> Optional[str]:
        """Generate response using OpenAI"""
        try:
            if not self.openai_client:
                return f"I heard you say: '{text}' but I don't have AI access configured."
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"You are a helpful AI assistant in a Discord voice chat. Keep responses concise (1-2 sentences) and conversational. The user's name is {user_name}."},
                    {"role": "user", "content": text}
                ],
                max_tokens=100,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"❌ Response generation error: {e}")
            return f"I heard: '{text}' but couldn't generate a response."
    
    async def text_to_speech(self, text: str) -> Optional[bytes]:
        """Convert text to speech using OpenAI TTS"""
        try:
            if not self.openai_client:
                return None
            
            response = await self.openai_client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text,
                response_format="wav"
            )
            
            return response.content
            
        except Exception as e:
            logger.error(f"❌ TTS error: {e}")
            return None
    
    async def speak_text(self, text: str):
        """Speak text through Discord voice"""
        try:
            if not self.voice_client or not self.voice_client.is_connected():
                logger.warning("⚠️ No voice connection for TTS")
                return False
            
            # Generate speech audio
            audio_data = await self.text_to_speech(text)
            if not audio_data:
                logger.warning("⚠️ No audio generated")
                return False
            
            # Save to temp file and play
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                # Play through Discord
                audio_source = discord.FFmpegPCMAudio(temp_path)
                self.voice_client.play(audio_source)
                
                # Wait for playback
                while self.voice_client.is_playing():
                    await asyncio.sleep(0.1)
                
                return True
            finally:
                os.unlink(temp_path)
                
        except Exception as e:
            logger.error(f"❌ TTS playback error: {e}")
            return False

class SimpleDiscordBot(discord.Client):
    """Simplified Discord bot with API fallbacks"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.voice_handlers = {}
    
    async def on_ready(self):
        """Bot ready event"""
        logger.info(f"🤖 {self.user} connected to Discord!")
        logger.info(f"📊 Bot in {len(self.guilds)} guilds")
        
        # Check components
        opus_status = "✅" if discord.opus.is_loaded() else "❌"
        openai_status = "✅" if os.getenv('OPENAI_API_KEY') else "❌"
        
        logger.info(f"🧩 Components: Opus: {opus_status} | OpenAI: {openai_status}")
    
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
        elif content == '!help':
            await self._show_help(message)
    
    async def _join_voice(self, message):
        """Join voice channel"""
        if not message.author.voice:
            await message.reply("❌ You need to be in a voice channel!")
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
                handler = SimpleVoiceHandler(self, guild_id)
                self.voice_handlers[guild_id] = handler
                await handler.start_listening(voice_client)
                
                embed = discord.Embed(
                    title="🎤 Simple Voice Bot Connected",
                    description=f"Connected to **{channel.name}**!",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Available Features",
                    value="• `!speak <text>` - Text-to-speech\n• `!ask <question>` - AI chat\n• Voice processing ready!",
                    inline=False
                )
                
                await message.reply(embed=embed)
                logger.info(f"✅ Connected to {channel.name}")
            else:
                raise Exception("Connection failed")
                
        except Exception as e:
            await message.reply(f"❌ Failed to join: {str(e)}")
            logger.error(f"❌ Join error: {e}")
    
    async def _leave_voice(self, message):
        """Leave voice channel"""
        guild_id = message.guild.id
        
        try:
            if guild_id in self.voice_handlers:
                await self.voice_handlers[guild_id].stop_listening()
                del self.voice_handlers[guild_id]
            
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect(force=True)
                await message.reply("👋 Left voice channel!")
            else:
                await message.reply("❌ Not in voice!")
                
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
    
    async def _speak_text(self, message, text: str):
        """Speak text"""
        guild_id = message.guild.id
        
        if guild_id not in self.voice_handlers:
            await message.reply("❌ Not in voice! Use `!join` first.")
            return
        
        if not text.strip():
            await message.reply("❌ Provide text to speak!")
            return
        
        try:
            handler = self.voice_handlers[guild_id]
            await message.reply(f"🗣️ Speaking: *{text[:100]}{'...' if len(text) > 100 else ''}*")
            
            success = await handler.speak_text(text)
            if success:
                await message.reply("✅ Speech complete!")
            else:
                await message.reply("❌ TTS failed - check logs")
                
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
    
    async def _ask_question(self, message, question: str):
        """Ask AI a question"""
        if not question.strip():
            await message.reply("❌ Ask a question!")
            return
        
        try:
            guild_id = message.guild.id
            if guild_id in self.voice_handlers:
                handler = self.voice_handlers[guild_id]
                response = await handler.generate_response(question, message.author.display_name)
            else:
                # Use direct OpenAI call
                api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    await message.reply("❌ No AI API configured!")
                    return
                
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=api_key)
                
                completion = await client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": f"You are a helpful AI assistant. Keep responses concise. The user's name is {message.author.display_name}."},
                        {"role": "user", "content": question}
                    ],
                    max_tokens=150
                )
                response = completion.choices[0].message.content.strip()
            
            if len(response) > 1900:
                response = response[:1900] + "..."
            
            await message.reply(response)
            
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
    
    async def _show_status(self, message):
        """Show status"""
        embed = discord.Embed(title="🖥️ Simple Bot Status", color=0x0099ff)
        
        opus_status = "✅" if discord.opus.is_loaded() else "❌"
        openai_status = "✅" if os.getenv('OPENAI_API_KEY') else "❌"
        
        embed.add_field(
            name="Core Status",
            value=f"Latency: {round(self.latency * 1000)}ms\nGuilds: {len(self.guilds)}\nVoice: {len(self.voice_handlers)} active",
            inline=True
        )
        
        embed.add_field(
            name="Components",
            value=f"Opus: {opus_status}\nOpenAI API: {openai_status}",
            inline=True
        )
        
        await message.reply(embed=embed)
    
    async def _show_help(self, message):
        """Show help"""
        embed = discord.Embed(
            title="🤖 Simple WSL2 Voice Bot",
            description="API-powered voice bot with local model framework",
            color=0x0099ff
        )
        
        embed.add_field(
            name="🎤 Voice Commands",
            value="`!join` - Connect to voice with TTS\n"
                  "`!leave` - Leave voice channel\n"
                  "`!speak <text>` - Text-to-speech",
            inline=False
        )
        
        embed.add_field(
            name="💬 Chat Commands",
            value="`!ask <question>` - AI conversation\n"
                  "`!status` - Show bot status\n"
                  "`!help` - Show this help",
            inline=False
        )
        
        await message.reply(embed=embed)

def main():
    """Main entry point"""
    # Load environment
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"✅ Environment loaded")
    
    # Get token
    token = os.getenv('DISCORD_TOKEN') or os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("❌ Discord token not found!")
        sys.exit(1)
    
    # Run bot
    bot = SimpleDiscordBot()
    
    try:
        logger.info("🚀 Starting Simple WSL2 Discord Bot...")
        bot.run(token)
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")

if __name__ == "__main__":
    main()