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
    #dj-banner.error #dj-banner-body {
      background: #1f0d0d;
      border-bottom: 2px solid #cc4444;
      color: #ff7777;
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
  let lastBtTs   = parseInt(localStorage.getItem('_dj_bt')        || '0');
  let lastPlayTs = parseInt(localStorage.getItem('_dj_play')      || '0');
  let lastDiscTs = parseInt(localStorage.getItem('_dj_disc')      || '0');
  let successAt  = parseInt(localStorage.getItem('_dj_success_at')|| '0');

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

  function enterSuccess() {
    successAt = Math.floor(Date.now() / 1000);
    localStorage.setItem('_dj_success_at', successAt);
    show('success', '🎵 Tocando na caixinha!');
    hideTimer = setTimeout(hide, 5000);
  }

  function enterLoading() {
    show('loading', '<span class="_dj_spin"></span>Dando play na fila...');
  }

  function enterError() {
    if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
    show('error', '⚠️ Caixinha desconectada. Reconectando...');
  }

  // Restaura estado ao navegar entre páginas usando localStorage
  const nowInit = Math.floor(Date.now() / 1000);
  if (successAt > 0 && (nowInit - successAt) < 5) {
    // Sucesso ainda dentro da janela de 5s — retoma com o tempo restante
    const remaining = Math.max(100, 5000 - (nowInit - successAt) * 1000);
    show('success', '🎵 Tocando na caixinha!');
    hideTimer = setTimeout(hide, remaining);
  } else if (lastDiscTs > lastPlayTs) {
    // Desconexão mais recente que último play → erro persiste entre navegações
    enterError();
  } else if (lastBtTs > 0 && (nowInit - lastBtTs) < 180 && lastPlayTs <= lastBtTs) {
    // BT conectou recentemente e play ainda não foi confirmado → loading
    enterLoading();
  }

  async function poll() {
    try {
      const res  = await fetch('/api/status/banner');
      const data = await res.json();
      if (!data.ok) return;

      const bt_ts        = data.bt_ts        || 0;
      const play_ts      = data.play_ts      || 0;
      const disconnect_ts = data.disconnect_ts || 0;
      const now = Math.floor(Date.now() / 1000);

      // Play recente e novo → sucesso (limpa qualquer estado de erro/loading)
      if (play_ts > lastPlayTs && (now - play_ts) < 30) {
        lastPlayTs = play_ts;
        lastBtTs   = Math.max(lastBtTs, bt_ts);
        localStorage.setItem('_dj_play', lastPlayTs);
        localStorage.setItem('_dj_bt',   lastBtTs);
        if (state !== 'success') enterSuccess();
        return;
      }

      // Desconexão nova e mais recente que o último play → erro
      if (disconnect_ts > lastDiscTs && disconnect_ts > lastPlayTs) {
        lastDiscTs = disconnect_ts;
        localStorage.setItem('_dj_disc', lastDiscTs);
        enterError();
        return;
      }

      // BT recente e novo, mais recente que a última desconexão → loading (sai do erro)
      if (bt_ts > lastBtTs && (now - bt_ts) < 180 && play_ts <= bt_ts && bt_ts >= disconnect_ts) {
        lastBtTs = bt_ts;
        localStorage.setItem('_dj_bt', lastBtTs);
        if (state !== 'success') enterLoading();
        return;
      }

      // Estava em loading e play chegou (pode ter passado mais de 30s)
      if (state === 'loading' && play_ts > lastPlayTs) {
        lastPlayTs = play_ts;
        localStorage.setItem('_dj_play', lastPlayTs);
        enterSuccess();
        return;
      }

      // Loading expirado sem play confirmado → vira erro ao invés de sumir silenciosamente
      if (state === 'loading' && lastBtTs > 0 && (now - lastBtTs) >= 180) {
        if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
        show('error', '⚠️ Não consegui dar play. Desligue e ligue a caixinha de novo.');
      }

    } catch (_) {}
  }

  poll();
  setInterval(poll, 4000);
}());
