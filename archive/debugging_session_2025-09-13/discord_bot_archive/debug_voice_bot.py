#!/usr/bin/env python3
"""
Debug Voice Bot - Simplified to test basic functionality
"""

import asyncio
import discord
import discord.opus
import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from backend_client import BackendClient
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Suppress Discord logs
for logger_name in ['discord', 'discord.gateway', 'discord.client']:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# Force load Opus
logger.info("[SETUP] Loading Opus library...")
try:
    discord.opus._load_default()
    opus_status = "[OK] Loaded" if discord.opus.is_loaded() else "[ERROR] Failed"
    logger.info(f"Opus status: {opus_status}")
except Exception as e:
    logger.error(f"[ERROR] Opus error: {e}")

class DebugBot(discord.Client):
    """Simple debug bot"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(intents=intents)
        self.backend_client = None
    
    async def on_ready(self):
        """Bot ready event"""
        logger.info(f"[BOT] {self.user} connected to Discord!")
        logger.info(f"[INFO] Bot in {len(self.guilds)} guilds")
        
        # Test backend
        try:
            self.backend_client = BackendClient(
                base_url=Config.BACKEND_API_URL,
                api_key=Config.BACKEND_API_KEY
            )
            
            health = await self.backend_client.health_check()
            logger.info(f"[BACKEND] Health check: {health}")
            
            if health:
                status = await self.backend_client.get_api_status()
                logger.info(f"[BACKEND] Status: {status}")
            
        except Exception as e:
            logger.error(f"[ERROR] Backend error: {e}")
        
        logger.info("[READY] Bot ready for commands!")
    
    async def on_message(self, message):
        """Handle all messages"""
        # Skip own messages
        if message.author == self.user:
            return
        
        content = message.content.strip()
        logger.info(f"[MSG] Received: '{content}' from {message.author.display_name}")
        
        # Test basic response
        if content.lower() == '!ping':
            await message.reply("Pong! Bot is responding.")
            logger.info("[PING] Responded to ping")
            return
        
        # Test backend connection
        if content.lower() == '!backend':
            if self.backend_client:
                try:
                    health = await self.backend_client.health_check()
                    await message.reply(f"Backend health: {health}")
                    logger.info(f"[BACKEND] Health test: {health}")
                except Exception as e:
                    await message.reply(f"Backend error: {str(e)}")
                    logger.error(f"[ERROR] Backend test failed: {e}")
            else:
                await message.reply("Backend client not initialized")
            return
        
        # Test voice connection
        if content.lower() == '!voice':
            if not message.author.voice:
                await message.reply("You need to be in a voice channel!")
                return
            
            channel = message.author.voice.channel
            logger.info(f"[VOICE] Attempting to join {channel.name}")
            
            try:
                # Test voice connection
                voice_client = await channel.connect(timeout=10.0)
                await message.reply(f"Connected to {channel.name}!")
                logger.info(f"[OK] Connected to voice")
                
                # Disconnect after 5 seconds
                await asyncio.sleep(5)
                await voice_client.disconnect()
                await message.reply("Disconnected from voice")
                logger.info("[OK] Disconnected from voice")
                
            except Exception as e:
                await message.reply(f"Voice connection failed: {str(e)}")
                logger.error(f"[ERROR] Voice connection error: {e}")
            return
        
        # Test TTS
        if content.lower().startswith('!tts '):
            text = content[5:]
            if not text.strip():
                await message.reply("Provide text for TTS")
                return
            
            logger.info(f"[TTS] Testing with text: {text}")
            
            if not self.backend_client:
                await message.reply("Backend not available")
                return
            
            try:
                await message.reply(f"Generating TTS for: {text}")
                audio_data = await self.backend_client.text_to_speech(text)
                
                if audio_data:
                    await message.reply(f"TTS generated: {len(audio_data)} bytes")
                    logger.info(f"[OK] TTS generated {len(audio_data)} bytes")
                else:
                    await message.reply("TTS generation failed")
                    logger.error("[ERROR] TTS returned no data")
                    
            except Exception as e:
                await message.reply(f"TTS error: {str(e)}")
                logger.error(f"[ERROR] TTS error: {e}")
            return
        
        # Test AI chat
        if content.lower().startswith('!chat '):
            question = content[6:]
            if not question.strip():
                await message.reply("Provide a question")
                return
            
            logger.info(f"[CHAT] Testing with question: {question}")
            
            if not self.backend_client:
                await message.reply("Backend not available")
                return
            
            try:
                await message.reply(f"Processing: {question}")
                response = await self.backend_client.send_message(
                    user_id=str(message.author.id),
                    message=question,
                    context={"source": "debug", "guild_id": str(message.guild.id)}
                )
                
                if response:
                    # Truncate if too long
                    if len(response) > 1500:
                        response = response[:1500] + "..."
                    await message.reply(f"AI Response: {response}")
                    logger.info(f"[OK] AI responded: {response[:100]}...")
                else:
                    await message.reply("AI returned empty response")
                    logger.error("[ERROR] Empty AI response")
                    
            except Exception as e:
                await message.reply(f"AI error: {str(e)}")
                logger.error(f"[ERROR] AI error: {e}")
            return
        
        # Help command
        if content.lower() == '!help':
            help_text = """
**Debug Commands:**
`!ping` - Test bot response
`!backend` - Test backend connection
`!voice` - Test voice connection (join/leave)
`!tts <text>` - Test text-to-speech
`!chat <question>` - Test AI chat
`!help` - Show this help

**Instructions:**
1. Try `!ping` first
2. Test `!backend` to check API
3. Join voice channel, then `!voice`
4. Test `!tts Hello world`
5. Test `!chat What is 2+2?`
            """
            await message.reply(help_text)
            return
        
        # Log unrecognized commands
        if content.startswith('!'):
            await message.reply(f"Unknown command: {content}. Use `!help` for available commands.")
            logger.warning(f"[WARN] Unknown command: {content}")

def main():
    """Main entry point"""
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"[ERROR] Configuration error: {e}")
        sys.exit(1)
    
    bot = DebugBot()
    
    try:
        logger.info("[START] Starting Debug Bot...")
        logger.info("[INFO] Use !help in Discord to see available commands")
        bot.run(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("[BYE] Bot stopped")
    except Exception as e:
        logger.error(f"[CRASH] Fatal error: {e}")

if __name__ == "__main__":
    main()