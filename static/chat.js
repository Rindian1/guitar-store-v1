// Chat Widget JavaScript
class ChatWidget {
    constructor() {
        this.isOpen = false;
        this.conversationId = null;
        this.isLoading = false;
        this.init();
    }

    init() {
        this.cacheElements();
        this.bindEvents();
        this.checkAuthStatus();
    }

    cacheElements() {
        this.elements = {
            widget: document.getElementById('chat-widget'),
            toggle: document.getElementById('chat-toggle'),
            container: document.getElementById('chat-container'),
            minimize: document.getElementById('chat-minimize'),
            close: document.getElementById('chat-close'),
            messages: document.getElementById('chat-messages'),
            input: document.getElementById('chat-input'),
            sendBtn: document.getElementById('chat-send'),
            typingIndicator: document.getElementById('typing-indicator'),
            charCount: document.getElementById('char-count'),
            suggestionBtns: document.querySelectorAll('.suggestion-btn')
        };
    }

    bindEvents() {
        // Toggle chat
        this.elements.toggle.addEventListener('click', () => this.toggleChat());
        this.elements.minimize.addEventListener('click', () => this.minimizeChat());
        this.elements.close.addEventListener('click', () => this.closeChat());

        // Message input
        this.elements.input.addEventListener('input', (e) => this.handleInput(e));
        this.elements.input.addEventListener('keydown', (e) => this.handleKeyDown(e));
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());

        // Suggestion buttons
        this.elements.suggestionBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const message = btn.getAttribute('data-message');
                this.setInput(message);
                this.sendMessage();
            });
        });

        // Click outside to close (on mobile)
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 480 && 
                this.isOpen && 
                !this.elements.widget.contains(e.target)) {
                this.minimizeChat();
            }
        });
    }

    checkAuthStatus() {
        // Check if user is authenticated
        fetch('/profile')
            .then(response => {
                if (response.ok) {
                    this.isAuthenticated = true;
                } else {
                    this.isAuthenticated = false;
                    this.showLoginPrompt();
                }
            })
            .catch(() => {
                this.isAuthenticated = false;
                this.showLoginPrompt();
            });
    }

    showLoginPrompt() {
        const welcomeDiv = this.elements.messages.querySelector('.chat-welcome');
        if (welcomeDiv) {
            welcomeDiv.innerHTML = `
                <div class="welcome-message">
                    <p>👋 Welcome! Please <a href="/login" style="color: #667eea; text-decoration: none;">log in</a> or 
                    <a href="/register" style="color: #667eea; text-decoration: none;">create an account</a> to use the chat assistant.</p>
                </div>
            `;
            this.elements.input.disabled = true;
            this.elements.input.placeholder = 'Please log in to chat...';
            this.elements.sendBtn.disabled = true;
        }
    }

    toggleChat() {
        if (this.isOpen) {
            this.minimizeChat();
        } else {
            this.openChat();
        }
    }

    openChat() {
        this.elements.container.classList.remove('hidden');
        this.isOpen = true;
        this.elements.input.focus();
        
        // Start new conversation if authenticated
        if (this.isAuthenticated && !this.conversationId) {
            this.startNewConversation();
        }
    }

    minimizeChat() {
        this.elements.container.classList.add('hidden');
        this.isOpen = false;
    }

    closeChat() {
        this.elements.container.classList.add('hidden');
        this.isOpen = false;
        this.clearMessages();
        this.conversationId = null;
    }

    clearMessages() {
        const messages = this.elements.messages.querySelectorAll('.message');
        messages.forEach(msg => msg.remove());
    }

    startNewConversation() {
        if (!this.isAuthenticated) return;

        fetch('/chat/new', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.conversation_id) {
                this.conversationId = data.conversation_id;
            } else {
                console.error('Failed to start conversation');
            }
        })
        .catch(error => console.error('Error starting conversation:', error));
    }

    handleInput(e) {
        const text = e.target.value;
        this.elements.charCount.textContent = text.length;
        this.elements.sendBtn.disabled = !text.trim() || this.isLoading;

        // Auto-resize textarea
        this.elements.input.style.height = 'auto';
        this.elements.input.style.height = Math.min(this.elements.input.scrollHeight, 100) + 'px';
    }

    handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendMessage();
        }
    }

    setInput(text) {
        this.elements.input.value = text;
        this.elements.charCount.textContent = text.length;
        this.elements.sendBtn.disabled = !text.trim() || this.isLoading;
        this.elements.input.style.height = 'auto';
        this.elements.input.style.height = Math.min(this.elements.input.scrollHeight, 100) + 'px';
    }

    sendMessage() {
        const message = this.elements.input.value.trim();
        if (!message || this.isLoading || !this.isAuthenticated) return;

        // Add user message to chat
        this.addMessage(message, 'user');
        
        // Clear input
        this.setInput('');
        
        // Show typing indicator
        this.setLoading(true);
        
        // Send to server
        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify({
                message: message,
                conversation_id: this.conversationId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                this.addMessage('Sorry, I encountered an error. Please try again.', 'assistant');
            } else {
                this.addMessage(data.response, 'assistant');
                if (data.conversation_id) {
                    this.conversationId = data.conversation_id;
                }
            }
        })
        .catch(error => {
            console.error('Error sending message:', error);
            this.addMessage('Sorry, I\'m having trouble connecting. Please try again in a moment.', 'assistant');
        })
        .finally(() => {
            this.setLoading(false);
        });
    }

    addMessage(content, role) {
        // Remove welcome message if it exists
        const welcomeDiv = this.elements.messages.querySelector('.chat-welcome');
        if (welcomeDiv) {
            welcomeDiv.remove();
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = role === 'user' ? 'U' : 'AI';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.textContent = content;
        
        const messageTime = document.createElement('div');
        messageTime.className = 'message-time';
        messageTime.textContent = this.getCurrentTime();
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(messageContent);
        messageContent.appendChild(messageTime);
        
        this.elements.messages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    setLoading(isLoading) {
        this.isLoading = isLoading;
        this.elements.sendBtn.disabled = isLoading || !this.elements.input.value.trim();
        
        if (isLoading) {
            this.elements.typingIndicator.classList.remove('hidden');
        } else {
            this.elements.typingIndicator.classList.add('hidden');
        }
    }

    scrollToBottom() {
        this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
    }

    getCurrentTime() {
        const now = new Date();
        return now.toLocaleTimeString('en-US', { 
            hour: 'numeric', 
            minute: '2-digit',
            hour12: true 
        });
    }

    getCSRFToken() {
        // Try to get CSRF token from meta tag or cookie
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            return metaTag.getAttribute('content');
        }
        
        // Fallback to cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrf_token') {
                return decodeURIComponent(value);
            }
        }
        
        return '';
    }

    // Public methods for external use
    reset() {
        this.closeChat();
        this.checkAuthStatus();
    }
}

// Initialize chat widget when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.chatWidget = new ChatWidget();
});

// Handle page navigation (for SPA-like behavior)
window.addEventListener('beforeunload', () => {
    if (window.chatWidget) {
        window.chatWidget.closeChat();
    }
});
