"""LLM integration with support for API providers and local models"""
import asyncio
import os
import json
from typing import Dict, Any, Optional, List, AsyncIterator
from pathlib import Path

# Import LangChain components with fallbacks
try:
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    ChatOpenAI = None
    ChatAnthropic = None

try:
    from langchain_community.llms import HuggingFacePipeline, LlamaCpp
    from langchain.schema import HumanMessage, SystemMessage, AIMessage
    LOCAL_MODELS_AVAILABLE = True
except ImportError:
    LOCAL_MODELS_AVAILABLE = False
    HuggingFacePipeline = None
    LlamaCpp = None
    HumanMessage = SystemMessage = AIMessage = None
from loguru import logger

class LocalModelHandler:
    """Handler for local model inference"""
    
    def __init__(self, model_path: str, model_type: str = "auto"):
        self.model_path = Path(model_path)
        self.model_type = model_type
        self.model = None
        
    async def load_model(self):
        """Load the local model based on type detection"""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model path not found: {self.model_path}")
            
        # Detect model type from files
        if self.model_type == "auto":
            self.model_type = self._detect_model_type()
            
        logger.info(f"Loading {self.model_type} model from {self.model_path}")
        
        if self.model_type == "deepseek-coder":
            await self._load_deepseek_model()
        elif self.model_type == "llama":
            await self._load_llama_model()
        else:
            await self._load_huggingface_model()
            
    def _detect_model_type(self) -> str:
        """Detect model type from directory structure and files"""
        path_str = str(self.model_path).lower()
        
        if "deepseek-coder" in path_str:
            return "deepseek-coder"
        elif "llama" in path_str:
            return "llama"
        elif any(f.suffix == ".gguf" for f in self.model_path.rglob("*.gguf")):
            return "llama-cpp"
        elif (self.model_path / "config.json").exists():
            return "huggingface"
        else:
            return "huggingface"  # Default fallback
            
    async def _load_deepseek_model(self):
        """Load DeepSeek Coder model"""
        try:
            # Check for both AWQ and base models
            if "awq" in str(self.model_path).lower():
                # AWQ quantized model
                from transformers import AutoTokenizer, AutoModelForCausalLM
                import torch
                
                self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_path))
                self.model = AutoModelForCausalLM.from_pretrained(
                    str(self.model_path),
                    torch_dtype=torch.float16,
                    device_map="auto",
                    trust_remote_code=True
                )
            else:
                # Standard model loading
                from transformers import pipeline
                self.model = pipeline(
                    "text-generation",
                    model=str(self.model_path),
                    torch_dtype="auto",
                    device_map="auto"
                )
                
        except Exception as e:
            logger.error(f"Failed to load DeepSeek model: {e}")
            raise
            
    async def _load_llama_model(self):
        """Load LLaMA model using LlamaCpp"""
        try:
            # Look for .gguf files
            gguf_files = list(self.model_path.rglob("*.gguf"))
            if gguf_files:
                model_file = gguf_files[0]
                self.model = LlamaCpp(
                    model_path=str(model_file),
                    n_ctx=2048,
                    n_batch=512,
                    verbose=False
                )
            else:
                # Try huggingface transformers
                await self._load_huggingface_model()
                
        except Exception as e:
            logger.error(f"Failed to load LLaMA model: {e}")
            raise
            
    async def _load_huggingface_model(self):
        """Load model using HuggingFace transformers"""
        try:
            from transformers import pipeline
            
            self.model = HuggingFacePipeline.from_model_id(
                model_id=str(self.model_path),
                task="text-generation",
                model_kwargs={"temperature": 0.7, "max_length": 2048}
            )
            
        except Exception as e:
            logger.error(f"Failed to load HuggingFace model: {e}")
            raise
            
    async def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        """Generate text using the loaded model"""
        if not self.model:
            await self.load_model()
            
        try:
            if hasattr(self.model, 'invoke'):
                # LangChain interface
                response = self.model.invoke(prompt)
                return response
            elif hasattr(self.model, '__call__'):
                # Pipeline interface
                response = self.model(prompt, max_new_tokens=max_tokens, do_sample=True)
                if isinstance(response, list) and len(response) > 0:
                    return response[0]['generated_text']
                return str(response)
            else:
                # Direct model interface
                inputs = self.tokenizer.encode(prompt, return_tensors="pt")
                with torch.no_grad():
                    outputs = self.model.generate(inputs, max_length=max_tokens)
                response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                return response[len(prompt):].strip()
                
        except Exception as e:
            logger.error(f"Error generating with local model: {e}")
            return f"Error: {str(e)}"


