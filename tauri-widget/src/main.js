const { invoke } = window.__TAURI__.core;
const win = window.__TAURI__.window.getCurrentWindow();

const FLASH_SECONDS = 30;

const STATE_MAP = {
  idle:     { cls: 'blue',   blink: true,  label: 'Done' },
  idle_off: { cls: '',       blink: false, label: 'Idle' },
  working:  { cls: 'green',  blink: false, label: 'Working' },
  waiting:  { cls: 'yellow', blink: true,  label: 'Waiting' },
  blocked:  { cls: 'red',    blink: false, label: 'Blocked' },
};

const SRC_LABELS = {
  antigravity: 'ANTIGRAVITY', claude: 'CLAUDE', codex: 'CODEX',
  codexpp: 'CODEX++', cursor: 'CURSOR', none: 'AI',
};

function resolve(data) {
  let s = data.state || 'idle';
  if (s !== 'idle') return s;

  const sources = data.sources || {};
  if (!Object.keys(sources).length) return 'idle_off';

  const ua = data.updated_at || '';
  if (!ua) return 'idle_off';

  try {
    const age = (Date.now() - new Date(ua.replace('Z', '+00:00')).getTime()) / 1000;
    return (age >= 0 && age <= FLASH_SECONDS) ? 'idle' : 'idle_off';
  } catch {
    return 'idle_off';
  }
}

let prevKey = '';
let prevDs = '';
let currentDs = 'idle_off';
let pollCount = 0;

function render(data) {
  const ds = resolve(data);
  const src = data.source || 'none';
  const key = ds + '|' + src;

  currentDs = ds;
  const m = STATE_MAP[ds] || STATE_MAP.idle_off;

  document.getElementById('src').textContent = SRC_LABELS[src] || src.slice(0, 6) || 'AI';
  document.getElementById('status').textContent = m.label;
  document.body.dataset.state = ds;

  if (key !== prevKey) {
    const led = document.getElementById('led');
    led.className = 'light ' + m.cls + (m.blink ? ' blink' : '');
    prevKey = key;
  }

  if (ds !== prevDs) {
    invoke('update_tray_icon', { state: ds }).catch(() => {});
    prevDs = ds;
  }
}

async function poll() {
  try {
    const raw = await invoke('read_state');
    render(JSON.parse(raw));
  } catch (e) {
    console.error('poll error:', e);
  }

  pollCount++;
  if (pollCount % 10 === 0) {
    try {
      const pos = await win.outerPosition();
      await invoke('save_position', { x: pos.x, y: pos.y });
    } catch (_) {}
  }

  setTimeout(poll, 500);
}

poll();

// Double-click to focus the active AI tool window
document.getElementById('widget').addEventListener('dblclick', () => {
  invoke('focus_source').catch(() => {});
});

// Right-click context menu
document.addEventListener('contextmenu', e => {
  e.preventDefault();
  invoke('show_context_menu').catch(console.error);
});
