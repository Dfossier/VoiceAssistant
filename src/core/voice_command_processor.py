"""Voice Command Processor for Development Assistance

Processes voice commands related to development tasks and Claude Code integration.
Provides intelligent command recognition and execution for coding workflows.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from loguru import logger

@dataclass
class VoiceCommand:
    """Represents a recognized voice command"""
    action: str
    parameters: Dict[str, Any]
    confidence: float
    description: str

class VoiceCommandProcessor:
    """Processes voice commands for development assistance"""
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "voice_commands.json"
        
        self.config_path = Path(config_path)
        self.commands_config = {}
        self.context_keywords = []
        self.response_templates = {}
        self.safety_filters = {}
        
        self._load_config()
    
    def _load_config(self):
        """Load voice commands configuration"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    
                self.commands_config = config.get("development_commands", {})
                self.context_keywords = config.get("context_keywords", [])
                self.response_templates = config.get("response_templates", {})
                self.safety_filters = config.get("safety_filters", {})
                
                logger.info(f"✅ Loaded voice commands config from {self.config_path}")
            else:
                logger.warning(f"⚠️ Voice commands config not found: {self.config_path}")
                self._create_default_config()
                
        except Exception as e:
            logger.error(f"❌ Error loading voice commands config: {e}")
            self._create_default_config()
    
    def _create_default_config(self):
        """Create default configuration if file is missing"""
        self.commands_config = {
            "terminal_commands": [
                {
                    "trigger": ["run command", "execute"],
                    "action": "send_command",
                    "description": "Execute a command in terminal"
                }
            ]
        }
        self.context_keywords = ["code", "debug", "error", "file", "terminal"]
        self.response_templates = {
            "command_executed": "✅ Executed: {command}",
            "no_action": "❓ I didn't understand that command."
        }
        self.safety_filters = {
            "dangerous_commands": ["rm -rf", "del /s", "format"],
            "require_confirmation": ["git push", "npm publish"]
        }
    
    async def process_voice_input(self, text: str) -> Optional[VoiceCommand]:
        """Process voice input and return a recognized command"""
        text_lower = text.lower().strip()
        
        # Check all command categories
        for category, commands in self.commands_config.items():
            for command_def in commands:
                # Check if any trigger phrase matches
                for trigger in command_def.get("trigger", []):
                    if trigger.lower() in text_lower:
                        # Extract parameters based on action type
                        parameters = await self._extract_parameters(
                            text, text_lower, trigger, command_def["action"]
                        )
                        
                        # Calculate confidence based on match quality
                        confidence = self._calculate_confidence(text_lower, trigger, parameters)
                        
                        return VoiceCommand(
                            action=command_def["action"],
                            parameters=parameters,
                            confidence=confidence,
                            description=command_def.get("description", "")
                        )
        
        return None
    
    async def _extract_parameters(self, original_text: str, text_lower: str, 
                                 trigger: str, action: str) -> Dict[str, Any]:
        """Extract parameters from voice input based on action type"""
        parameters = {}
        
        if action == "send_command":
            # Extract command after trigger
            command = self._extract_after_trigger(text_lower, trigger)
            command = self._clean_command(command)
            if command:
                parameters["command"] = command
                
        elif action == "add_text":
            # Extract text after trigger
            text_to_add = self._extract_after_trigger(text_lower, trigger)
            text_to_add = self._clean_text_input(text_to_add)
            if text_to_add:
                parameters["text"] = text_to_add
                
        elif action == "read_file":
            # Extract filename
            filename = self._extract_filename(original_text)
            if filename:
                parameters["file_path"] = filename
                
        elif action == "edit_file":
            # Extract filename and optional changes
            filename = self._extract_filename(original_text)
            if filename:
                parameters["file_path"] = filename
                # Look for edit instructions
                edit_text = self._extract_after_pattern(text_lower, ["to", "and", "change"])
                if edit_text:
                    parameters["changes"] = edit_text
                    
        elif action == "debug_assistance":
            # Look for specific error or context
            error_context = self._extract_after_pattern(text_lower, ["with", "for", "about"])
            if error_context:
                parameters["context"] = error_context
                
        elif action == "run_tests":
            # Extract specific test or test file
            test_spec = self._extract_after_pattern(text_lower, ["for", "on", "in"])
            if test_spec:
                parameters["test_spec"] = test_spec
        
        return parameters
    
    def _extract_after_trigger(self, text: str, trigger: str) -> str:
        """Extract text that comes after a trigger phrase"""
        trigger_lower = trigger.lower()
        if trigger_lower in text:
            parts = text.split(trigger_lower, 1)
            if len(parts) > 1:
                return parts[1].strip()
        return ""
    
    def _extract_after_pattern(self, text: str, patterns: List[str]) -> str:
        """Extract text after any of the given patterns"""
        for pattern in patterns:
            if pattern in text:
                parts = text.split(pattern, 1)
                if len(parts) > 1:
                    return parts[1].strip()
        return ""
    
    def _extract_filename(self, text: str) -> Optional[str]:
        """Extract filename from text using various patterns"""
        # Common filename patterns
        patterns = [
            r'([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)',  # Files with extensions
            r'([a-zA-Z0-9_\-./\\]+)',                # Files without extensions
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                # Return the longest match (likely most complete filename)
                return max(matches, key=len)
        
        return None
    
    def _clean_command(self, command: str) -> str:
        """Clean up extracted command"""
        # Remove common filler words
        command = command.replace("in terminal", "").replace("in the terminal", "")
        command = command.replace("please", "").replace("now", "")
        return command.strip()
    
    def _clean_text_input(self, text: str) -> str:
        """Clean up extracted text input"""
        text = text.replace("in terminal", "").replace("in the terminal", "")
        text = text.replace("please", "")
        return text.strip()
    
    def _calculate_confidence(self, text: str, trigger: str, parameters: Dict[str, Any]) -> float:
        """Calculate confidence score for command recognition"""
        base_confidence = 0.7  # Base confidence for trigger match
        
        # Boost confidence based on parameters
        if parameters:
            base_confidence += 0.2
            
        # Boost confidence for exact trigger match
        if trigger in text:
            base_confidence += 0.1
            
        # Reduce confidence for very long or complex text
        if len(text) > 100:
            base_confidence -= 0.1
            
        return min(base_confidence, 1.0)
    
    def is_development_context(self, text: str) -> bool:
        """Check if text is in development context"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.context_keywords)
    
    def check_safety(self, command: str) -> Tuple[bool, Optional[str]]:
        """Check if command is safe to execute"""
        command_lower = command.lower()
        
        # Check for dangerous commands
        dangerous = self.safety_filters.get("dangerous_commands", [])
        for dangerous_cmd in dangerous:
            if dangerous_cmd.lower() in command_lower:
                return False, f"Dangerous command detected: {dangerous_cmd}"
        
        # Check for commands requiring confirmation
        require_confirm = self.safety_filters.get("require_confirmation", [])
        for confirm_cmd in require_confirm:
            if confirm_cmd.lower() in command_lower:
                return True, f"Command requires confirmation: {confirm_cmd}"
        
        return True, None
    
    def format_response(self, template_key: str, **kwargs) -> str:
        """Format response using templates"""
        template = self.response_templates.get(template_key, "{message}")
        try:
            return template.format(**kwargs)
        except Exception:
            return str(kwargs.get("message", "Action completed"))
    
    async def get_command_suggestions(self, partial_text: str) -> List[str]:
        """Get command suggestions based on partial input"""
        suggestions = []
        text_lower = partial_text.lower()
        
        # Find matching triggers
        for category, commands in self.commands_config.items():
            for command_def in commands:
                for trigger in command_def.get("trigger", []):
                    if any(word in trigger.lower() for word in text_lower.split()):
                        suggestion = f"{trigger} - {command_def.get('description', '')}"
                        if suggestion not in suggestions:
                            suggestions.append(suggestion)
        
        return suggestions[:5]  # Return top 5 suggestions


# Global instance
voice_command_processor = VoiceCommandProcessor()