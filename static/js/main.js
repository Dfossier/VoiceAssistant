// WebSocket connection and UI management
let ws = null;
let reconnectInterval = null;
let reconnectAttempts = 0;

// DOM elements
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const voiceButton = document.getElementById('voice-button');
const chatMessages = document.getElementById('chat-messages');
const outputTerminal = document.getElementById('output-terminal');
const statusText = document.getElementById('status-text');
const statusIndicator = document.querySelector('#connection-status span');

// Initialize WebSocket connection
function connectWebSocket() {
    const wsUrl = `ws://${window.location.host}/ws`;
    
    try {
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log('WebSocket connected');
            updateConnectionStatus(true);
            reconnectAttempts = 0;
            
            if (reconnectInterval) {
                clearInterval(reconnectInterval);
                reconnectInterval = null;
            }
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleMessage(data);
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            updateConnectionStatus(false);
        };
        
        ws.onclose = () => {
            console.log('WebSocket disconnected');
            updateConnectionStatus(false);
            attemptReconnect();
        };
        
    } catch (error) {
        console.error('Failed to create WebSocket:', error);
        updateConnectionStatus(false);
        attemptReconnect();
    }
}

// Handle incoming messages
function handleMessage(data) {
    switch (data.type) {
        case 'chat_response':
            addChatMessage('assistant', data.message);
            break;
            
        case 'command_response':
            addOutputLine(data.output);
            break;
            
        case 'file_response':
            updateFileDisplay(data.result);
            break;
            
        case 'voice_response':
            // Show transcribed text if available
            if (data.transcribed_text) {
                addChatMessage('user', `🎤 ${data.transcribed_text}`);
            }
            addChatMessage('assistant', data.text || data.message);
            // Play audio if available
            if (data.audio && data.has_audio) {
                playAudioResponse(data.audio);
            }
            break;
            
        case 'error':
            addChatMessage('error', data.message);
            break;
            
        default:
            console.log('Unknown message type:', data.type);
    }
}

// Send message to server
function sendMessage() {
    const message = messageInput.value.trim();
    
    if (!message || !ws || ws.readyState !== WebSocket.OPEN) {
        return;
    }
    
    // Add user message to chat
    addChatMessage('user', message);
    
    // Send to server
    ws.send(JSON.stringify({
        type: 'chat',
        message: message,
        timestamp: Date.now()
    }));
    
    // Clear input
    messageInput.value = '';
}

// Add message to chat display
function addChatMessage(sender, message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'mb-3';
    
    const senderSpan = document.createElement('span');
    senderSpan.className = sender === 'user' ? 'text-blue-400' : 
                         sender === 'assistant' ? 'text-green-400' : 'text-red-400';
    senderSpan.textContent = sender.charAt(0).toUpperCase() + sender.slice(1) + ': ';
    
    const messageSpan = document.createElement('span');
    messageSpan.textContent = message;
    
    messageDiv.appendChild(senderSpan);
    messageDiv.appendChild(messageSpan);
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Add line to output terminal
function addOutputLine(line) {
    const lineDiv = document.createElement('div');
    lineDiv.textContent = line;
    lineDiv.className = 'text-gray-300';
    
    outputTerminal.appendChild(lineDiv);
    outputTerminal.scrollTop = outputTerminal.scrollHeight;
    
    // Limit output lines
    while (outputTerminal.children.length > 100) {
        outputTerminal.removeChild(outputTerminal.firstChild);
    }
}

// Update connection status display
function updateConnectionStatus(connected) {
    if (connected) {
        statusIndicator.className = 'inline-block w-2 h-2 bg-green-500 rounded-full mr-2';
        statusText.textContent = 'Connected';
    } else {
        statusIndicator.className = 'inline-block w-2 h-2 bg-red-500 rounded-full mr-2';
        statusText.textContent = 'Disconnected';
    }
}

// Attempt to reconnect
function attemptReconnect() {
    if (reconnectInterval) {
        return;
    }
    
    reconnectInterval = setInterval(() => {
        reconnectAttempts++;
        console.log(`Reconnection attempt ${reconnectAttempts}...`);
        
        if (reconnectAttempts > 10) {
            clearInterval(reconnectInterval);
            reconnectInterval = null;
            statusText.textContent = 'Connection failed';
            return;
        }
        
        connectWebSocket();
    }, 3000);
}

// Update file display (placeholder)
function updateFileDisplay(files) {
    const fileBrowser = document.getElementById('file-browser');
    fileBrowser.innerHTML = '<p class="text-gray-400">File browser update pending...</p>';
}

// Event listeners
sendButton.addEventListener('click', () => {
    // If in Firefox voice mode, treat as voice input
    if (voiceChat.isListening && !voiceChat.recognition && messageInput.value.trim()) {
        voiceChat.sendVoiceMessage(messageInput.value.trim());
        messageInput.value = '';
        voiceChat.stopListening();
    } else {
        sendMessage();
    }
});

messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        // If in Firefox voice mode, treat as voice input
        if (voiceChat.isListening && !voiceChat.recognition && messageInput.value.trim()) {
            voiceChat.sendVoiceMessage(messageInput.value.trim());
            messageInput.value = '';
            voiceChat.stopListening();
        } else {
            sendMessage();
        }
    }
});

// Quick action buttons
document.querySelectorAll('.space-y-2 button').forEach((button, index) => {
    button.addEventListener('click', () => {
        const actions = ['run_tests', 'check_logs', 'browse_web'];
        
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'command',
                action: actions[index],
                timestamp: Date.now()
            }));
        }
    });
});