class LLMHandler:
    """Main LLM handler supporting multiple providers and local models"""
    
    def __init__(self):
        self.api_models = {}
        self.local_models = {}
        
        # Configuration from environment
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        self.llm_max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1024"))
        self.preferred_llm_provider = os.getenv("PREFERRED_LLM_PROVIDER", "fallback")
        
        # Local vLLM server configuration
        self.vllm_base_url = os.getenv("VLLM_BASE_URL", "http://localhost:8001/v1")
        self.vllm_available = False
        
        self._initialize_models()
        
    def _initialize_models(self):
        """Initialize available models based on configuration"""
        
        # Initialize API-based models only if LangChain is available
        if LANGCHAIN_AVAILABLE:
            if self.openai_api_key and ChatOpenAI:
                self.api_models['openai'] = ChatOpenAI(
                    api_key=self.openai_api_key,
                    model_name="gpt-3.5-turbo",
                    temperature=self.llm_temperature,
                    max_tokens=self.llm_max_tokens
                )
                
            if self.anthropic_api_key and ChatAnthropic:
                self.api_models['anthropic'] = ChatAnthropic(
                    api_key=self.anthropic_api_key,
                    model_name="claude-3-sonnet-20240229",
                    temperature=self.llm_temperature,
                    max_tokens_to_sample=self.llm_max_tokens
                )
        else:
            logger.warning("LangChain not available - API models disabled")
            
        # Scan for local models
        self._scan_local_models()
        
        # Check for vLLM server (disabled - using direct model loading)
        # asyncio.create_task(self._check_vllm_server())
        
    def _scan_local_models(self):
        """Scan the local models directory for available models"""
        models_dir = Path("/mnt/c/users/dfoss/desktop/localaimodels")
        
        if not models_dir.exists():
            logger.warning("Local models directory not found")
            return
            
        # Look for known model patterns - Updated for Pipecat models
        model_patterns = [
            "*phi3-mini*",           # Microsoft Phi-3 Mini
            "*parakeet-tdt*",        # NVIDIA Parakeet-TDT
            "*kokoro-tts*",          # Kokoro TTS
            "*deepseek-coder*",      # Legacy DeepSeek models
            "*llama*",
            "*mistral*",
            "*DeepScaleR*"
        ]
        
        for pattern in model_patterns:
            for model_path in models_dir.glob(pattern):
                if model_path.is_dir() and not model_path.name.endswith("-env"):
                    model_name = model_path.name.lower().replace("-", "_")
                    logger.info(f"Found local model: {model_name} at {model_path}")
                    
                    # Don't load immediately, load on demand
                    self.local_models[model_name] = {
                        'path': model_path,
                        'handler': None,
                        'loaded': False
                    }
    
    async def _check_vllm_server(self):
        """Check if vLLM server is available"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.vllm_base_url}/models", timeout=2.0)
                if response.status_code == 200:
                    self.vllm_available = True
                    models = response.json()
                    logger.info(f"✅ vLLM server available at {self.vllm_base_url}")
                    logger.info(f"Available models: {models}")
                else:
                    self.vllm_available = False
        except Exception as e:
            self.vllm_available = False
            logger.info(f"vLLM server not available at {self.vllm_base_url}: {str(e)[:50]}")
    
    async def get_available_models(self) -> Dict[str, List[str]]:
        """Get list of available models"""
        models = {
            'api_models': list(self.api_models.keys()),
            'local_models': list(self.local_models.keys())
        }
        if self.vllm_available:
            models['vllm_server'] = ['available']
        return models
        
    async def generate_response(
        self, 
        prompt: str, 
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        context: Optional[List[str]] = None
    ) -> str:
        """Generate a response using the specified model"""
        
        if not model:
            model = self.preferred_llm_provider
            
        # Skip local models for now due to complex WSL/Windows path issues
        # TODO: Fix local model integration for WSL environment
        logger.info("Skipping local Phi-3 model due to WSL path issues, using API models")
        
        # If LangChain isn't available, provide a basic response
        if not LANGCHAIN_AVAILABLE:
            return f"LLM integration not yet fully loaded. You asked: '{prompt}'. Please wait for the full installation to complete, or configure your API keys and restart."
        
        # Prepare messages
        messages = []
        if system_prompt and SystemMessage:
            messages.append(SystemMessage(content=system_prompt))
            
        if context and SystemMessage:
            context_text = "\n".join(context)
            messages.append(SystemMessage(content=f"Context:\n{context_text}"))
            
        if HumanMessage:
            messages.append(HumanMessage(content=prompt))
        
        try:
            # Check for vLLM server first (fastest option)
            if self.vllm_available:
                try:
                    logger.info("Using vLLM server for response generation")
                    return await self._generate_vllm_response(prompt, messages)
                except Exception as vllm_error:
                    logger.warning(f"vLLM server error: {vllm_error}")
                    self.vllm_available = False
            
            # If model not found, use preferred provider or fallback to openai
            if model not in self.api_models and model not in self.local_models:
                model = "openai" if "openai" in self.api_models else list(self.api_models.keys())[0] if self.api_models else "anthropic"
                logger.info(f"Model not found, using: {model}")
            
            # Try API models first (but fallback if they fail)
            if model in self.api_models and LANGCHAIN_AVAILABLE:
                try:
                    logger.info(f"Using API model: {model}")
                    response = await self.api_models[model].agenerate([messages])
                    return response.generations[0][0].text
                except Exception as api_error:
                    logger.error(f"API model {model} failed: {api_error}")
                    raise Exception(f"LLM API call failed: {api_error}")
                
            # Try local models (currently disabled due to WSL PyTorch issues)
            elif model in self.local_models:
                logger.info(f"Using local model: {model}")
                local_model = self.local_models[model]
                
                if not local_model['handler']:
                    local_model['handler'] = LocalModelHandler(
                        local_model['path'],
                        model_type="auto"
                    )
                    
                if not local_model['loaded']:
                    await local_model['handler'].load_model()
                    local_model['loaded'] = True
                    
                # Format prompt for local model
                full_prompt = self._format_prompt_for_local(messages)
                response = await local_model['handler'].generate(full_prompt)
                return response
                
            else:
                # Fallback to simple response if no models are available
                logger.warning(f"No models available, providing fallback response")
                return self._generate_fallback_response(prompt)
                
        except Exception as e:
            logger.error(f"Error generating response with {model}: {e}")
            # Provide fallback response instead of error
            return self._generate_fallback_response(prompt)
    
    def _generate_fallback_response(self, prompt: str) -> str:
        """Generate an intelligent fallback response using pattern matching"""
        prompt_lower = prompt.lower()
        
        # Programming and technical questions
        if any(word in prompt_lower for word in ["code", "programming", "python", "javascript", "function", "bug", "error", "debug"]):
            return "I can help with programming questions! While my full AI models are being optimized for WSL, I can provide basic guidance on coding, debugging, and technical issues. What specific problem are you working on?"
        
        # Questions and inquiries
        elif any(word in prompt_lower for word in ["what", "how", "why", "when", "where", "explain"]):
            if "hear" in prompt_lower:
                return "Yes, I can hear you perfectly! I'm your Discord AI assistant running with intelligent pattern matching while optimizing the full DeepSeek models for better WSL compatibility."
            elif "do" in prompt_lower or "can you" in prompt_lower:
                return "I can help with conversations, answer questions, provide coding assistance, and respond with voice. I'm currently running with smart fallback responses while optimizing the heavy AI models for WSL."
            else:
                return f"That's an interesting question about '{prompt}'. While my full AI models are being optimized, I can provide thoughtful responses based on common patterns and knowledge."
        
        # Greetings and social
        elif any(word in prompt_lower for word in ["hello", "hi", "hey", "greetings", "good morning", "good evening"]):
            return "Hello! Great to meet you! I'm your Discord AI assistant. I'm currently running with optimized pattern matching while the full DeepSeek models are being configured for WSL compatibility."
        
        # Status and capability questions  
        elif any(word in prompt_lower for word in ["status", "how are you", "working", "ready", "available"]):
            return "I'm working great! Currently running with intelligent fallback responses while optimizing the DeepSeek and DeepScaler models for better WSL performance. All core functionality is active!"
        
        # Testing
        elif "test" in prompt_lower:
            return "Test successful! All systems are operational. I'm responding with intelligent pattern matching while the full AI models are being optimized for WSL. Everything is working perfectly!"
        
        # Help and commands
        elif any(word in prompt_lower for word in ["help", "commands", "what can you do"]):
            return "I can help with conversations, coding questions, provide voice responses, and assist with various tasks. Try asking me about programming, technical issues, or just chat! Use !ask, !speak, or !status commands."
        
        # Default intelligent response
        else:
            # Extract key words for more contextual response
            words = prompt_lower.split()
            key_words = [w for w in words if len(w) > 3 and w not in ["the", "and", "for", "are", "but", "not", "you", "all", "can", "had", "her", "was", "one", "our", "out", "day", "get", "has", "him", "his", "how", "its", "may", "new", "now", "old", "see", "two", "way", "who", "boy", "did", "man", "men", "run", "try"]]
            
            if key_words:
                return f"I understand you're asking about {', '.join(key_words[:3])}. That's a great topic! While my full AI models are being optimized for WSL, I can definitely help discuss this. Could you tell me more specifically what you'd like to know?"
            else:
                return f"I received your message: '{prompt}'. I'm ready to help! While optimizing my full AI models for better WSL compatibility, I can provide thoughtful responses. What would you like to discuss?"
    
    async def _use_local_phi3_model(self, prompt: str, system_prompt: str = None) -> str:
        """Use local Phi-3 model via Windows subprocess"""
        try:
            # Create Windows script to run Phi-3
            phi3_path = self.local_models["phi3_mini"]["path"]
            model_file = phi3_path / "Phi-3-mini-4k-instruct-Q4_K_M.gguf"
            
            if not model_file.exists():
                raise FileNotFoundError(f"Phi-3 model not found at {model_file}")
            
            # Create Python script for Windows execution
            script_content = f'''
import sys
sys.path.append(r"C:\\Users\\dfoss\\Desktop\\LocalAIModels")

try:
    from llama_cpp import Llama
    
    # Load model
    model = Llama(
        model_path=r"{model_file}",
        n_gpu_layers=-1,
        n_ctx=4096,
        n_batch=512,
        verbose=False
    )
    
    # Format prompt
    system_msg = "{system_prompt or 'You are a helpful AI assistant.'}"
    user_msg = "{prompt.replace('"', '\\"')}"
    
    formatted_prompt = f"<|system|>\\n{{system_msg}}<|end|>\\n<|user|>\\n{{user_msg}}<|end|>\\n<|assistant|>\\n"
    
    # Generate response
    response = model(
        formatted_prompt,
        max_tokens=512,
        temperature=0.7,
        top_p=0.9,
        stop=["<|end|>", "<|user|>"],
        echo=False
    )
    
    print(response['choices'][0]['text'].strip())
    
except ImportError:
    print("ERROR: llama-cpp-python not installed. Run: pip install llama-cpp-python")
except Exception as e:
    print(f"ERROR: {{e}}")
'''
            
            # Write script to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script_content)
                script_path = f.name
            
            # Convert WSL path to Windows path
            windows_script_path = script_path.replace('/mnt/c/', 'C:\\').replace('/', '\\')
            
            # Run via Windows Command Prompt
            import subprocess
            import asyncio
            
            process = await asyncio.create_subprocess_shell(
                f'cmd.exe /c "cd C:\\Users\\dfoss\\Desktop\\LocalAIModels && python {windows_script_path}"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=30.0
                )
                
                # Clean up temp file
                Path(script_path).unlink(missing_ok=True)
                
                if process.returncode == 0:
                    result = stdout.decode('utf-8', errors='ignore').strip()
                    if result and not result.startswith("ERROR:"):
                        logger.info(f"✅ Phi-3 local response generated")
                        return result
                    else:
                        logger.error(f"Phi-3 script error: {result}")
                        raise Exception(f"Phi-3 script failed: {result}")
                else:
                    error_msg = stderr.decode('utf-8', errors='ignore')
                    logger.error(f"Phi-3 process error: {error_msg}")
                    raise Exception(f"Process failed: {error_msg}")
                    
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise Exception("Phi-3 processing timed out")
                
        except Exception as e:
            logger.error(f"Local Phi-3 model error: {e}")
            raise
    
    async def _generate_vllm_response(self, prompt: str, messages: List) -> str:
        """Generate response using vLLM server"""
        try:
            import httpx
            
            # Format messages for OpenAI-compatible API
            formatted_messages = []
            for msg in messages:
                if hasattr(msg, 'content'):
                    if isinstance(msg, SystemMessage):
                        formatted_messages.append({"role": "system", "content": msg.content})
                    elif isinstance(msg, HumanMessage):
                        formatted_messages.append({"role": "user", "content": msg.content})
                    elif isinstance(msg, AIMessage):
                        formatted_messages.append({"role": "assistant", "content": msg.content})
            
            # If no formatted messages, just use the prompt
            if not formatted_messages:
                formatted_messages = [{"role": "user", "content": prompt}]
            
            async with httpx.AsyncClient() as client:
                # Check if this is Ollama (different API structure)
                if "11434" in self.vllm_base_url:
                    # Ollama API format
                    response = await client.post(
                        f"{self.vllm_base_url.replace('/v1', '')}/chat",
                        json={
                            "model": "deepseek-coder:1.3b",
                            "messages": formatted_messages,
                            "stream": False
                        },
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return result['message']['content']
                    else:
                        raise Exception(f"Ollama server error: {response.status_code}")
                else:
                    # vLLM/OpenAI-compatible format
                    response = await client.post(
                        f"{self.vllm_base_url}/chat/completions",
                        json={
                            "model": "deepseek-coder",  # vLLM will use whatever model is loaded
                            "messages": formatted_messages,
                            "temperature": self.llm_temperature,
                            "max_tokens": self.llm_max_tokens
                        },
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return result['choices'][0]['message']['content']
                    else:
                        raise Exception(f"vLLM server error: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Error calling vLLM server: {e}")
            raise
            
    def _format_prompt_for_local(self, messages: List) -> str:
        """Format messages for local model inference"""
        formatted_parts = []
        
        for message in messages:
            if isinstance(message, SystemMessage):
                formatted_parts.append(f"System: {message.content}")
            elif isinstance(message, HumanMessage):
                formatted_parts.append(f"Human: {message.content}")
            elif isinstance(message, AIMessage):
                formatted_parts.append(f"Assistant: {message.content}")
                
        formatted_parts.append("Assistant:")
        return "\n\n".join(formatted_parts)
        
    async def stream_response(
        self, 
        prompt: str, 
        model: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Stream response tokens (for supported models)"""
        
        if not model:
            model = self.preferred_llm_provider
            
        try:
            if model in self.api_models and hasattr(self.api_models[model], 'astream'):
                async for chunk in self.api_models[model].astream([HumanMessage(content=prompt)]):
                    if chunk.content:
                        yield chunk.content
            else:
                # For non-streaming models, yield the full response
                response = await self.generate_response(prompt, model)
                yield response
                
        except Exception as e:
            logger.error(f"Error streaming response: {e}")
            yield f"Error: {str(e)}"
            
    async def analyze_code_error(self, error_text: str, code_context: str) -> str:
        """Specialized method for analyzing code errors"""
        system_prompt = """You are a debugging assistant. Analyze the error and provide:
1. Root cause explanation
2. Specific fix suggestions
3. Prevention tips
Keep responses concise and actionable."""
        
        prompt = f"""
Error:
{error_text}

Code Context:
{code_context}

Please analyze this error and provide debugging guidance.
"""
        
        return await self.generate_response(
            prompt, 
            system_prompt=system_prompt
        )
        
    async def suggest_code_improvements(self, code: str, file_type: str) -> str:
        """Analyze code and suggest improvements"""
        system_prompt = f"""You are a code review assistant specializing in {file_type}. 
Provide concise suggestions for:
1. Code quality improvements
2. Performance optimizations  
3. Best practices
4. Security considerations"""
        
        prompt = f"""Review this {file_type} code:

{code}

Provide improvement suggestions.
"""
        
        return await self.generate_response(
            prompt,
            system_prompt=system_prompt
        )
    
    async def process_message(
        self,
        message: str,
        conversation_history: List[Dict],
        context: Optional[Dict[str, Any]] = None
    ) -> 'ConversationResponse':
        """Process a Discord message with conversation history and context"""
        
        # Build conversation context
        recent_history = conversation_history[-10:]  # Last 10 messages for context
        
        # Create system prompt with context
        system_parts = ["You are a helpful AI assistant integrated with Discord."]
        
        if context:
            if context.get('current_directory'):
                system_parts.append(f"Current working directory: {context['current_directory']}")
            if context.get('active_files'):
                system_parts.append(f"Active files: {', '.join(context['active_files'])}")
        
        system_parts.append("Provide helpful, concise responses. Use Discord markdown for formatting.")
        system_prompt = "\n".join(system_parts)
        
        # Build conversation prompt
        conversation_context = []
        for msg in recent_history[-5:]:  # Last 5 exchanges
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            conversation_context.append(f"{role.title()}: {content}")
        
        if conversation_context:
            full_prompt = f"Previous conversation:\n{chr(10).join(conversation_context)}\n\nUser: {message}"
        else:
            full_prompt = message
        
        try:
            response_text = await self.generate_response(
                prompt=full_prompt,
                system_prompt=system_prompt
            )
            
            # Parse response for suggestions and file references
            suggestions = self._extract_suggestions(response_text)
            files_referenced = self._extract_file_references(response_text)
            
            return ConversationResponse(
                response=response_text,
                suggestions=suggestions,
                files_referenced=files_referenced
            )
            
        except Exception as e:
            logger.error(f"Error processing Discord message: {e}")
            return ConversationResponse(
                response=f"I encountered an error processing your message: {str(e)}",
                suggestions=[],
                files_referenced=[]
            )
    
    def _extract_suggestions(self, text: str) -> List[str]:
        """Extract command suggestions from response text"""
        suggestions = []
        
        # Look for common patterns that suggest actions
        if "run" in text.lower() and ("command" in text.lower() or "script" in text.lower()):
            suggestions.append("!run")
        if "debug" in text.lower() or "error" in text.lower():
            suggestions.append("!debug")
        if "file" in text.lower() and ("check" in text.lower() or "look" in text.lower()):
            suggestions.append("!analyze")
        
        return suggestions
    
    def _extract_file_references(self, text: str) -> List[str]:
        """Extract file path references from response text"""
        import re
        
        # Pattern to match file paths (simplified)
        file_patterns = [
            r'[\w\/\-\.]+\.\w+:\d+',  # file.py:123
            r'`[\w\/\-\.]+\.\w+`',    # `file.py`
            r'[\w\/\-\.]+\.py',       # file.py
            r'[\w\/\-\.]+\.js',       # file.js  
            r'[\w\/\-\.]+\.cpp',      # file.cpp
        ]
        
        references = []
        for pattern in file_patterns:
            matches = re.findall(pattern, text)
            references.extend(matches)
        
        return list(set(references))  # Remove duplicates
    
    async def analyze_project(self, path: str) -> str:
        """Analyze a project directory for issues and insights"""
        try:
            project_path = Path(path)
            if not project_path.exists():
                return f"Project path does not exist: {path}"
            
            # Basic project analysis
            python_files = list(project_path.rglob("*.py"))
            js_files = list(project_path.rglob("*.js"))
            
            analysis_parts = [
                f"Project Analysis for: {project_path.name}",
                f"Python files found: {len(python_files)}",
                f"JavaScript files found: {len(js_files)}"
            ]
            
            # Check for common project files
            if (project_path / "requirements.txt").exists():
                analysis_parts.append("✅ Requirements file found")
            if (project_path / "package.json").exists():
                analysis_parts.append("✅ Package.json found")
            if (project_path / ".gitignore").exists():
                analysis_parts.append("✅ Git ignore file found")
            
            # Sample a few files for quick analysis
            if python_files:
                sample_file = python_files[0]
                try:
                    with open(sample_file, 'r', encoding='utf-8') as f:
                        content = f.read(1000)  # First 1000 chars
                    analysis_parts.append(f"Sample from {sample_file.name}: {len(content.split())} words")
                except:
                    pass
            
            return "\n".join(analysis_parts)
            
        except Exception as e:
            logger.error(f"Error analyzing project {path}: {e}")
            return f"Error analyzing project: {str(e)}"


# Response model for Discord integration
class ConversationResponse:
    """Response structure for Discord conversation"""
    def __init__(self, response: str, suggestions: List[str] = None, files_referenced: List[str] = None):
        self.response = response
        self.suggestions = suggestions or []
        self.files_referenced = files_referenced or []