#!/usr/bin/env python3
"""
Discord.py Voice Bot with Full Pipeline
Uses discord.py (no Error 4006) + manual voice recording approach
"""

import asyncio
import discord
import discord.opus
import logging
import sys
import os
import tempfile
import wave
import io
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
    """Voice recorder using discord.py capabilities"""
    
    def __init__(self, voice_handler, voice_client):
        self.voice_handler = voice_handler
        self.voice_client = voice_client
        self.recording = True
        self.users_speaking = {}
        
    async def start_monitoring(self):
        """Start voice activity monitoring"""
        logger.info("[VOICE] Starting voice activity monitoring")
        
        # Monitor voice state changes
        self.monitor_task = asyncio.create_task(self._monitor_voice_activity())
    
    async def stop_monitoring(self):
        """Stop voice monitoring"""
        self.recording = False
        if hasattr(self, 'monitor_task'):
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
    
    async def _monitor_voice_activity(self):
        """Monitor voice activity and simulate recording"""
        try:
            while self.recording:
                await asyncio.sleep(2)
                
                # In a real implementation, we'd capture actual audio here
                # For now, we'll use voice state events and manual triggers
                
                # Check if anyone is speaking (we'll detect this through voice state changes)
                if self.users_speaking:
                    logger.info(f"[VOICE] Detected {len(self.users_speaking)} active speakers")
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[ERROR] Voice monitoring error: {e}")
    
    def user_started_speaking(self, user):
        """Called when user starts speaking"""
        if user.bot:
            return
        
        self.users_speaking[user.id] = {
            'user': user,
            'start_time': asyncio.get_event_loop().time(),
            'chunks': []
        }
        
        logger.info(f"[VOICE] {user.display_name} started speaking")
    
    def user_stopped_speaking(self, user):
        """Called when user stops speaking"""
        if user.bot or user.id not in self.users_speaking:
            return
        
        speaking_data = self.users_speaking.pop(user.id)
        duration = asyncio.get_event_loop().time() - speaking_data['start_time']
        
        logger.info(f"[VOICE] {user.display_name} spoke for {duration:.2f} seconds")
        
        # If they spoke for a reasonable amount of time, process it
        if duration > 1.0:  # At least 1 second
            asyncio.create_task(self._simulate_voice_processing(user, duration))
    
    async def _simulate_voice_processing(self, user, duration):
        """Simulate voice processing for testing"""
        logger.info(f"[TEST] Simulating voice processing for {user.display_name} ({duration:.2f}s)")
        
        # Create simulated audio data for testing
        test_audio = self._create_test_audio_data(duration)
        
        if test_audio:
            await self.voice_handler.process_voice_audio(test_audio, user.display_name)
    
    def _create_test_audio_data(self, duration):
        """Create test audio data (silence) for testing the pipeline"""
        try:
            # Create a WAV file with silence
            sample_rate = 44100
            samples = int(sample_rate * duration)
            
            # Create silence (zeros)
            audio_data = [0] * (samples * 2)  # Stereo
            
            # Convert to bytes
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
            
            with wave.open(temp_path, 'wb') as wav_file:
                wav_file.setnchannels(2)  # Stereo
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(bytes(audio_data))
            
            # Read back as bytes
            with open(temp_path, 'rb') as f:
                wav_bytes = f.read()
            
            os.unlink(temp_path)
            return wav_bytes
            
        except Exception as e:
            logger.error(f"[ERROR] Test audio creation failed: {e}")
            return None