// Voice Chat Integration
class VoiceChat {
    constructor() {
        this.recognition = null;
        this.audioRecorder = null;
        this.isListening = false;
        
        // Check for browser support
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = false;
            this.recognition.lang = 'en-US';
            
            this.recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                this.sendVoiceMessage(transcript);
            };
            
            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                addChatMessage('error', `Voice error: ${event.error}`);
                this.stopListening();
            };
            
            this.recognition.onend = () => {
                this.isListening = false;
                this.updateVoiceButton();
            };
        } else {
            // Initialize audio recorder for Firefox/other browsers
            this.audioRecorder = new AudioRecorder();
        }
    }
    
    startListening() {
        if (!this.recognition) {
            // Use real audio recording for Firefox
            if (this.audioRecorder) {
                this.audioRecorder.startRecording().then(started => {
                    if (started) {
                        this.isListening = true;
                        this.updateVoiceButton();
                        addChatMessage('system', '🎤 Recording... Click Stop when done');
                    }
                });
            }
            return;
        }
        
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(() => {
                this.recognition.start();
                this.isListening = true;
                this.updateVoiceButton();
                addChatMessage('system', '🎤 Listening... Speak now!');
            })
            .catch((err) => {
                console.error('Microphone access denied:', err);
                addChatMessage('error', 'Microphone access denied. Please allow microphone permissions.');
            });
    }
    
    stopListening() {
        if (this.recognition && this.isListening) {
            this.recognition.stop();
            this.isListening = false;
            this.updateVoiceButton();
        } else if (this.isListening && this.audioRecorder) {
            // Stop audio recording
            this.audioRecorder.stopRecording();
            this.isListening = false;
            this.updateVoiceButton();
            addChatMessage('system', '⏹️ Processing audio...');
        }
    }
    
    sendVoiceMessage(text) {
        // Add voice input to chat
        addChatMessage('user', `🎤 ${text}`);
        
        // Send to server for processing
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'voice',
                action: 'process',
                text: text,
                timestamp: Date.now()
            }));
        }
    }
    
    updateVoiceButton() {
        if (this.isListening) {
            voiceButton.textContent = '🔴 Stop';
            voiceButton.className = 'bg-red-500 hover:bg-red-600 px-4 py-2 rounded font-medium transition';
        } else {
            voiceButton.textContent = '🎤 Voice';
            voiceButton.className = 'bg-green-500 hover:bg-green-600 px-4 py-2 rounded font-medium transition';
        }
    }
}

// Play audio response
function playAudioResponse(audioData) {
    try {
        // Convert base64 to audio blob
        const audioBytes = atob(audioData);
        const arrayBuffer = new ArrayBuffer(audioBytes.length);
        const uint8Array = new Uint8Array(arrayBuffer);
        for (let i = 0; i < audioBytes.length; i++) {
            uint8Array[i] = audioBytes.charCodeAt(i);
        }
        
        const audioBlob = new Blob([arrayBuffer], { type: 'audio/wav' });
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        
        audio.play().catch(err => {
            console.error('Audio playback failed:', err);
        });
        
    } catch (err) {
        console.error('Error processing audio response:', err);
    }
}

// Initialize voice chat
let voiceChat;
try {
    voiceChat = new VoiceChat();
    console.log('Voice chat initialized:', {
        hasRecognition: !!voiceChat.recognition,
        hasAudioRecorder: !!voiceChat.audioRecorder,
        browser: navigator.userAgent
    });
} catch (err) {
    console.error('Failed to initialize voice chat:', err);
    addChatMessage('error', 'Voice chat initialization failed: ' + err.message);
}

// Voice button event listener
if (voiceButton && voiceChat) {
    voiceButton.addEventListener('click', () => {
        console.log('Voice button clicked, isListening:', voiceChat.isListening);
        if (voiceChat.isListening) {
            voiceChat.stopListening();
        } else {
            voiceChat.startListening();
        }
    });
} else {
    console.error('Voice button or voiceChat not initialized');
}

// Audio Recorder for Firefox/Safari
class AudioRecorder {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
    }
    
    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus'
            });
            
            this.audioChunks = [];
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                console.log('Audio recorded:', audioBlob.size, 'bytes');
                addChatMessage('system', `📼 Recorded ${Math.round(audioBlob.size / 1024)}KB of audio`);
                
                const audioBase64 = await this.blobToBase64(audioBlob);
                
                // Send to server for transcription
                if (ws && ws.readyState === WebSocket.OPEN) {
                    console.log('Sending audio to server...');
                    ws.send(JSON.stringify({
                        type: 'voice',
                        action: 'transcribe',
                        audio: audioBase64,
                        timestamp: Date.now()
                    }));
                    addChatMessage('system', '📡 Sending to server for transcription...');
                } else {
                    console.error('WebSocket not connected');
                    addChatMessage('error', 'WebSocket not connected');
                }
                
                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());
            };
            
            this.mediaRecorder.start();
            this.isRecording = true;
            
            return true;
        } catch (err) {
            console.error('Failed to start recording:', err);
            addChatMessage('error', 'Microphone access denied or not available');
            return false;
        }
    }
    
    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
        }
    }
    
    blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result.split(',')[1]);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }
}

// Initialize connection
connectWebSocket();

// Welcome message
addChatMessage('assistant', 'Welcome to Local AI Assistant! Type or click 🎤 Voice to talk. Try saying "Hello" or "/help"');