const state = {
  host: localStorage.getItem('wizytaHost') || 'http://127.0.0.1:8089',
  frontendLogs: [],
  backendLogs: '',
  lastHealth: null,
};

const $ = (id) => document.getElementById(id);

const hostInput = $('host');
const statusPill = $('status-pill');
const statusDetail = $('status-detail');
const backendValue = $('backend-value');
const modelValue = $('model-value');
const deviceValue = $('device-value');
const portValue = $('port-value');
const backendLogPreview = $('backend-log-preview');
const frontendLogBox = $('frontend-log-box');
const connectPanel = $('connect-panel');
const servicePanel = $('service-panel');

const log = (level, message, data) => {
  const entry = {
    time: new Date().toISOString(),
    level,
    message,
    data: data ?? null,
  };
  state.frontendLogs.push(entry);
  if (state.frontendLogs.length > 300) {
    state.frontendLogs.shift();
  }
  if (frontendLogBox) {
    const line = `[${entry.time}] [${level}] ${message}` + (data ? ` | ${JSON.stringify(data)}` : '');
    frontendLogBox.textContent = `${line}\n${frontendLogBox.textContent}`.trim();
  }
  if (level === 'error') {
    console.error(message, data || '');
  } else {
    console.log(message, data || '');
  }
};

const setStatus = (ok, title, subtitle) => {
  if (statusPill) {
    statusPill.textContent = title;
    statusPill.classList.toggle('good', ok);
  }
  if (statusDetail) {
    statusDetail.textContent = subtitle;
  }
};

const setHost = (value) => {
  state.host = value.trim();
  if (hostInput) {
    hostInput.value = state.host;
  }
  localStorage.setItem('wizytaHost', state.host);
  log('info', 'Host ustawiony', { host: state.host });
};

const fetchWithTimeout = async (url, options = {}, timeoutMs = 2500) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
      cache: 'no-store',
    });
    return res;
  } finally {
    clearTimeout(timeout);
  }
};

const updateHealthUI = (data) => {
  if (backendValue) backendValue.textContent = data.backend || '-';
  if (modelValue) modelValue.textContent = data.model || '-';
  if (deviceValue) deviceValue.textContent = data.device || '-';
  if (portValue) portValue.textContent = data.port ? String(data.port) : '-';
};

const checkHealth = async () => {
  try {
    const res = await fetchWithTimeout(`${state.host}/api/health`, { mode: 'cors' }, 3000);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    state.lastHealth = data;
    updateHealthUI(data);
    setStatus(true, 'Połączono', data.message || 'Powiernik działa poprawnie.');
    log('info', 'Powiernik online', data);
    return true;
  } catch (err) {
    setStatus(false, 'Brak połączenia', 'Uruchom Powiernika i kliknij „Połącz”.');
    log('error', 'Powiernik offline lub blokada przeglądarki', { error: String(err) });
    return false;
  }
};

const scanPorts = async () => {
  log('info', 'Skanowanie portów 8089-8100...');
  const ports = Array.from({ length: 12 }, (_, i) => 8089 + i);
  for (const port of ports) {
    const candidate = `${state.host.replace(/:\d+$/, '')}:${port}`;
    try {
      const res = await fetchWithTimeout(`${candidate}/api/health`, { mode: 'cors' }, 1200);
      if (res.ok) {
        setHost(candidate);
        await checkHealth();
        return;
      }
    } catch (err) { /* ignore */ }
  }
  log('warn', 'Nie znaleziono Powiernika na standardowych portach.');
};

const fetchBackendLogs = async () => {
  try {
    const res = await fetchWithTimeout(`${state.host}/api/debug/logs?tail=200`, { mode: 'cors' }, 4000);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    const text = data.lines ? data.lines.join('\n') : (data.stdout_lines || []).join('\n');
    state.backendLogs = text || JSON.stringify(data, null, 2);
    if (backendLogPreview) {
      backendLogPreview.textContent = state.backendLogs || 'Brak logów.';
    }
    log('info', 'Pobrano logi hosta', { lines: (data.lines || []).length });
  } catch (err) {
    if (backendLogPreview) {
      backendLogPreview.textContent = `Błąd pobierania logów: ${err}`;
    }
    log('error', 'Nie udało się pobrać logów hosta', { error: String(err) });
  }
};

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
    log('info', 'Skopiowano do schowka');
  } catch (err) {
    log('error', 'Nie udało się skopiować do schowka', { error: String(err) });
  }
};

const buildDebugBundle = () => {
  return JSON.stringify({
    generated_at: new Date().toISOString(),
    host: state.host,
    user_agent: navigator.userAgent,
    health: state.lastHealth,
    frontend_logs: state.frontendLogs,
    backend_logs: state.backendLogs,
  }, null, 2);
};

const openLocal = (path) => {
  const url = `${state.host}${path}`;
  window.open(url, '_blank', 'noopener');
  log('info', 'Otwarto lokalny adres', { url });
};

window.addEventListener('error', (event) => {
  log('error', 'Wyjątek frontu', { message: event.message, source: event.filename, line: event.lineno });
});

window.addEventListener('unhandledrejection', (event) => {
  log('error', 'Nieobsłużone odrzucenie', { reason: String(event.reason) });
});

if (hostInput) {
  hostInput.value = state.host;
}

const connectNow = $('connect-now');
const connectNow2 = $('connect-now-2');
const serviceToggle = $('service-toggle');
const openLocalBtn = $('open-local');
const scanPortsBtn = $('scan-ports');

if (connectNow && connectPanel) {
  connectNow.addEventListener('click', () => {
    connectPanel.classList.remove('hidden');
    connectPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    if (hostInput) {
      hostInput.focus();
    }
  });
}

if (connectNow2) {
  connectNow2.addEventListener('click', checkHealth);
}

if (serviceToggle && servicePanel) {
  serviceToggle.addEventListener('click', () => {
    servicePanel.classList.toggle('hidden');
    if (!servicePanel.classList.contains('hidden')) {
      servicePanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
}

const saveHostBtn = $('save-host');
if (saveHostBtn && hostInput) {
  saveHostBtn.addEventListener('click', () => setHost(hostInput.value));
}

const refreshStatusBtn = $('refresh-status');
if (refreshStatusBtn) {
  refreshStatusBtn.addEventListener('click', checkHealth);
}

const openHealthBtn = $('open-health');
if (openHealthBtn) {
  openHealthBtn.addEventListener('click', () => openLocal('/api/health'));
}

const fetchBackendLogsBtn = $('fetch-backend-logs');
if (fetchBackendLogsBtn) {
  fetchBackendLogsBtn.addEventListener('click', fetchBackendLogs);
}

const copyDebugBtn = $('copy-debug');
if (copyDebugBtn) {
  copyDebugBtn.addEventListener('click', () => copyToClipboard(buildDebugBundle()));
}

const clearLogsBtn = $('clear-logs');
if (clearLogsBtn && frontendLogBox) {
  clearLogsBtn.addEventListener('click', () => {
    state.frontendLogs = [];
    frontendLogBox.textContent = '';
  });
}

if (openLocalBtn) {
  openLocalBtn.addEventListener('click', () => openLocal('/'));
}

if (scanPortsBtn) {
  scanPortsBtn.addEventListener('click', scanPorts);
}

log('info', 'Front uruchomiony');
checkHealth();
