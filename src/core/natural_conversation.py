"""Natural conversation system with streaming audio"""
import asyncio
import json
from typing import Dict, Any, Optional
from loguru import logger

class NaturalConversation:
    """Handle natural voice conversations with streaming"""
    
    def __init__(self, llm_handler, whisper_handler):
        self.llm_handler = llm_handler
        self.whisper_handler = whisper_handler
        self.conversation_active = False
        self.conversation_history = []
        
    async def process_conversation_turn(self, audio_data: str, websocket=None) -> Dict[str, Any]:
        """Process a complete conversation turn with context"""
        try:
            logger.info(f"Processing conversation turn, audio size: {len(audio_data)} chars")
            
            # 1. Transcribe speech
            logger.info("Starting transcription...")
            transcription = await self.whisper_handler.transcribe_audio(audio_data)
            logger.info(f"Transcription result: success={transcription.get('success')}")
            
            if not transcription.get("success"):
                return {
                    "type": "conversation_error",
                    "error": transcription.get("error", "Transcription failed")
                }
            
            user_text = transcription["text"].strip()
            if not user_text:
                return {
                    "type": "conversation_response",
                    "transcribed_text": "",
                    "response": "I didn't hear anything. Could you speak again?"
                }
            
            # 2. Add to conversation history
            self.conversation_history.append({
                "role": "user", 
                "content": user_text,
                "timestamp": asyncio.get_event_loop().time()
            })
            
            # Keep last 10 exchanges for context
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]
            
            # 3. Generate contextual response
            conversation_context = self._build_conversation_context()
            
            response = await self.llm_handler.generate_response(
                prompt=user_text,
                system_prompt=f"""You are in a natural voice conversation. 

Previous context:
{conversation_context}

Guidelines:
- Keep responses conversational and natural (1-3 sentences)
- Reference previous topics when relevant
- Ask follow-up questions to keep conversation flowing
- Speak as if talking to a friend
- No special formatting, just natural speech
- Be engaging and show interest in what they're saying"""
            )
            
            # 4. Add response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": response,
                "timestamp": asyncio.get_event_loop().time()
            })
            
            # 5. Send streaming response if websocket available
            if websocket:
                await self._stream_response(response, websocket)
            
            return {
                "type": "conversation_response",
                "transcribed_text": user_text,
                "response": response,
                "conversation_length": len(self.conversation_history)
            }
            
        except Exception as e:
            logger.error(f"Conversation error: {e}")
            return {
                "type": "conversation_error",
                "error": str(e)
            }
    
    def _build_conversation_context(self) -> str:
        """Build conversation context from history"""
        if len(self.conversation_history) < 2:
            return "This is the start of a new conversation."
        
        context_lines = []
        recent_history = self.conversation_history[-8:]  # Last 4 exchanges
        
        for entry in recent_history:
            role = "You" if entry["role"] == "user" else "Assistant"
            context_lines.append(f"{role}: {entry['content']}")
        
        return "\n".join(context_lines)
    
    async def _stream_response(self, response: str, websocket):
        """Stream response with chunked delivery for better UX"""
        try:
            # Send immediate feedback that processing is complete
            await websocket.send_json({
                "type": "conversation_stream_start",
                "message": "🎯 Transcription complete, responding..."
            })
            
            # Stream in chunks for better readability
            words = response.split()
            chunk_size = 3  # Stream 3 words at a time
            current_text = ""
            
            for i in range(0, len(words), chunk_size):
                chunk = words[i:i + chunk_size]
                current_text += " ".join(chunk) + " "
                
                await websocket.send_json({
                    "type": "conversation_stream",
                    "chunk": " ".join(chunk),
                    "current_text": current_text.strip(),
                    "position": i,
                    "total_words": len(words),
                    "progress": min(1.0, (i + chunk_size) / len(words))
                })
                
                # Shorter delay for better responsiveness
                await asyncio.sleep(0.05)
            
            # Send complete response
            await websocket.send_json({
                "type": "conversation_stream_complete",
                "complete_response": response.strip()
            })
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            # Fallback to direct response
            await websocket.send_json({
                "type": "conversation_response",
                "response": response,
                "streaming_failed": True
            })
    
    def start_new_conversation(self):
        """Start a fresh conversation"""
        self.conversation_history.clear()
        self.conversation_active = True
        return {
            "type": "conversation_started",
            "message": "New conversation started. Say hello!"
        }
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get summary of current conversation"""
        if not self.conversation_history:
            return {"exchanges": 0, "status": "no_conversation"}
        
        user_messages = [h for h in self.conversation_history if h["role"] == "user"]
        assistant_messages = [h for h in self.conversation_history if h["role"] == "assistant"]
        
        return {
            "exchanges": len(user_messages),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "last_user_message": user_messages[-1]["content"] if user_messages else None,
            "last_assistant_message": assistant_messages[-1]["content"] if assistant_messages else None,
            "conversation_duration": (
                self.conversation_history[-1]["timestamp"] - self.conversation_history[0]["timestamp"]
            ) if len(self.conversation_history) > 1 else 0
        }
    
    def end_conversation(self):
        """End the current conversation"""
        self.conversation_active = False
        summary = self.get_conversation_summary()
        self.conversation_history.clear()
        
        return {
            "type": "conversation_ended",
            "summary": summary
        }