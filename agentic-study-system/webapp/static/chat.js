/**
 * WebSocket streaming chat client for real-time LLM interaction.
 * Connects to /ws/chat and displays streamed responses character-by-character.
 */

class StreamingChatClient {
  constructor(wsUrl, outputElement, statusCallback) {
    this.wsUrl = wsUrl;
    this.output = outputElement;
    this.onStatusChange = statusCallback || (() => {});
    this.ws = null;
    this.isConnected = false;
  }

  connect() {
    if (this.ws && this.isConnected) return;

    this.ws = new WebSocket(this.wsUrl);

    this.ws.onopen = () => {
      this.isConnected = true;
      this.onStatusChange('connected');
      console.log('[Chat] WebSocket connected');
    };

    this.ws.onmessage = (event) => {
      try {
        // Try to parse as JSON (control messages)
        const data = JSON.parse(event.data);

        if (data.error) {
          this.appendToOutput(`\n\n❌ 错误: ${data.error}\n\n`, 'error');
          this.onStatusChange('error');
        } else if (data.done) {
          this.onStatusChange('done');
          console.log('[Chat] Stream complete');
        }
      } catch (e) {
        // Not JSON, it's a text chunk - append directly
        this.appendToOutput(event.data, 'chunk');
      }
    };

    this.ws.onerror = (error) => {
      console.error('[Chat] WebSocket error:', error);
      this.onStatusChange('error');
    };

    this.ws.onclose = () => {
      this.isConnected = false;
      this.onStatusChange('disconnected');
      console.log('[Chat] WebSocket closed');
    };
  }

  send(message, mode = 'chat', ragMode = 'mix') {
    if (!this.isConnected) {
      console.warn('[Chat] Not connected, attempting to connect...');
      this.connect();
      setTimeout(() => this.send(message, mode, ragMode), 500);
      return;
    }

    this.ws.send(JSON.stringify({ message, mode, rag_mode: ragMode }));
  }

  appendToOutput(text, type = 'chunk') {
    // Create a temporary element to hold new content
    if (type === 'chunk') {
      // For streaming chunks, append to the last text node or create one
      const lastChild = this.output.lastChild;
      if (lastChild && lastChild.nodeType === Node.TEXT_NODE) {
        lastChild.textContent += text;
      } else {
        this.output.appendChild(document.createTextNode(text));
      }
    } else if (type === 'error') {
      const errorSpan = document.createElement('span');
      errorSpan.className = 'chat-error';
      errorSpan.textContent = text;
      this.output.appendChild(errorSpan);
    }

    // Auto-scroll to bottom
    this.output.scrollTop = this.output.scrollHeight;
  }

  clear() {
    this.output.innerHTML = '';
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.isConnected = false;
    }
  }
}

// Initialize chat UI when DOM is ready
function initStreamingChat() {
  const chatOutput = document.getElementById('rag-answer');
  const chatInput = document.getElementById('rag-question');
  const askButton = document.getElementById('rag-ask');
  const clearButton = document.getElementById('rag-clear');

  if (!chatOutput || !chatInput || !askButton) {
    console.warn('[Chat] Required elements not found, skipping init');
    return;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/chat`;

  const client = new StreamingChatClient(wsUrl, chatOutput, (status) => {
    askButton.disabled = status === 'streaming';

    if (status === 'connected') {
      console.log('[Chat] Ready to send messages');
    } else if (status === 'done') {
      askButton.disabled = false;
      chatOutput.appendChild(document.createElement('hr'));
    } else if (status === 'error') {
      askButton.disabled = false;
    }
  });

  // Connect on first interaction
  askButton.addEventListener('click', async (e) => {
    e.preventDefault();
    const question = chatInput.value.trim();
    if (!question) {
      toast('请先输入问题。');
      return;
    }

    // Show user's question
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-user-message';
    userDiv.textContent = `🧑 ${question}`;
    chatOutput.appendChild(userDiv);

    // Add assistant header
    const assistantDiv = document.createElement('div');
    assistantDiv.className = 'chat-assistant-message';
    assistantDiv.textContent = '🤖 ';
    chatOutput.appendChild(assistantDiv);

    // Temporarily replace output element to stream into assistant div
    const originalOutput = client.output;
    client.output = assistantDiv;

    // Connect and send (connects automatically if not connected)
    client.connect();
    const ragModeEl = document.getElementById('rag-mode');
    const ragMode = ragModeEl ? ragModeEl.value : 'mix';
    client.send(question, 'rag', ragMode);
    client.onStatusChange('streaming');

    // Restore original output after a moment
    setTimeout(() => {
      client.output = originalOutput;
    }, 100);

    // Clear input
    chatInput.value = '';
  });

  // Optional: clear button
  if (clearButton) {
    clearButton.addEventListener('click', () => {
      client.clear();
    });
  }

  // Disconnect when leaving the page
  window.addEventListener('beforeunload', () => {
    client.disconnect();
  });
}

// Auto-init when script loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initStreamingChat);
} else {
  initStreamingChat();
}
