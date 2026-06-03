(function () {
  'use strict';

  var script = document.currentScript || (function () {
    var scripts = document.getElementsByTagName('script');
    return scripts[scripts.length - 1];
  })();

  var API_KEY = script.getAttribute('data-key') || script.getAttribute('data-api-key') || '';
  var BASE_URL = script.getAttribute('data-base-url') || 'https://app.synapflow.com';
  var TITLE = script.getAttribute('data-title') || 'Support Chat';
  var COLOR = script.getAttribute('data-color') || '#6366f1';

  if (!API_KEY) { console.warn('[SynapFlow Widget] Missing data-key attribute'); return; }

  var SESSION_KEY = 'sf_widget_session';
  var sessionId = sessionStorage.getItem(SESSION_KEY);
  if (!sessionId) {
    sessionId = 'sess-' + Math.random().toString(36).slice(2) + '-' + Date.now();
    sessionStorage.setItem(SESSION_KEY, sessionId);
  }

  var lastReplyTs = null;
  var pollTimer = null;

  function post(path, data) {
    return fetch(BASE_URL + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
      body: JSON.stringify(data),
    });
  }

  function get(path) {
    return fetch(BASE_URL + path, { headers: { 'x-api-key': API_KEY } });
  }

  function appendMessage(container, text, sender) {
    var bubble = document.createElement('div');
    bubble.style.cssText = [
      'max-width:75%', 'padding:8px 12px', 'border-radius:12px',
      'margin-bottom:8px', 'word-break:break-word', 'font-size:13px', 'line-height:1.4',
      sender === 'user'
        ? 'background:' + COLOR + ';color:#fff;align-self:flex-end;margin-left:auto'
        : 'background:#f1f5f9;color:#1e293b;align-self:flex-start',
    ].join(';');
    bubble.textContent = text;
    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
  }

  function pollReplies(msgArea) {
    var url = '/api/widget/replies/' + encodeURIComponent(sessionId);
    if (lastReplyTs) url += '?since=' + encodeURIComponent(lastReplyTs);
    get(url).then(function (r) { return r.json(); }).then(function (data) {
      (data.replies || []).forEach(function (reply) {
        appendMessage(msgArea, reply.body, 'agent');
        lastReplyTs = reply.created_at;
      });
    }).catch(function () {});
  }

  function buildWidget() {
    var fab = document.createElement('button');
    fab.innerHTML = '&#x1F4AC;';
    fab.title = TITLE;
    fab.style.cssText = [
      'position:fixed', 'bottom:24px', 'right:24px', 'z-index:9999',
      'width:52px', 'height:52px', 'border-radius:50%', 'border:none',
      'background:' + COLOR, 'color:#fff', 'font-size:22px',
      'cursor:pointer', 'box-shadow:0 4px 14px rgba(0,0,0,.25)',
    ].join(';');

    var panel = document.createElement('div');
    panel.style.cssText = [
      'position:fixed', 'bottom:88px', 'right:24px', 'z-index:9999',
      'width:320px', 'background:#fff', 'border-radius:12px',
      'box-shadow:0 8px 32px rgba(0,0,0,.18)', 'display:none',
      'flex-direction:column', 'overflow:hidden',
    ].join(';');

    var header = document.createElement('div');
    header.style.cssText = 'background:' + COLOR + ';color:#fff;padding:12px 16px;font-weight:600;font-size:14px;';
    header.textContent = TITLE;

    var msgArea = document.createElement('div');
    msgArea.style.cssText = 'flex:1;overflow-y:auto;padding:12px;min-height:200px;max-height:320px;display:flex;flex-direction:column;';

    var inputRow = document.createElement('div');
    inputRow.style.cssText = 'display:flex;padding:8px;border-top:1px solid #e2e8f0;gap:6px;';

    var input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Type a message…';
    input.style.cssText = 'flex:1;border:1px solid #e2e8f0;border-radius:6px;padding:6px 10px;font-size:13px;outline:none;';

    var sendBtn = document.createElement('button');
    sendBtn.textContent = 'Send';
    sendBtn.style.cssText = 'background:' + COLOR + ';color:#fff;border:none;border-radius:6px;padding:6px 12px;cursor:pointer;font-size:13px;';

    function sendMessage() {
      var text = input.value.trim();
      if (!text) return;
      appendMessage(msgArea, text, 'user');
      input.value = '';
      post('/api/widget/message', {
        session_id: sessionId,
        message: text,
        page_url: window.location.href,
      }).catch(function () {});
    }

    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') sendMessage(); });

    inputRow.appendChild(input);
    inputRow.appendChild(sendBtn);
    panel.appendChild(header);
    panel.appendChild(msgArea);
    panel.appendChild(inputRow);

    var open = false;
    fab.addEventListener('click', function () {
      open = !open;
      panel.style.display = open ? 'flex' : 'none';
      if (open) {
        input.focus();
        if (!pollTimer) pollTimer = setInterval(function () { pollReplies(msgArea); }, 3000);
      } else {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    });

    document.body.appendChild(panel);
    document.body.appendChild(fab);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildWidget);
  } else {
    buildWidget();
  }
})();
