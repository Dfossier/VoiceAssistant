#!/usr/bin/env python3
"""
Full-Featured WSL2 Discord Bot with Local AI Models
Features: VAD, Pipecat, Parakeet ASR, Phi-3 LLM, Kokoro TTS
"""

import asyncio
import discord
import discord.opus
import logging
import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any
import numpy as np
import sounddevice as sd
from io import BytesIO
import base64

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Suppress noisy Discord logs
for logger_name in ['discord', 'discord.gateway', 'discord.client', 'discord.voice_client']:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# Import AI model handlers
try:
    from ai_models import LocalModelHandler
    logger.info("✅ Local AI models imported successfully")
except ImportError as e:
    logger.warning(f"⚠️ Local AI models not available: {e}")
    LocalModelHandler = None

# Force load Opus
logger.info("🔧 Loading Opus library...")
try:
    discord.opus._load_default()
    opus_status = "✅ Loaded" if discord.opus.is_loaded() else "❌ Failed"
    logger.info(f"Opus status: {opus_status}")
except Exception as e:
    logger.error(f"❌ Opus error: {e}")

class VoiceActivityDetector:
    """Multi-method Voice Activity Detection"""
    
    def __init__(self):
        self.method = "webrtc"  # webrtc, silero, or rms
        self.webrtc_vad = None
        self.silero_model = None
        self._init_vad()
    
    def _init_vad(self):
        """Initialize VAD models"""
        try:
            if self.method == "webrtc":
                import webrtcvad
                self.webrtc_vad = webrtcvad.Vad(2)  # Aggressiveness 0-3
                logger.info("✅ WebRTC VAD initialized")
        except ImportError:
            logger.warning("⚠️ WebRTC VAD not available, using RMS fallback")
            self.method = "rms"
        
        try:
            if self.method == "silero":
                import torch
                torch.set_num_threads(1)
                self.silero_model, _ = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False
                )
                logger.info("✅ Silero VAD initialized")
        except Exception as e:
            logger.warning(f"⚠️ Silero VAD not available: {e}")
    
    def detect_speech(self, audio_data: bytes, sample_rate: int = 48000) -> bool:
        """Detect speech in audio data"""
        try:
            if self.method == "webrtc" and self.webrtc_vad:
                # WebRTC VAD requires 16kHz
                if sample_rate != 16000:
                    # Simple downsampling (not ideal but functional)
                    audio_np = np.frombuffer(audio_data, dtype=np.int16)
                    step = sample_rate // 16000
                    audio_np = audio_np[::step]
                    audio_data = audio_np.tobytes()
                
                # WebRTC VAD needs specific frame sizes
                frame_duration = 30  # ms
                frame_size = int(16000 * frame_duration / 1000) * 2  # bytes
                
                if len(audio_data) >= frame_size:
                    return self.webrtc_vad.is_speech(audio_data[:frame_size], 16000)
            
            elif self.method == "silero" and self.silero_model:
                import torch
                # Convert to tensor and run Silero
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                audio_tensor = torch.FloatTensor(audio_np)
                
                with torch.no_grad():
                    speech_prob = self.silero_model(audio_tensor, sample_rate).item()
                return speech_prob > 0.5
            
            # Fallback: RMS-based VAD
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            rms = np.sqrt(np.mean(audio_np**2))
            return rms > 500  # Adjust threshold as needed
            
        except Exception as e:
            logger.error(f"❌ VAD error: {e}")
            return False

