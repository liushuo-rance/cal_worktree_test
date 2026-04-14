(function () {
  const messagesEl = document.getElementById('messages');
  const inputEl = document.getElementById('message-input');
  const formEl = document.getElementById('chat-form');
  const sendBtn = document.getElementById('send-btn');
  const clearBtn = document.getElementById('clear-btn');
  const emptyStateEl = document.getElementById('empty-state');

  const STREAM_URL = window.ASSISTANT_STREAM_URL || '/assistant/stream';
  const CLEAR_URL = window.ASSISTANT_CLEAR_URL || '/assistant/clear';

  function stripToolCall(text) {
    const idx = text.indexOf('TOOL_CALL');
    if (idx !== -1) {
      return text.slice(0, idx).trimEnd();
    }
    return text;
  }

  // Render any server-side assistant messages with markdown on load
  document.querySelectorAll('.assistant-bubble').forEach((bubble) => {
    const raw = stripToolCall(bubble.textContent.trim());
    if (raw && typeof marked !== 'undefined') {
      const html = marked.parse(raw, { breaks: true, gfm: true });
      bubble.innerHTML = typeof DOMPurify !== 'undefined'
        ? DOMPurify.sanitize(html)
        : html;
    }
  });

  // Auto-scroll to bottom on load
  scrollToBottom();

  // Auto-resize textarea
  inputEl.addEventListener('input', () => {
    inputEl.style.height = 'auto';
    const newHeight = Math.min(inputEl.scrollHeight, 200);
    inputEl.style.height = newHeight + 'px';
  });

  // Enter sends, Shift+Enter inserts newline
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      formEl.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    }
  });

  formEl.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text) return;

    // Remove empty state if present
    if (emptyStateEl) {
      emptyStateEl.remove();
    }

    appendUserMessage(text);
    inputEl.value = '';
    inputEl.style.height = 'auto';
    setInputDisabled(true);

    const turn = appendAssistantTurn();
    let markdownText = '';
    let toolIndicator = null;

    try {
      const response = await fetch(STREAM_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });

      if (!response.ok) {
        throw new Error('请求失败，请稍后重试');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        // Normalize CRLF to LF before splitting SSE frames
        const normalized = buffer.replace(/\r\n/g, '\n');
        const lines = normalized.split('\n\n');
        buffer = lines.pop() || '';

        for (const chunk of lines) {
          const dataMatch = chunk.match(/^data:\s*(.+)$/m);
          if (!dataMatch) continue;

          let event;
          try {
            event = JSON.parse(dataMatch[1]);
          } catch (err) {
            console.warn('SSE JSON parse error', err);
            continue;
          }

          if (event.type === 'delta' && typeof event.content === 'string') {
            markdownText += event.content;
            updateAssistantMarkdown(turn.bubble, stripToolCall(markdownText));
            if (toolIndicator) {
              hideToolIndicator(toolIndicator);
              toolIndicator = null;
            }
          } else if (event.type === 'status') {
            if (event.status === 'calling_api') {
              if (!toolIndicator) {
                toolIndicator = showToolIndicator(turn.bubble, event.message || ('正在调用 ' + (event.api_name || 'API') + '...'));
              } else {
                toolIndicator.querySelector('.tool-text').textContent = event.message || ('正在调用 ' + (event.api_name || 'API') + '...');
              }
            } else if (event.status === 'thinking') {
              if (!toolIndicator) {
                toolIndicator = showThinkingIndicator(turn.bubble, event.message || 'AI 正在思考...');
              } else {
                const textEl = toolIndicator.querySelector('.thinking-text');
                if (textEl) textEl.textContent = event.message || 'AI 正在思考...';
              }
            }
          } else if (event.type === 'tool_call_record') {
            appendToolCallRecord(turn.wrapper, event.arguments);
            if (toolIndicator) {
              hideToolIndicator(toolIndicator);
              toolIndicator = null;
            }
          } else if (event.type === 'tool_result') {
            if (toolIndicator) {
              hideToolIndicator(toolIndicator);
              toolIndicator = null;
            }
          } else if (event.type === 'done') {
            if (toolIndicator) {
              hideToolIndicator(toolIndicator);
              toolIndicator = null;
            }
            if (event.full_text) {
              markdownText = event.full_text;
              updateAssistantMarkdown(turn.bubble, markdownText);
            }
          } else if (event.type === 'error') {
            if (toolIndicator) {
              hideToolIndicator(toolIndicator);
              toolIndicator = null;
            }
            turn.bubble.innerHTML = '<p style="color: #ba1a1a; margin: 0;">' + escapeHtml(event.message || '发生错误') + '</p>';
          }
        }
      }

      // Finalize markdown
      if (markdownText) {
        updateAssistantMarkdown(turn.bubble, stripToolCall(markdownText));
      }
    } catch (err) {
      console.error('Stream error:', err);
      turn.bubble.innerHTML = '<p style="color: #ba1a1a; margin: 0;">' + escapeHtml(err.message || '网络错误，请稍后重试') + '</p>';
    } finally {
      if (toolIndicator) {
        hideToolIndicator(toolIndicator);
      }
      setInputDisabled(false);
      inputEl.focus();
    }
  });

  clearBtn.addEventListener('click', async () => {
    try {
      const res = await fetch(CLEAR_URL, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        messagesEl.innerHTML = '';
        const empty = document.createElement('div');
        empty.id = 'empty-state';
        empty.className = 'empty-state';
        empty.innerHTML =
          '<div class="empty-state__icon">' +
          '<span class="material-symbols-outlined">smart_toy</span>' +
          '</div>' +
          '<p class="empty-state__title">有什么可以帮您的？</p>' +
          '<p class="empty-state__hint">可查询加班记录、生成统计报表、分析调休余额……</p>';
        messagesEl.appendChild(empty);
      } else {
        alert('清空失败，请稍后重试');
      }
    } catch (err) {
      console.error('Clear error:', err);
      alert('清空失败，请稍后重试');
    }
  });

  function appendUserMessage(text) {
    const wrapper = document.createElement('div');
    wrapper.className = 'msg-row msg-row--user';
    wrapper.innerHTML =
      '<div class="msg-bubble--user">' +
      '<p class="whitespace-pre-wrap"></p>' +
      '</div>' +
      '<div class="user-avatar">我</div>';
    wrapper.querySelector('p').textContent = text;
    messagesEl.appendChild(wrapper);
    scrollToBottom();
  }

  function appendToolCallRecord(turnWrapper, argumentsObj) {
    const record = document.createElement('div');
    record.className = 'tool-record';
    let argsText = '';
    if (argumentsObj) {
      argsText = JSON.stringify(argumentsObj);
      if (argsText.length > 60) {
        argsText = argsText.slice(0, 60) + '...';
      }
    }
    record.innerHTML =
      '<span class="material-symbols-outlined">build_circle</span>' +
      '<span><code>' + escapeHtml(argsText) + '</code></span>';
    // Insert before the bubble so it appears above
    turnWrapper.insertBefore(record, turnWrapper.querySelector('.msg-bubble--ai'));
    scrollToBottom();
  }

  function appendAssistantTurn() {
    const row = document.createElement('div');
    row.className = 'msg-row msg-row--ai';

    const avatar = document.createElement('div');
    avatar.className = 'ai-avatar';
    avatar.innerHTML = '<span class="material-symbols-outlined text-base">auto_awesome</span>';

    const wrapper = document.createElement('div');
    wrapper.className = 'assistant-turn';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble--ai assistant-bubble';
    bubble.innerHTML =
      '<div class="wave-bars">' +
      '<span class="wave-bar"></span>' +
      '<span class="wave-bar"></span>' +
      '<span class="wave-bar"></span>' +
      '</div>';

    wrapper.appendChild(bubble);
    row.appendChild(avatar);
    row.appendChild(wrapper);
    messagesEl.appendChild(row);
    scrollToBottom();
    return { row, wrapper, bubble };
  }

  function updateAssistantMarkdown(bubble, markdown) {
    if (typeof marked !== 'undefined') {
      const html = marked.parse(markdown, { breaks: true, gfm: true });
      bubble.innerHTML = typeof DOMPurify !== 'undefined'
        ? DOMPurify.sanitize(html)
        : html;
    } else {
      bubble.innerHTML = '<p>' + escapeHtml(markdown).replace(/\n/g, '<br>') + '</p>';
    }
    scrollToBottom();
  }

  function showThinkingIndicator(bubble, text) {
    const indicator = document.createElement('div');
    indicator.className = 'thinking-indicator';
    indicator.innerHTML =
      '<div class="wave-bars">' +
      '<span class="wave-bar"></span>' +
      '<span class="wave-bar"></span>' +
      '<span class="wave-bar"></span>' +
      '</div>' +
      '<span class="thinking-text">' + escapeHtml(text) + '</span>';
    bubble.appendChild(indicator);
    scrollToBottom();
    return indicator;
  }

  function showToolIndicator(bubble, text) {
    const indicator = document.createElement('div');
    indicator.className = 'tool-indicator';
    indicator.innerHTML =
      '<span class="spinner"></span>' +
      '<span class="tool-text">' + escapeHtml(text) + '</span>';
    bubble.appendChild(indicator);
    scrollToBottom();
    return indicator;
  }

  function hideToolIndicator(indicator) {
    if (indicator && indicator.parentNode) {
      indicator.remove();
    }
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function setInputDisabled(disabled) {
    inputEl.disabled = disabled;
    sendBtn.disabled = disabled;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
})();
