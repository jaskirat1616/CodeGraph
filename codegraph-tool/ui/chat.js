(function() {
  var chatPanel = document.getElementById('chatPanel');
  var chatToggle = document.getElementById('chatToggle');
  var chatMessages = document.getElementById('chatMessages');
  var chatInput = document.getElementById('chatInput');
  var chatSend = document.getElementById('chatSend');
  var chatModelSelect = document.getElementById('chatModel');
  var chatStatus = document.getElementById('chatStatus');

  function loadModels() {
    chatStatus.textContent = 'Loading models…';
    fetch('/ollama/models')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        chatModelSelect.innerHTML = '';
        var models = data.models || [];
        var err = data.error || '';
        if (models.length === 0) {
          chatModelSelect.innerHTML = '<option value="">No models — run: ollama pull llama3.2</option>';
          chatStatus.textContent = err || 'No Ollama models. Run: ollama pull llama3.2';
          return;
        }
        chatStatus.textContent = models.length + ' model(s) available';
        models.forEach(function(m) {
          var opt = document.createElement('option');
          opt.value = m.name;
          opt.textContent = (m.light ? '⚡ ' : '') + m.name;
          chatModelSelect.appendChild(opt);
        });
      })
      .catch(function(e) {
        chatModelSelect.innerHTML = '<option value="">Ollama not available</option>';
        chatStatus.textContent = 'Ollama offline. Start Ollama and refresh.';
      });
  }

  function renderMarkdown(text) {
    if (!window.marked) return text;
    try {
      return window.marked.parse(String(text || ''), { gfm: true, breaks: true });
    } catch (_) { return text; }
  }

  function addMessage(role, content, meta) {
    var wrap = document.createElement('div');
    wrap.className = 'chat-msg chat-msg-' + role;
    var bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    if (role === 'assistant') {
      bubble.innerHTML = renderMarkdown(content);
    } else {
      bubble.textContent = content;
    }
    wrap.appendChild(bubble);
    if (meta && role === 'assistant' && (meta.cypher || meta.results)) {
      if (meta.cypher) {
        var cypherBlock = document.createElement('pre');
        cypherBlock.className = 'chat-code chat-code-cypher';
        cypherBlock.textContent = meta.cypher;
        wrap.appendChild(cypherBlock);
      }
      if (meta.results && meta.results.length) {
        var resBlock = document.createElement('pre');
        resBlock.className = 'chat-code chat-code-results';
        var resStr = JSON.stringify(meta.results, null, 2);
        if (resStr.length > 600) resStr = resStr.slice(0, 600) + '\n…';
        resBlock.textContent = resStr;
        wrap.appendChild(resBlock);
      }
    }
    chatMessages.appendChild(wrap);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return wrap;
  }

  function addThinkingBubble(msg) {
    var wrap = document.createElement('div');
    wrap.className = 'chat-msg chat-msg-assistant chat-msg-thinking';
    wrap.innerHTML = '<div class="chat-thinking"><span class="chat-thinking-dots"><i></i><i></i><i></i></span><span class="chat-thinking-text">' + (msg || 'Thinking…') + '</span></div>';
    chatMessages.appendChild(wrap);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return wrap;
  }

  function replaceThinkingWithMessage(thinkingEl, explanation, cypher, results) {
    thinkingEl.classList.remove('chat-msg-thinking');
    thinkingEl.innerHTML = '';
    var bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    bubble.innerHTML = renderMarkdown(explanation || '');
    thinkingEl.appendChild(bubble);
    if (cypher) {
      var cb = document.createElement('pre');
      cb.className = 'chat-code chat-code-cypher';
      cb.textContent = cypher;
      thinkingEl.appendChild(cb);
    }
    if (results && results.length) {
      var rb = document.createElement('pre');
      rb.className = 'chat-code chat-code-results';
      rb.textContent = JSON.stringify(results, null, 2).slice(0, 600) + (JSON.stringify(results).length > 600 ? '\n…' : '');
      thinkingEl.appendChild(rb);
    }
  }

  function appendToBubble(el, text) {
    var bubble = el.querySelector('.chat-bubble');
    if (bubble) bubble.textContent += text;
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
    chatStatus.textContent = '';
    addMessage('user', q);
    var thinkingEl = addThinkingBubble('Understanding your request…');

    fetch('/ollama/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, model: model })
    })
      .then(function(r) {
        if (!r.ok) throw new Error('Request failed');
        return r.body.getReader();
      })
      .then(function(reader) {
        var decoder = new TextDecoder();
        var buf = '';
            var cypher = '', results = [], explanation = '';
            function pump() {
              return reader.read().then(function(_ref) {
                var done = _ref.done;
                var value = _ref.value;
                if (done) {
                  chatSend.disabled = false;
                  return;
                }
                buf += decoder.decode(value, { stream: true });
                var lines = buf.split('\n');
                buf = lines.pop() || '';
                lines.forEach(function(line) {
                  if (!line.trim()) return;
                  try {
                    var obj = JSON.parse(line);
                    if (obj.stage === 'thinking') {
                      var txt = thinkingEl.querySelector('.chat-thinking-text');
                      if (txt) txt.textContent = obj.message || 'Thinking…';
                    } else if (obj.stage === 'cypher') {
                      cypher = obj.content || '';
                    } else if (obj.stage === 'results') {
                      results = obj.content || [];
                    } else if (obj.stage === 'explanation') {
                      explanation += obj.content || '';
                      thinkingEl.classList.remove('chat-msg-thinking');
                      thinkingEl.innerHTML = '';
                      var b = document.createElement('div');
                      b.className = 'chat-bubble chat-bubble-streaming';
                      b.innerHTML = renderMarkdown(explanation);
                      thinkingEl.appendChild(b);
                    } else if (obj.stage === 'command_result') {
                      var cmdOut = obj.content || '';
                      var cmdIds = obj.highlight_ids || [];
                      replaceThinkingWithMessage(thinkingEl, cmdOut, null, null);
                      if (cmdIds.length && typeof window.codegraphHighlightFromResults === 'function') {
                        window.codegraphHighlightFromResults([cmdIds]);
                      }
                      var cp = document.getElementById('chatPanel');
                      if (cp && cp.classList.contains('chat-open')) cp.classList.remove('chat-open');
                    } else if (obj.stage === 'done') {
                      replaceThinkingWithMessage(thinkingEl, explanation, cypher, results);
                      if (results && results.length && typeof window.codegraphHighlightFromResults === 'function') {
                        window.codegraphHighlightFromResults(results);
                        var chatPanel = document.getElementById('chatPanel');
                        if (chatPanel && chatPanel.classList.contains('chat-open')) {
                          chatPanel.classList.remove('chat-open');
                        }
                      }
                    } else if (obj.stage === 'error') {
                      replaceThinkingWithMessage(thinkingEl, 'Error: ' + (obj.content || 'Unknown'), null, null);
                    }
                  } catch (_) {}
                });
                chatMessages.scrollTop = chatMessages.scrollHeight;
                return pump();
              });
            }
        return pump();
      })
      .catch(function(err) {
        replaceThinkingWithMessage(thinkingEl, 'Error: ' + (err.message || err), null, null);
        chatSend.disabled = false;
      });
  }

  document.getElementById('chatRefreshModels').addEventListener('click', loadModels);
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
