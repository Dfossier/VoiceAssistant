#!/usr/bin/env python3
"""
Voice Command Formatting Agent
Uses LLM to clean and format voice commands for terminal interaction
"""

import json
import asyncio
from typing import Dict, Any, Optional
from loguru import logger


class VoiceFormattingAgent:
    """Dedicated LLM agent for cleaning and formatting voice commands"""
    
    def __init__(self, model_manager):
        self.model_manager = model_manager
        self.system_prompt = """You are a voice command formatting specialist for terminal interaction.

Your job: Clean and format voice commands into structured actions.

INPUT: Raw speech-to-text transcription (may have punctuation errors, filler words, STT artifacts)
OUTPUT: JSON with clean action and parameters

ACTIONS:
- "add_text": Add text to terminal without executing
- "send_command": Add text and execute (press Enter)
- "conversation": Regular conversation (not a terminal command)

RULES:
1. Remove STT artifacts (trailing punctuation like comma/period, filler words like uh/um)
2. Preserve exact case for intended text/commands
3. Identify action intent clearly
4. Extract clean parameters
5. If not a terminal command, use "conversation" action

EXAMPLES:
INPUT: "type in terminal hello world comma"
OUTPUT: {"action": "add_text", "text": "hello world"}

INPUT: "send to terminal, uh, npm install"  
OUTPUT: {"action": "send_command", "command": "npm install"}

INPUT: "execute cd slash home"
OUTPUT: {"action": "send_command", "command": "cd /home"}

INPUT: "just type the word hello"
OUTPUT: {"action": "add_text", "text": "hello"}

INPUT: "what's the weather like"
OUTPUT: {"action": "conversation", "text": "what's the weather like"}

INPUT: "type Hello World with capital letters"
OUTPUT: {"action": "add_text", "text": "Hello World"}

CRITICAL: Only respond with valid JSON. No explanations or extra text."""

    async def format_voice_command(self, raw_transcription: str) -> Dict[str, Any]:
        """Clean and format voice command using LLM (with fast fallback)"""
        try:
            # Quick pre-check for obvious patterns to avoid LLM call
            if self._is_simple_pattern(raw_transcription):
                logger.debug(f"🚀 Fast pattern match for: '{raw_transcription}'")
                return self._fallback_parsing(raw_transcription)
                
            logger.debug(f"🧹 Formatting voice command: '{raw_transcription}'")
            
            # Use shorter, simpler prompt for faster processing
            prompt = f"Format: '{raw_transcription}'"
            
            response = await self.model_manager.generate_response(
                prompt, 
                system_prompt=self._get_short_system_prompt()
            )
            
            # Clean response (remove any markdown or extra text)
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()
            
            # Parse JSON response
            result = json.loads(response)
            
            logger.info(f"✅ Formatted: '{raw_transcription}' → {result}")
            return result
            
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Invalid JSON from formatting agent: {response}")
            return self._fallback_parsing(raw_transcription)
        except Exception as e:
            logger.error(f"❌ Formatting agent error: {e}")
            return self._fallback_parsing(raw_transcription)
    
    def _fallback_parsing(self, text: str) -> Dict[str, Any]:
        """Fallback to regex-based parsing if LLM fails"""
        logger.debug("🔄 Using fallback regex parsing")
        
        text_lower = text.lower().strip()
        
        # Terminal command patterns
        if any(phrase in text_lower for phrase in [
            "run command", "execute", "type in terminal", "send to terminal",
            "run in terminal", "terminal command"
        ]):
            # Extract command from text
            for trigger in ["run", "execute", "type", "send"]:
                if trigger in text_lower:
                    parts = text_lower.split(trigger, 1)
                    if len(parts) > 1:
                        command = parts[1].strip()
                        command = command.replace("in terminal", "").replace("in the terminal", "").strip()
                        command = command.strip('.,!?;:')  # Remove STT punctuation
                        if command:
                            return {"action": "send_command", "command": command}
        
        # Text addition patterns
        if any(phrase in text_lower for phrase in [
            "add text", "type", "write in terminal", "input"
        ]):
            for trigger in ["add", "type", "write", "input"]:
                if trigger in text_lower:
                    # Find trigger position in original text to preserve case
                    trigger_pos = text_lower.find(trigger)
                    if trigger_pos != -1:
                        text_to_add = text[trigger_pos + len(trigger):].strip()
                        text_to_add = text_to_add.replace("in terminal", "").replace("in the terminal", "").strip()
                        text_to_add = text_to_add.strip('.,!?;:')
                        if text_to_add:
                            return {"action": "add_text", "text": text_to_add}
        
        # Default to conversation
        return {"action": "conversation", "text": text.strip('.,!?;:')}
    
    def _is_simple_pattern(self, text: str) -> bool:
        """Check if text matches simple patterns that don't need LLM processing"""
        text_lower = text.lower().strip()
        
        # Common greeting patterns
        greetings = ["hi", "hello", "good morning", "good afternoon", "good evening", "hey"]
        if any(greeting in text_lower for greeting in greetings):
            return True
            
        # Questions about hearing
        if any(phrase in text_lower for phrase in ["can you hear", "do you hear", "hello?"]):
            return True
            
        # Very short texts (likely conversation)
        if len(text.split()) <= 3:
            return True
            
        return False
    
    def _get_short_system_prompt(self) -> str:
        """Shorter system prompt for faster processing"""
        return """Voice command parser. Return JSON only:
{"action": "add_text", "text": "..."} - type text
{"action": "send_command", "command": "..."} - execute command  
{"action": "conversation", "text": "..."} - chat
Clean STT artifacts (um, uh, trailing punctuation)."""


# Global instance
_formatting_agent = None

async def get_formatting_agent(model_manager):
    """Get or create the global formatting agent instance"""
    global _formatting_agent
    if _formatting_agent is None:
        _formatting_agent = VoiceFormattingAgent(model_manager)
    return _formatting_agent