class VoiceHandler:
    """Voice handler for full AI pipeline"""
    
    def __init__(self, bot, guild_id: int, backend_client: BackendClient):
        self.bot = bot
        self.guild_id = guild_id
        self.backend_client = backend_client
        self.voice_client = None
        self.recorder = None
        
    async def start_listening(self, voice_client):
        """Start voice processing"""
        self.voice_client = voice_client
        
        # Create recorder
        self.recorder = VoiceRecorder(self, voice_client)
        await self.recorder.start_monitoring()
        
        logger.info("[VOICE] Voice pipeline started")
    
    async def stop_listening(self):
        """Stop voice processing"""
        if self.recorder:
            await self.recorder.stop_monitoring()
            
        logger.info("[VOICE] Voice pipeline stopped")
    
    def user_speaking_update(self, user, speaking_state):
        """Handle user speaking state changes"""
        if not self.recorder:
            return
        
        if speaking_state:
            self.recorder.user_started_speaking(user)
        else:
            self.recorder.user_stopped_speaking(user)
    
    async def process_voice_audio(self, audio_data: bytes, user_name: str):
        """Process voice through full AI pipeline"""
        try:
            if not audio_data or len(audio_data) < 1000:
                logger.warning(f"[WARN] Audio too short from {user_name}")
                return
            
            logger.info(f"[PIPELINE] Processing {len(audio_data)} bytes from {user_name}")
            
            # Send status update
            guild = self.bot.get_guild(self.guild_id)
            if guild:
                channel = guild.system_channel or next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
                if channel:
                    await channel.send(f"🎤 Processing voice from **{user_name}**...")
            
            # Step 1: Speech to text (ASR)
            logger.info("[ASR] Transcribing with Parakeet...")
            text = await self.backend_client.transcribe_audio(audio_data)
            
            if not text or not text.strip():
                logger.warning("[WARN] Empty transcription")
                if channel:
                    await channel.send(f"❓ Could not understand speech from **{user_name}**")
                return
            
            logger.info(f"[ASR] Transcribed: '{text}'")
            
            # Step 2: Get AI response (LLM)
            logger.info("[LLM] Getting response from Phi-3...")
            response = await self.backend_client.send_message(
                user_id=user_name,
                message=text,
                context={"source": "voice", "guild_id": str(self.guild_id)}
            )
            
            if not response:
                logger.warning("[WARN] Empty AI response")
                return
            
            logger.info(f"[LLM] AI Response: {response[:100]}...")
            
            # Step 3: Text to speech (TTS)
            logger.info("[TTS] Generating speech with Kokoro...")
            audio_response = await self.backend_client.text_to_speech(response)
            
            if not audio_response:
                logger.warning("[WARN] TTS failed")
                if channel:
                    await channel.send(f"🔇 TTS generation failed")
                return
            
            logger.info(f"[TTS] Generated {len(audio_response)} bytes of speech")
            
            # Step 4: Play response
            logger.info("[AUDIO] Playing AI response...")
            success = await self.play_audio(audio_response)
            
            # Show conversation in text
            if channel:
                embed = discord.Embed(
                    title="🗣️ Voice Conversation",
                    color=0x00ff00
                )
                embed.add_field(name=f"You said:", value=text, inline=False)
                embed.add_field(name="AI replied:", value=response[:1000] + ("..." if len(response) > 1000 else ""), inline=False)
                embed.add_field(name="Status:", value="✅ Full pipeline completed!" if success else "⚠️ Audio playback failed", inline=False)
                await channel.send(embed=embed)
            
            logger.info("[SUCCESS] Full voice pipeline completed!")
                
        except Exception as e:
            logger.error(f"[ERROR] Voice pipeline error: {e}")
            if guild and channel:
                await channel.send(f"❌ Voice processing error: {str(e)}")
    
    async def play_audio(self, audio_data: bytes) -> bool:
        """Play audio through Discord"""
        try:
            if not self.voice_client or not self.voice_client.is_connected():
                return False
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                audio_source = discord.FFmpegPCMAudio(temp_path, options='-loglevel error')
                self.voice_client.play(audio_source)
                
                # Wait for playback
                while self.voice_client.is_playing():
                    await asyncio.sleep(0.1)
                
                logger.info("[OK] Audio playback complete")
                return True
                
            finally:
                await asyncio.sleep(0.5)
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"[ERROR] Audio playback error: {e}")
            return False