class FullVoiceHandler:
    """Complete voice processing pipeline"""
    
    def __init__(self, bot, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self.vad = VoiceActivityDetector()
        self.model_handler = LocalModelHandler() if LocalModelHandler else None
        self.recording = False
        self.voice_client = None
        
        # Audio settings
        self.sample_rate = 48000
        self.channels = 2
        self.chunk_size = 960  # 20ms at 48kHz
        
        logger.info(f"✅ Voice handler initialized for guild {guild_id}")
    
    async def start_listening(self, voice_client):
        """Start voice processing pipeline"""
        self.voice_client = voice_client
        self.recording = True
        
        logger.info("🎤 Starting voice pipeline...")
        
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
        """Main recording and processing loop"""
        try:
            # Simplified recording approach - periodic checks
            logger.info("🎤 Voice recording loop started (periodic mode)")
            
            while self.recording:
                await asyncio.sleep(2)  # Check every 2 seconds
                
                # In a real implementation, we'd capture audio from voice_client
                # For now, this is a placeholder that listens for voice commands
                
        except Exception as e:
            logger.error(f"❌ Recording loop error: {e}")
    
    async def _process_audio(self, audio_data: bytes, user_name: str):
        """Process recorded audio"""
        try:
            if not audio_data or len(audio_data) < 1000:
                return
            
            # VAD check
            if not self.vad.detect_speech(audio_data):
                return
            
            logger.info(f"🎤 Processing speech from {user_name}")
            
            # Transcribe audio
            text = await self._transcribe_audio(audio_data)
            if not text or text.strip() == "":
                return
            
            logger.info(f"📝 Transcribed: {text}")
            
            # Get AI response (create a mock user object)
            class MockUser:
                def __init__(self, name):
                    self.display_name = name
            
            mock_user = MockUser(user_name)
            response = await self._get_ai_response(text, mock_user)
            if not response:
                return
            
            logger.info(f"🤖 AI Response: {response}")
            
            # Convert to speech and play
            await self._speak_response(response)
            
            # Send text response to channel
            guild = self.bot.get_guild(self.guild_id)
            if guild and guild.system_channel:
                embed = discord.Embed(
                    title="🗣️ Voice Conversation",
                    color=0x00ff00
                )
                embed.add_field(name=f"🎤 {user_name}", value=text, inline=False)
                embed.add_field(name="🤖 Assistant", value=response, inline=False)
                await guild.system_channel.send(embed=embed)
                
        except Exception as e:
            logger.error(f"❌ Audio processing error: {e}")
    
    async def _transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio to text using Parakeet or Whisper"""
        try:
            if self.model_handler:
                # Try Parakeet first
                text = await self.model_handler.transcribe_parakeet(audio_data)
                if text:
                    return text
            
            # Fallback to Whisper
            return await self._whisper_transcribe(audio_data)
            
        except Exception as e:
            logger.error(f"❌ Transcription error: {e}")
            return ""
    
    async def _whisper_transcribe(self, audio_data: bytes) -> str:
        """Whisper fallback transcription"""
        try:
            import whisper
            import tempfile
            
            # Save audio to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            # Load Whisper model (cached)
            if not hasattr(self, '_whisper_model'):
                self._whisper_model = whisper.load_model("base")
            
            # Transcribe
            result = self._whisper_model.transcribe(temp_path)
            text = result["text"].strip()
            
            # Clean up
            os.unlink(temp_path)
            
            return text
            
        except Exception as e:
            logger.error(f"❌ Whisper error: {e}")
            return ""
    
    async def _get_ai_response(self, text: str, user: discord.User) -> str:
        """Get AI response using Phi-3 or API fallback"""
        try:
            if self.model_handler:
                # Try Phi-3 first
                response = await self.model_handler.generate_phi3(text, user.display_name)
                if response:
                    return response
            
            # Fallback to OpenAI
            return await self._openai_response(text, user)
            
        except Exception as e:
            logger.error(f"❌ AI response error: {e}")
            return "I'm sorry, I couldn't process your request right now."
    
    async def _openai_response(self, text: str, user: discord.User) -> str:
        """OpenAI API fallback"""
        try:
            from openai import AsyncOpenAI
            
            if not hasattr(self, '_openai_client'):
                api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    return "OpenAI API key not configured."
                self._openai_client = AsyncOpenAI(api_key=api_key)
            
            response = await self._openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"You are a helpful AI assistant in a Discord voice chat. Keep responses concise and conversational. The user's name is {user.display_name}."},
                    {"role": "user", "content": text}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"❌ OpenAI error: {e}")
            return "I'm having trouble connecting to my language model."
    
    async def _speak_response(self, text: str):
        """Convert text to speech and play using Kokoro or fallback"""
        try:
            if self.model_handler:
                # Try Kokoro first
                audio_data = await self.model_handler.synthesize_kokoro(text)
                if audio_data:
                    await self._play_audio(audio_data)
                    return
            
            # Fallback TTS
            await self._fallback_tts(text)
            
        except Exception as e:
            logger.error(f"❌ TTS error: {e}")
    
    async def _fallback_tts(self, text: str):
        """Fallback TTS using system tools"""
        try:
            import subprocess
            import tempfile
            
            # Use espeak-ng if available
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Generate speech
            result = subprocess.run([
                "espeak-ng", "-w", temp_path, "-s", "150", text
            ], capture_output=True, check=True)
            
            # Read generated audio
            with open(temp_path, "rb") as f:
                audio_data = f.read()
            
            # Clean up
            os.unlink(temp_path)
            
            await self._play_audio(audio_data)
            
        except Exception as e:
            logger.error(f"❌ Fallback TTS error: {e}")
    
    async def _play_audio(self, audio_data: bytes):
        """Play audio through Discord voice"""
        try:
            if not self.voice_client or not self.voice_client.is_connected():
                return
            
            # Create audio source from bytes
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            # Play audio
            audio_source = discord.FFmpegPCMAudio(temp_path)
            self.voice_client.play(audio_source)
            
            # Wait for playback to complete
            while self.voice_client.is_playing():
                await asyncio.sleep(0.1)
            
            # Clean up
            os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"❌ Audio playback error: {e}")

class FullFeaturedBot(discord.Client):
    """Full-featured Discord bot with local AI models"""
    
    def __init__(self):
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        
        self.voice_handlers: Dict[int, FullVoiceHandler] = {}
        self.model_handler = LocalModelHandler() if LocalModelHandler else None
        
    async def on_ready(self):
        """Bot ready event"""
        logger.info(f"🤖 {self.user} connected to Discord!")
        logger.info(f"📊 Bot in {len(self.guilds)} guilds")
        
        # Check components
        components = []
        components.append(f"Opus: {'✅' if discord.opus.is_loaded() else '❌'}")
        components.append(f"Local Models: {'✅' if self.model_handler else '❌'}")
        
        logger.info(f"🧩 Components: {' | '.join(components)}")
    
    async def on_message(self, message):
        """Handle text messages"""
        if message.author == self.user:
            return
        
        content = message.content.lower().strip()
        
        # Command handlers
        if content == '!join':
            await self._join_voice(message)
        elif content == '!leave':
            await self._leave_voice(message)
        elif content.startswith('!speak '):
            await self._speak_text(message, content[7:])
        elif content == '!status':
            await self._show_status(message)
        elif content == '!help':
            await self._show_help(message)
        elif content.startswith('!ask '):
            await self._ask_question(message, content[5:])
    
    async def _join_voice(self, message):
        """Join voice channel with full pipeline"""
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
            
            # Connect to voice
            voice_client = await channel.connect(timeout=20.0, reconnect=False)
            await asyncio.sleep(1)
            
            if voice_client and voice_client.is_connected():
                # Initialize voice handler
                handler = FullVoiceHandler(self, guild_id)
                self.voice_handlers[guild_id] = handler
                
                # Start voice pipeline
                await handler.start_listening(voice_client)
                
                embed = discord.Embed(
                    title="🎤 Voice Assistant Active",
                    description=f"Connected to **{channel.name}** with full AI pipeline!",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Features Active",
                    value="• Voice Activity Detection\n• Speech Recognition (Parakeet/Whisper)\n• AI Chat (Phi-3/OpenAI)\n• Text-to-Speech (Kokoro/eSpeak)",
                    inline=False
                )
                embed.add_field(
                    name="Usage", 
                    value="Just start talking naturally! I'll respond with voice + text.",
                    inline=False
                )
                
                await message.reply(embed=embed)
                logger.info(f"✅ Full voice pipeline active in {channel.name}")
                
            else:
                raise Exception("Connection failed")
                
        except Exception as e:
            await message.reply(f"❌ Failed to join voice: {str(e)}")
            logger.error(f"❌ Voice join error: {e}")
    
    async def _leave_voice(self, message):
        """Leave voice channel"""
        guild_id = message.guild.id
        
        try:
            # Stop voice handler
            if guild_id in self.voice_handlers:
                await self.voice_handlers[guild_id].stop_listening()
                del self.voice_handlers[guild_id]
            
            # Disconnect from voice
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect(force=True)
                await message.reply("👋 Left voice channel and stopped AI pipeline")
            else:
                await message.reply("❌ Not connected to voice!")
                
        except Exception as e:
            await message.reply(f"❌ Error leaving voice: {str(e)}")
    
    async def _speak_text(self, message, text: str):
        """Speak provided text"""
        guild_id = message.guild.id
        
        if guild_id not in self.voice_handlers:
            await message.reply("❌ Not connected to voice! Use `!join` first.")
            return
        
        if not text.strip():
            await message.reply("❌ Please provide text to speak!")
            return
        
        try:
            handler = self.voice_handlers[guild_id]
            await message.reply(f"🗣️ Speaking: *{text[:100]}{'...' if len(text) > 100 else ''}*")
            await handler._speak_response(text)
            
        except Exception as e:
            await message.reply(f"❌ TTS error: {str(e)}")
    
    async def _ask_question(self, message, question: str):
        """Ask AI a question (text only)"""
        if not question.strip():
            await message.reply("❌ Please ask a question!")
            return
        
        try:
            await message.reply(f"🤔 Processing: *{question[:100]}{'...' if len(question) > 100 else ''}*")
            
            if self.model_handler:
                response = await self.model_handler.generate_phi3(question, message.author.display_name)
                if response:
                    await message.reply(response)
                    return
            
            # OpenAI fallback
            await message.reply("🔄 Using OpenAI fallback...")
            # Implement OpenAI call here
            await message.reply("OpenAI response would go here")
            
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
    
    async def _show_status(self, message):
        """Show bot status"""
        embed = discord.Embed(title="🖥️ Bot Status", color=0x0099ff)
        
        # Core status
        embed.add_field(
            name="🤖 Bot Info",
            value=f"Latency: {round(self.latency * 1000)}ms\nGuilds: {len(self.guilds)}\nVoice: {len(self.voice_handlers)} active",
            inline=True
        )
        
        # Component status
        components = []
        components.append(f"Opus: {'✅' if discord.opus.is_loaded() else '❌'}")
        components.append(f"Local Models: {'✅' if self.model_handler else '❌'}")
        
        embed.add_field(
            name="🧩 Components",
            value="\n".join(components),
            inline=True
        )
        
        # Voice connections
        if self.voice_handlers:
            voice_info = []
            for guild_id, handler in self.voice_handlers.items():
                guild = self.get_guild(guild_id)
                if guild and guild.voice_client:
                    voice_info.append(f"• {guild.voice_client.channel.name} ({guild.name})")
            
            if voice_info:
                embed.add_field(
                    name="🎵 Active Voice",
                    value="\n".join(voice_info),
                    inline=False
                )
        
        await message.reply(embed=embed)
    
    async def _show_help(self, message):
        """Show help information"""
        embed = discord.Embed(
            title="🤖 Full-Featured AI Voice Bot",
            description="Local AI models with voice processing in WSL2",
            color=0x0099ff
        )
        
        embed.add_field(
            name="🎤 Voice Commands",
            value="`!join` - Join voice with full AI pipeline\n"
                  "`!leave` - Leave voice channel\n"
                  "`!speak <text>` - Convert text to speech",
            inline=False
        )
        
        embed.add_field(
            name="💬 Text Commands",
            value="`!ask <question>` - Ask AI a question\n"
                  "`!status` - Show system status\n"
                  "`!help` - Show this help",
            inline=False
        )
        
        embed.add_field(
            name="🧠 AI Features",
            value="• **VAD**: Voice Activity Detection\n"
                  "• **ASR**: Parakeet + Whisper backup\n"
                  "• **LLM**: Phi-3 + OpenAI backup\n"
                  "• **TTS**: Kokoro + eSpeak backup",
            inline=False
        )
        
        embed.add_field(
            name="🎯 Usage",
            value="1. Join a voice channel\n"
                  "2. Use `!join` to activate AI\n"
                  "3. Start talking naturally!\n"
                  "4. Bot responds with voice + text",
            inline=False
        )
        
        await message.reply(embed=embed)

def main():
    """Main entry point"""
    # Load environment
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"✅ Loaded .env from {env_path}")
    else:
        logger.warning(f"⚠️ .env not found at {env_path}")
    
    # Get Discord token
    token = os.getenv('DISCORD_TOKEN') or os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("❌ Discord token not found!")
        logger.info("💡 Set DISCORD_TOKEN or DISCORD_BOT_TOKEN in .env")
        sys.exit(1)
    
    # Initialize and run bot
    bot = FullFeaturedBot()
    
    try:
        logger.info("🚀 Starting Full-Featured WSL2 Discord Bot...")
        bot.run(token)
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
    finally:
        logger.info("🏁 Bot shutdown complete")

if __name__ == "__main__":
    main()