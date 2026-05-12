(function () {
  'use strict';

  const css = `
    #dj-banner {
      position: fixed;
      top: 0; left: 0; right: 0;
      z-index: 9999;
      transform: translateY(-100%);
      transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    #dj-banner.show { transform: translateY(0); }
    #dj-banner-body {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      padding: 0.65rem 1.2rem;
      font-size: 0.82rem;
      font-weight: 600;
      letter-spacing: 0.02em;
    }
    #dj-banner.loading #dj-banner-body {
      background: #1a1400;
      border-bottom: 2px solid #ffaa00;
      color: #ffaa00;
    }
    #dj-banner.success #dj-banner-body {
      background: #0d1f0d;
      border-bottom: 2px solid #44aa44;
      color: #77cc77;
    }
    ._dj_spin {
      width: 11px; height: 11px;
      border: 2px solid rgba(255,170,0,0.25);
      border-top-color: #ffaa00;
      border-radius: 50%;
      animation: _dj_spin 0.7s linear infinite;
      flex-shrink: 0;
    }
    @keyframes _dj_spin { to { transform: rotate(360deg); } }
  `;
  const styleEl = document.createElement('style');
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  const banner = document.createElement('div');
  banner.id = 'dj-banner';
  banner.innerHTML = '<div id="dj-banner-body"></div>';
  document.body.prepend(banner);
  const body = document.getElementById('dj-banner-body');

  let state      = 'hidden';
  let hideTimer  = null;
  let lastBtTs   = parseInt(localStorage.getItem('_dj_bt')   || '0');
  let lastPlayTs = parseInt(localStorage.getItem('_dj_play') || '0');

  function show(newState, html) {
    if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
    body.innerHTML = html;
    banner.className = newState + ' show';
    state = newState;
  }

  function hide() {
    banner.classList.remove('show');
    state = 'hidden';
    hideTimer = null;
  }

  async function poll() {
    try {
      const res  = await fetch('/api/status/banner');
      const data = await res.json();
      if (!data.ok) return;

      const { bt_ts, play_ts } = data;
      const now = Math.floor(Date.now() / 1000);

      // Play recente e novo → sucesso (janela de 30s para evitar repetir ao abrir a página)
      if (play_ts > lastPlayTs && (now - play_ts) < 30) {
        lastPlayTs = play_ts;
        lastBtTs   = Math.max(lastBtTs, bt_ts);
        localStorage.setItem('_dj_play', lastPlayTs);
        localStorage.setItem('_dj_bt',   lastBtTs);
        show('success', '🎵 Tocando na caixinha!');
        hideTimer = setTimeout(hide, 5000);
        return;
      }

      // BT recente e novo, play ainda pendente → loading
      if (bt_ts > lastBtTs && (now - bt_ts) < 180 && play_ts <= bt_ts) {
        lastBtTs = bt_ts;
        localStorage.setItem('_dj_bt', lastBtTs);
        if (state !== 'success') {
          show('loading', '<span class="_dj_spin"></span>Dando play na fila...');
        }
        return;
      }

      // Estava em loading e play chegou (pode ter passado mais de 30s)
      if (state === 'loading' && play_ts > lastPlayTs) {
        lastPlayTs = play_ts;
        localStorage.setItem('_dj_play', lastPlayTs);
        show('success', '🎵 Tocando na caixinha!');
        hideTimer = setTimeout(hide, 5000);
      }

    } catch (_) {}
  }

  poll();
  setInterval(poll, 4000);
}());
