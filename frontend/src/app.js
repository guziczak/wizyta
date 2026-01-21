const state = {
  host: localStorage.getItem('wizytaHost') || 'http://127.0.0.1:8089',
  frontendLogs: [],
  backendLogs: '',
  lastHealth: null,
};

const $ = (id) => document.getElementById(id);
const hostInput = $('host');
const statusDot = $('status-dot');
const statusTitle = $('status-title');
const statusSub = $('status-sub');
const heroMeta = $('hero-meta');
const backendValue = $('backend-value');
const modelValue = $('model-value');
const deviceValue = $('device-value');
const portValue = $('port-value');
const backendLogPreview = $('backend-log-preview');
const frontendLogBox = $('frontend-log-box');

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
  const line = `[${entry.time}] [${level}] ${message}` + (data ? ` | ${JSON.stringify(data)}` : '');
  if (frontendLogBox) {
    frontendLogBox.textContent = `${line}\n${frontendLogBox.textContent}`.trim();
  }
  if (level === 'error') {
    console.error(message, data || '');
  } else {
    console.log(message, data || '');
  }
};

const setStatus = (ok, title, subtitle) => {
  statusDot.classList.toggle('good', ok);
  statusTitle.textContent = title;
  statusSub.textContent = subtitle;
};

const setHost = (value) => {
  state.host = value.trim();
  hostInput.value = state.host;
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
  backendValue.textContent = data.backend || '—';
  modelValue.textContent = data.model || '—';
  deviceValue.textContent = data.device || '—';
  portValue.textContent = data.port ? String(data.port) : '—';
};

const checkHealth = async () => {
  const start = new Date();
  heroMeta.textContent = `Ostatnie sprawdzenie: ${start.toLocaleTimeString('pl-PL')}`;
  try {
    const res = await fetchWithTimeout(`${state.host}/api/health`, { mode: 'cors' }, 3000);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    state.lastHealth = data;
    updateHealthUI(data);
    setStatus(true, 'Połączono z Powiernikiem', data.message || 'Host odpowiada poprawnie.');
    log('info', 'Powiernik online', data);
    return true;
  } catch (err) {
    setStatus(false, 'Brak połączenia', 'Nie udało się pobrać /api/health.');
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
    } catch (err) {
      // ignore
    }
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
    backendLogPreview.textContent = state.backendLogs || 'Brak logów.';
    log('info', 'Pobrano logi hosta', { lines: (data.lines || []).length });
  } catch (err) {
    backendLogPreview.textContent = `Błąd pobierania logów: ${err}`;
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

hostInput.value = state.host;

$('save-host').addEventListener('click', () => setHost(hostInput.value));
$('connect-now').addEventListener('click', checkHealth);
$('refresh-status').addEventListener('click', checkHealth);
$('scan-ports').addEventListener('click', scanPorts);
$('open-local').addEventListener('click', () => openLocal('/'));
$('open-health').addEventListener('click', () => openLocal('/api/health'));
$('fetch-backend-logs').addEventListener('click', fetchBackendLogs);
$('copy-frontend-logs').addEventListener('click', () => copyToClipboard(JSON.stringify(state.frontendLogs, null, 2)));
$('copy-debug').addEventListener('click', () => copyToClipboard(buildDebugBundle()));
$('open-logs').addEventListener('click', fetchBackendLogs);
$('clear-logs').addEventListener('click', () => {
  state.frontendLogs = [];
  frontendLogBox.textContent = '';
});

Array.from(document.querySelectorAll('[data-open]')).forEach((el) => {
  el.addEventListener('click', () => openLocal(el.getAttribute('data-open')));
});

log('info', 'Front uruchomiony');
checkHealth();
