// WebSocket connection helper that works from any device
function connectWebSocket(onMessage, onOpen, onClose) {
    // Use the current host instead of hardcoded localhost
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;
    
    console.log('Connecting to WebSocket:', wsUrl);
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        if (onOpen) onOpen();
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (onMessage) onMessage(data);
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected');
        if (onClose) onClose();
        // Reconnect after 3 seconds
        setTimeout(() => connectWebSocket(onMessage, onOpen, onClose), 3000);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    return ws;
}