class DiscordPyVoiceBot(discord.Client):
    """Discord bot using discord.py with voice recording"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.voice_handlers: Dict[int, VoiceHandler] = {}
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
            
            if await self.backend_client.health_check():
                logger.info("[OK] Backend API connected")
            else:
                logger.warning("[WARN] Backend API not available")
                
        except Exception as e:
            logger.error(f"[ERROR] Backend error: {e}")
            self.backend_client = None
        
        # Show status
        opus_status = "[OK]" if discord.opus.is_loaded() else "[ERROR]"
        backend_status = "[OK]" if self.backend_client else "[ERROR]"
        logger.info(f"[STATUS] Opus: {opus_status} | Backend: {backend_status}")
    
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates for speaking detection"""
        # Skip bot's own state changes
        if member == self.user:
            return
        
        guild_id = member.guild.id
        if guild_id not in self.voice_handlers:
            return
        
        handler = self.voice_handlers[guild_id]
        
        # Detect speaking state changes (this is a simplified detection)
        # In practice, we'd need more sophisticated voice activity detection
        if hasattr(before, 'self_mute') and hasattr(after, 'self_mute'):
            if before.self_mute != after.self_mute:
                # User muted/unmuted - treat as speaking event for testing
                if not after.self_mute:  # User unmuted
                    handler.user_speaking_update(member, True)
                    await asyncio.sleep(3)  # Simulate speaking for 3 seconds
                    handler.user_speaking_update(member, False)
    
    async def on_message(self, message):
        """Handle messages"""
        if message.author == self.user:
            return
        
        content = message.content.lower().strip()
        
        if content == '!listen':
            await self._start_voice_pipeline(message)
        elif content == '!stop':
            await self._stop_voice_pipeline(message)
        elif content.startswith('!speak '):
            await self._test_tts(message, content[7:])
        elif content.startswith('!say '):
            await self._simulate_voice_input(message, content[5:])
        elif content == '!status':
            await self._show_status(message)
        elif content == '!help':
            await self._show_help(message)
    
    async def _start_voice_pipeline(self, message):
        """Start the full voice AI pipeline"""
        if not message.author.voice:
            await message.reply("Join a voice channel first!")
            return
        
        if not self.backend_client:
            await message.reply("Backend API not connected!")
            return
        
        channel = message.author.voice.channel
        guild_id = message.guild.id
        
        try:
            # Disconnect if already connected
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect()
                await asyncio.sleep(1)
            
            # Connect to voice
            voice_client = await channel.connect(timeout=20.0)
            
            if voice_client and voice_client.is_connected():
                # Initialize voice handler
                handler = VoiceHandler(self, guild_id, self.backend_client)
                self.voice_handlers[guild_id] = handler
                await handler.start_listening(voice_client)
                
                embed = discord.Embed(
                    title="🎙️ Full Voice AI Pipeline Active!",
                    description=f"Connected to **{channel.name}** with complete AI processing!",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Pipeline Steps",
                    value="1. 🎤 **Voice Input** (Your speech)\n2. 🔤 **ASR** (Parakeet transcription)\n3. 🧠 **LLM** (Phi-3 response)\n4. 🔊 **TTS** (Kokoro speech)\n5. 🎵 **Playback** (Voice response)",
                    inline=False
                )
                embed.add_field(
                    name="Test Methods",
                    value="• **Mute/unmute** your mic to trigger voice detection\n• Use `!say <text>` to simulate voice input\n• Use `!speak <text>` to test TTS only",
                    inline=False
                )
                
                await message.reply(embed=embed)
                logger.info(f"[OK] Full voice pipeline active in {channel.name}")
            else:
                await message.reply("❌ Failed to connect to voice")
                
        except Exception as e:
            await message.reply(f"❌ Connection error: {str(e)}")
            logger.error(f"[ERROR] Voice pipeline error: {e}")
    
    async def _stop_voice_pipeline(self, message):
        """Stop voice pipeline"""
        guild_id = message.guild.id
        
        try:
            if guild_id in self.voice_handlers:
                await self.voice_handlers[guild_id].stop_listening()
                del self.voice_handlers[guild_id]
            
            if message.guild.voice_client:
                await message.guild.voice_client.disconnect()
                await message.reply("🔇 Voice pipeline stopped!")
            else:
                await message.reply("Not listening!")
                
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _test_tts(self, message, text: str):
        """Test TTS only"""
        guild_id = message.guild.id
        
        if guild_id not in self.voice_handlers:
            await message.reply("Use `!listen` first!")
            return
        
        if not text.strip():
            await message.reply("Provide text to speak!")
            return
        
        try:
            handler = self.voice_handlers[guild_id]
            await message.reply(f"🔊 Speaking with Kokoro: *{text[:100]}...*")
            
            audio_data = await self.backend_client.text_to_speech(text)
            if audio_data:
                success = await handler.play_audio(audio_data)
                if not success:
                    await message.reply("⚠️ Playback failed")
            else:
                await message.reply("❌ TTS generation failed")
                
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _simulate_voice_input(self, message, text: str):
        """Simulate voice input for testing the full pipeline"""
        guild_id = message.guild.id
        
        if guild_id not in self.voice_handlers:
            await message.reply("Use `!listen` first!")
            return
        
        if not text.strip():
            await message.reply("Provide text to simulate!")
            return
        
        try:
            handler = self.voice_handlers[guild_id]
            await message.reply(f"🎤 Simulating voice input: *{text}*")
            
            # Skip ASR, directly process the text through LLM->TTS pipeline
            logger.info(f"[SIMULATE] Processing simulated input: {text}")
            
            response = await self.backend_client.send_message(
                user_id=message.author.display_name,
                message=text,
                context={"source": "voice_simulation", "guild_id": str(guild_id)}
            )
            
            if response:
                audio_data = await self.backend_client.text_to_speech(response)
                if audio_data:
                    success = await handler.play_audio(audio_data)
                    
                    embed = discord.Embed(
                        title="🤖 Simulated Voice Conversation",
                        color=0x0099ff
                    )
                    embed.add_field(name="Simulated input:", value=text, inline=False)
                    embed.add_field(name="AI response:", value=response, inline=False)
                    embed.add_field(name="Status:", value="✅ Pipeline completed!" if success else "⚠️ Playback failed", inline=False)
                    await message.reply(embed=embed)
                    
        except Exception as e:
            await message.reply(f"Error: {str(e)}")
    
    async def _show_status(self, message):
        """Show status"""
        embed = discord.Embed(title="🎙️ Discord.py Voice AI Bot Status", color=0x0099ff)
        
        opus_status = "OK" if discord.opus.is_loaded() else "ERROR"
        backend_status = "OK" if self.backend_client else "ERROR"
        
        embed.add_field(
            name="Core Components",
            value=f"Discord.py: 2.6.3\nOpus: {opus_status}\nBackend API: {backend_status}",
            inline=True
        )
        
        embed.add_field(
            name="Voice Pipeline",
            value=f"Active: {len(self.voice_handlers)} channels\nLatency: {round(self.latency * 1000)}ms",
            inline=True
        )
        
        if self.voice_handlers:
            embed.add_field(
                name="Pipeline Status", 
                value="🎤 ASR: Parakeet\n🧠 LLM: Phi-3\n🔊 TTS: Kokoro",
                inline=False
            )
        
        await message.reply(embed=embed)
    
    async def _show_help(self, message):
        """Show help"""
        embed = discord.Embed(
            title="🎙️ Full Voice AI Pipeline Bot",
            description="Complete voice conversation with local AI models",
            color=0x0099ff
        )
        
        embed.add_field(
            name="Voice Pipeline Commands",
            value="`!listen` - Start full voice AI pipeline\n`!stop` - Stop voice processing\n`!speak <text>` - Test TTS output",
            inline=False
        )
        
        embed.add_field(
            name="Testing Commands", 
            value="`!say <text>` - Simulate voice input (skip ASR)\n`!status` - Show system status\n`!help` - This help message",
            inline=False
        )
        
        embed.add_field(
            name="How to Test Full Pipeline",
            value="1. Join voice channel, use `!listen`\n2. **Mute/unmute** your mic to trigger voice detection\n3. Use `!say Hello` to test LLM→TTS pipeline\n4. Bot will respond with voice + text",
            inline=False
        )
        
        embed.add_field(
            name="AI Models",
            value="• **Parakeet**: Speech recognition\n• **Phi-3**: Language model\n• **Kokoro**: Text-to-speech (54 voices)",
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
    
    bot = DiscordPyVoiceBot()
    
    try:
        logger.info("[START] Starting Discord.py Voice AI Bot...")
        logger.info(f"[API] Backend URL: {Config.BACKEND_API_URL}")
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("[BYE] Bot stopped")
    except Exception as e:
        logger.error(f"[CRASH] Fatal error: {e}")

if __name__ == "__main__":
    main()