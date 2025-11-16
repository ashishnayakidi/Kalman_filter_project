// Chat functionality
document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.getElementById('chat-container');
    const chatMessages = document.getElementById('chat-messages');
    const questionInput = document.getElementById('question-input');
    const sendBtn = document.getElementById('send-btn');
    const clearBtn = document.getElementById('clear-btn');

    // Load chat history from sessionStorage
    let messages = JSON.parse(sessionStorage.getItem('chatMessages') || '[]');
    renderMessages();

    function renderMessages() {
        chatMessages.innerHTML = '';
        messages.forEach(msg => {
            addMessage(msg.role, msg.content, false);
        });
        scrollToBottom();
    }

    function addMessage(role, content, save = true) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `mb-3 ${role === 'user' ? 'text-end' : 'text-start'}`;
        
        const bubble = document.createElement('div');
        bubble.className = `d-inline-block p-3 rounded ${role === 'user' ? 'bg-primary text-white' : 'bg-light'}`;
        bubble.style.maxWidth = '70%';
        bubble.innerHTML = content.replace(/\n/g, '<br>');
        
        messageDiv.appendChild(bubble);
        chatMessages.appendChild(messageDiv);
        
        if (save) {
            messages.push({ role, content });
            sessionStorage.setItem('chatMessages', JSON.stringify(messages));
        }
        
        scrollToBottom();
    }

    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    async function sendQuestion() {
        const question = questionInput.value.trim();
        if (!question) return;

        // Add user message
        addMessage('user', question);
        questionInput.value = '';

        // Show loading
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'mb-3 text-start';
        loadingDiv.id = 'loading-message';
        loadingDiv.innerHTML = '<div class="d-inline-block p-3 rounded bg-light"><em>Thinking...</em></div>';
        chatMessages.appendChild(loadingDiv);
        scrollToBottom();

        try {
            const response = await fetch('/api/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ question: question })
            });

            const data = await response.json();
            
            // Remove loading
            loadingDiv.remove();

            if (data.error) {
                addMessage('assistant', `Error: ${data.error}`);
            } else {
                // Convert markdown-like formatting to HTML
                let answer = data.answer || '';
                
                // Debug: log response length
                console.log('Response received:', answer.length, 'chars');
                
                // Better markdown to HTML conversion
                // Handle headers first (most specific to least)
                answer = answer.replace(/^#### (.*$)/gm, '<h6>$1</h6>');
                answer = answer.replace(/^### (.*$)/gm, '<h5>$1</h5>');
                answer = answer.replace(/^## (.*$)/gm, '<h4>$1</h4>');
                answer = answer.replace(/^# (.*$)/gm, '<h3>$1</h3>');
                
                // Handle bold and italic
                answer = answer.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                answer = answer.replace(/\*(.*?)\*/g, '<em>$1</em>');
                
                // Handle lists (convert - or * to list items)
                const lines = answer.split('\n');
                let inList = false;
                let processedLines = [];
                
                for (let line of lines) {
                    const trimmed = line.trim();
                    if (trimmed.match(/^[-*]\s/)) {
                        if (!inList) {
                            processedLines.push('<ul>');
                            inList = true;
                        }
                        processedLines.push('<li>' + trimmed.substring(2) + '</li>');
                    } else {
                        if (inList) {
                            processedLines.push('</ul>');
                            inList = false;
                        }
                        if (trimmed) {
                            processedLines.push(trimmed);
                        }
                    }
                }
                if (inList) {
                    processedLines.push('</ul>');
                }
                
                answer = processedLines.join('\n');
                
                // Convert remaining newlines to breaks
                answer = answer.replace(/\n/g, '<br>');
                
                addMessage('assistant', answer);
            }
        } catch (error) {
            loadingDiv.remove();
            addMessage('assistant', `Sorry, I encountered an error: ${error.message}`);
        }
    }

    sendBtn.addEventListener('click', sendQuestion);
    questionInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendQuestion();
        }
    });

    clearBtn.addEventListener('click', function() {
        messages = [];
        sessionStorage.removeItem('chatMessages');
        renderMessages();
    });
});
