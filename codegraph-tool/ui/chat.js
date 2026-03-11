(function() {
  var chatPanel = document.getElementById('chatPanel');
  var chatToggle = document.getElementById('chatToggle');
  var chatMessages = document.getElementById('chatMessages');
  var chatInput = document.getElementById('chatInput');
  var chatSend = document.getElementById('chatSend');
  var chatModelSelect = document.getElementById('chatModel');
  var chatStatus = document.getElementById('chatStatus');

  function loadModels() {
    fetch('/ollama/models')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        chatModelSelect.innerHTML = '';
        var models = data.models || [];
        if (models.length === 0) {
          chatModelSelect.innerHTML = '<option value="">No models — run: ollama pull llama3.2</option>';
          chatStatus.textContent = 'No Ollama models';
          return;
        }
        chatStatus.textContent = '';
        models.forEach(function(m) {
          var opt = document.createElement('option');
          opt.value = m.name;
          opt.textContent = (m.light ? '⚡ ' : '') + m.name;
          chatModelSelect.appendChild(opt);
        });
      })
      .catch(function() {
        chatModelSelect.innerHTML = '<option value="">Ollama not available</option>';
        chatStatus.textContent = 'Ollama offline';
      });
  }

  function addMessage(role, content, meta) {
    var wrap = document.createElement('div');
    wrap.className = 'chat-msg chat-msg-' + role;
    var bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    bubble.textContent = content;
    wrap.appendChild(bubble);
    if (meta && role === 'assistant' && (meta.cypher || meta.results)) {
      var block = document.createElement('pre');
      block.className = 'chat-code';
      var parts = [];
      if (meta.cypher) parts.push('Cypher:\n' + meta.cypher);
      if (meta.results) {
        var resStr = JSON.stringify(meta.results, null, 2);
        if (resStr.length > 800) resStr = resStr.slice(0, 800) + '\n...';
        parts.push('\nResults:\n' + resStr);
      }
      block.textContent = parts.join('\n');
      wrap.appendChild(block);
    }
    chatMessages.appendChild(wrap);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function sendMessage() {
    var q = (chatInput.value || '').trim();
    if (!q) return;
    var model = chatModelSelect.value;
    if (!model) {
      chatStatus.textContent = 'Select a model first';
      return;
    }
    chatInput.value = '';
    chatSend.disabled = true;
    chatStatus.textContent = 'Thinking…';
    addMessage('user', q);
    fetch('/ollama/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, model: model })
    })
      .then(function(r) {
        if (!r.ok) return r.json().then(function(e) { throw new Error(e.detail || e.error || 'Error'); });
        return r.json();
      })
      .then(function(data) {
        addMessage('assistant', data.explanation || 'No explanation.', {
          cypher: data.cypher,
          results: data.results
        });
        chatStatus.textContent = '';
      })
      .catch(function(err) {
        addMessage('assistant', 'Error: ' + (err.message || err), null);
        chatStatus.textContent = 'Error';
      })
      .finally(function() {
        chatSend.disabled = false;
      });
  }

  chatToggle.addEventListener('click', function(e) {
    e.preventDefault();
    chatPanel.classList.toggle('chat-open');
  });
  chatSend.addEventListener('click', sendMessage);
  chatInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  loadModels();
})();
