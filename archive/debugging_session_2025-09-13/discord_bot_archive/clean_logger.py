"""
Clean logging configuration without emojis
"""

import logging
import sys

def setup_clean_logging(level=logging.INFO):
    """Setup logging without emoji characters"""
    
    # Create custom formatter without emojis
    class CleanFormatter(logging.Formatter):
        """Formatter that removes emoji characters"""
        
        def format(self, record):
            # Remove common emojis from the message
            if hasattr(record, 'msg'):
                record.msg = clean_emojis(str(record.msg))
            return super().format(record)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )
    
    # Apply clean formatter to all handlers
    formatter = CleanFormatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    for handler in logging.root.handlers:
        handler.setFormatter(formatter)

def clean_emojis(text):
    """Replace emoji characters with text equivalents"""
    replacements = {
        '🔧': '[SETUP]',
        '✅': '[OK]',
        '❌': '[ERROR]',
        '⚠️': '[WARN]',
        '🤖': '[BOT]',
        '📊': '[INFO]',
        '🧩': '[STATUS]',
        '🎤': '[VOICE]',
        '🔇': '[MUTE]',
        '🗣️': '[SPEAK]',
        '📝': '[TEXT]',
        '💭': '[THINK]',
        '🔊': '[AUDIO]',
        '📡': '[API]',
        '🚀': '[START]',
        '👋': '[BYE]',
        '💥': '[CRASH]',
        '🎯': '[READY]',
        '🔄': '[LOAD]',
        '📁': '[FILE]',
        '🎵': '[MUSIC]',
        '🎪': '[MODEL]',
        '🧪': '[TEST]',
    }
    
    result = text
    for emoji, replacement in replacements.items():
        result = result.replace(emoji, replacement)
    
    # Remove any remaining Unicode emoji characters
    import re
    # This pattern matches most emoji
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    
    result = emoji_pattern.sub('', result)
    
    return result