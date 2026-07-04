/**
 * Telegram AI Agent — Frontend v3 (Neon Glass + Tabs)
 */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// Поля
const fieldApiId         = $('#fieldApiId');
const fieldApiHash       = $('#fieldApiHash');
const fieldOpenaiKey     = $('#fieldOpenaiKey');
const fieldBaseUrl       = $('#fieldBaseUrl');
const fieldModel         = $('#fieldModel');
const fieldApiFormat     = $('#fieldApiFormat');
const fieldContacts      = $('#fieldContacts');
const fieldPrompt        = $('#fieldPrompt');
const fieldMinDelay      = $('#fieldMinDelay');
const fieldMaxDelay      = $('#fieldMaxDelay');
const fieldContextEnabled = $('#fieldContextEnabled');
const fieldContextMsgs    = $('#fieldContextMessages');

// UI
const logPanel   = $('#logPanel');
const btnStart   = $('#btnStart');
const btnStop    = $('#btnStop');
const agentPill  = $('#agentPill');
const wsPill     = $('#wsPill');
const modelInfo  = $('#modelInfo');
const apiUrlInfo = $('#apiUrlInfo');

let ws = null;
let reconnectTimer = null;

// ============================================================
// Утилиты
// ============================================================
function timeNow() {
    return new Date().toLocaleTimeString('ru-RU', { hour12: false });
}
function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}
function showToast(message, type = 'success') {
    const container = $('#toast-container');
    const el = document.createElement('div');
    el.className = `toast-item ${type}`;
    const icons = { success: 'bi-check-circle', error: 'bi-x-circle', info: 'bi-info-circle' };
    el.innerHTML = `<i class="bi ${icons[type] || icons.info}"></i><span>${esc(message)}</span>`;
    el.onclick = () => dismissToast(el);
    container.appendChild(el);
    setTimeout(() => dismissToast(el), 3500);
}
function dismissToast(el) {
    el.style.animation = 'slideOut 0.3s ease forwards';
    setTimeout(() => el.remove(), 300);
}
function togglePassword(fieldId, btn) {
    const f = document.getElementById(fieldId);
    const icon = btn.querySelector('i');
    if (f.type === 'password') { f.type = 'text'; icon.className = 'bi bi-eye-slash'; }
    else { f.type = 'password'; icon.className = 'bi bi-eye'; }
}

// ============================================================
// Вкладки
// ============================================================
function initTabs() {
    $$('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;
            $$('.tab-btn').forEach(b => b.classList.remove('active'));
            $$('.tab-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('tab-' + target).classList.add('active');
        });
    });
}

// ============================================================
// Логи
// ============================================================
function addLogEntry(entry) {
    const { type, text, sender, timestamp } = entry;
    const div = document.createElement('div');
    div.className = `log-entry type-${type || 'info'}`;
    const time = timestamp || timeNow();
    const senderHtml = sender ? `<span class="log-sender">[${esc(sender)}]</span>` : '';
    div.innerHTML = `
        <span class="log-time">${esc(time)}</span>
        <span class="log-badge">${esc(type || 'info')}</span>
        ${senderHtml}
        <span class="log-text">${esc(text)}</span>
    `;
    logPanel.appendChild(div);
    logPanel.scrollTop = logPanel.scrollHeight;
    while (logPanel.children.length > 500) logPanel.removeChild(logPanel.firstChild);
}
function clearLogs() {
    logPanel.innerHTML = '';
    addLogEntry({ type: 'info', text: 'Логи очищены.', sender: 'panel' });
}

// ============================================================
// Статус
// ============================================================
function setAgentStatus(running) {
    btnStart.disabled = running;
    btnStop.disabled = !running;
    agentPill.className = 'status-pill agent' + (running ? ' running' : '');
    agentPill.querySelector('.pill-text').textContent = running ? 'Работает' : 'Остановлен';
}
function setAgentStarting() {
    btnStart.disabled = true;
    agentPill.className = 'status-pill agent starting';
    agentPill.querySelector('.pill-text').textContent = 'Запуск...';
}

// ============================================================
// Загрузка данных
// ============================================================
async function loadEnv() {
    try {
        const d = await (await fetch('/env')).json();
        fieldApiId.value = d.TELEGRAM_API_ID || '';
        fieldApiHash.value = d.TELEGRAM_API_HASH || '';
        fieldOpenaiKey.value = d.OPENAI_API_KEY || '';
        fieldBaseUrl.value = d.OPENAI_BASE_URL || '';
        fieldModel.value = d.AI_MODEL || '';
        fieldApiFormat.value = d.API_FORMAT || 'openai';
    } catch (e) {
        addLogEntry({ type: 'error', text: `Загрузка .env: ${e.message}` });
    }
}
async function loadConfig() {
    try {
        const d = await (await fetch('/settings')).json();
        fieldContacts.value = (d.allowed_contacts || []).join('\n');
        fieldPrompt.value = d.system_prompt || '';
        fieldMinDelay.value = d.min_delay ?? 1.0;
        fieldMaxDelay.value = d.max_delay ?? 3.0;
        fieldContextEnabled.checked = d.context_enabled ?? true;
        fieldContextMsgs.value = d.context_messages ?? 6;
    } catch (e) {
        addLogEntry({ type: 'error', text: `Загрузка config: ${e.message}` });
    }
}
async function fetchStatus() {
    try {
        const d = await (await fetch('/status')).json();
        modelInfo.textContent = d.model || '—';
        apiUrlInfo.textContent = d.api_url || '—';
        // Добавляем формат к чипу модели
        const fmt = d.api_format === 'anthropic' ? '📜' : '🤖';
        modelInfo.textContent = fmt + ' ' + (d.model || '—');
        setAgentStatus(d.running);
    } catch {
        setTimeout(fetchStatus, 2000);
    }
}

// ============================================================
// Сохранение
// ============================================================
async function saveEnv() {
    const rawId   = fieldApiId.value.trim();
    const rawHash = fieldApiHash.value.trim();
    const rawKey  = fieldOpenaiKey.value.trim();
    const rawBase = fieldBaseUrl.value.trim();
    const rawModel = fieldModel.value.trim();
    const rawFmt  = fieldApiFormat.value.trim();

    const data = {
        TELEGRAM_API_ID: rawId ? (parseInt(rawId) || 0) : undefined,
        TELEGRAM_API_HASH: (!rawHash || rawHash.includes('***')) ? undefined : rawHash,
        OPENAI_API_KEY: (!rawKey || rawKey.includes('***')) ? undefined : rawKey,
        OPENAI_BASE_URL: rawBase || undefined,
        AI_MODEL: rawModel || undefined,
        API_FORMAT: rawFmt || undefined,
    };
    try {
        const r = await (await fetch('/env', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
        })).json();
        if (r.status === 'ok') {
            showToast('API-ключи сохранены', 'success');
            addLogEntry({ type: 'info', text: 'API-ключи обновлены.', sender: 'panel' });
            fetchStatus();
        }
    } catch (e) {
        showToast('Ошибка сохранения', 'error');
        addLogEntry({ type: 'error', text: `Ошибка: ${e.message}` });
    }
}
async function saveConfig() {
    const contacts = fieldContacts.value.split('\n').map(s => s.trim()).filter(Boolean);
    const minD = parseFloat(fieldMinDelay.value) || 1.0;
    const maxD = parseFloat(fieldMaxDelay.value) || 3.0;
    // Если max < min, делаем min+0.5
    const maxDelay = maxD < minD ? minD + 0.5 : maxD;
    try {
        const r = await (await fetch('/settings', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                allowed_contacts: contacts,
                system_prompt: fieldPrompt.value.trim(),
                min_delay: minD,
                max_delay: maxDelay,
                context_enabled: fieldContextEnabled.checked,
                context_messages: parseInt(fieldContextMsgs.value) || 6,
            }),
        })).json();
        if (r.status === 'ok') {
            showToast('Настройки бота сохранены', 'success');
            addLogEntry({ type: 'info', text: 'Настройки бота обновлены.', sender: 'panel' });
        }
    } catch (e) {
        showToast('Ошибка сохранения', 'error');
    }
}

async function testApi() {
    const btn = $('#btnTestApi');
    const result = $('#testApiResult');
    btn.disabled = true;
    result.className = 'test-result pending';
    result.textContent = '⏳ Проверка...';
    try {
        const r = await (await fetch('/test-api', { method: 'POST' })).json();
        if (r.status === 'ok') {
            result.className = 'test-result success';
            result.textContent = r.message;
            showToast('API работает ✅', 'success');
        } else {
            result.className = 'test-result error';
            result.textContent = r.message;
            showToast('Ошибка API', 'error');
        }
    } catch (e) {
        result.className = 'test-result error';
        result.textContent = '❌ Ошибка соединения с сервером';
    }
    btn.disabled = false;
    // Очищаем результат через 15 секунд
    setTimeout(() => { result.textContent = ''; result.className = 'test-result'; }, 15000);
}

// ============================================================
// Управление агентом
// ============================================================
async function startAgent() {
    setAgentStarting();
    try {
        const d = await (await fetch('/start', { method: 'POST' })).json();
        if (d.status === 'ok' || d.status === 'already_running') {
            showToast(d.message, 'success');
        } else {
            showToast(d.message, 'error');
            setAgentStatus(false);
        }
        // Начинаем проверять, не нужна ли авторизация
        checkAuthModal();
    } catch (e) {
        showToast('Ошибка запуска', 'error');
        setAgentStatus(false);
    }
}
async function stopAgent() {
    btnStop.disabled = true;
    try {
        const d = await (await fetch('/stop', { method: 'POST' })).json();
        showToast(d.message, 'info');
        setAgentStatus(false);
    } catch (e) {
        showToast('Ошибка остановки', 'error');
    }
}

// ============================================================
// WebSocket
// ============================================================
function connectWS() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${proto}//${location.host}/ws`);
    ws.onopen = () => {
        const dot = wsPill.querySelector('.pill-dot.ws');
        dot.classList.add('on');
        wsPill.querySelector('.pill-text').textContent = 'Online';
        addLogEntry({ type: 'info', text: 'WebSocket подключён.', sender: 'ws' });
        fetchStatus(); loadEnv(); loadConfig();
    };
    ws.onmessage = (e) => {
        try {
            const entry = JSON.parse(e.data);
            addLogEntry(entry);
            if (entry.text?.includes('Telegram-агент запущен')) setAgentStatus(true);
            if (entry.text?.includes('Telegram-агент остановлен')) setAgentStatus(false);
            // Авторизация: открываем модалку
            if (entry.text?.includes('номер телефона')) {
                showAuthModal('phone');
            }
            if (entry.text?.includes('Код отправлен') || entry.text?.includes('Введите код')) {
                showAuthModal('code');
            }
            if (entry.text?.includes('двухфакторной') || entry.text?.includes('пароль')) {
                showAuthModal('2fa');
            }
            if (entry.text?.includes('Авторизация успешна')) {
                closeAuthModal();
                setAgentStatus(true);
            }
            if (entry.text?.includes('Неверный') || entry.text?.includes('ошибк')) {
                showAuthError(entry.text);
            }
        } catch {}
    };
    ws.onclose = () => {
        wsPill.querySelector('.pill-dot.ws').classList.remove('on');
        wsPill.querySelector('.pill-text').textContent = 'Offline';
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(connectWS, 3000);
    };
}

// ============================================================
// Init
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    addLogEntry({ type: 'info', text: 'Панель загружена. Подключение...', sender: 'panel' });
    fetchStatus(); loadEnv(); loadConfig(); connectWS();
});

// ============================================================
// Модальное окно авторизации Telegram
// ============================================================
let authTimerInterval = null;

function showAuthModal(step) {
    const modal = $('#authModal');
    if (!modal) return;
    modal.style.display = 'flex';

    // Скрываем все шаги
    $$('.auth-step').forEach(el => el.style.display = 'none');
    $('#authError').style.display = 'none';

    if (step === 'phone') {
        $('#authStepPhone').style.display = 'flex';
        $('#authDesc').textContent = 'Введите номер телефона для входа в Telegram';
        $('#authPhoneInput').focus();
        startAuthTimer(300);
    } else if (step === 'code') {
        $('#authStepCode').style.display = 'flex';
        $('#authDesc').textContent = 'Введите код из Telegram';
        $('#authCodeInput').focus();
        startAuthTimer(300);
    } else if (step === '2fa') {
        $('#authStep2FA').style.display = 'flex';
        $('#authDesc').textContent = 'Введите пароль двухфакторной аутентификации';
        $('#auth2FAInput').focus();
        startAuthTimer(120);
    }
}

function closeAuthModal() {
    $('#authModal').style.display = 'none';
    clearInterval(authTimerInterval);
    $('#authTimer').textContent = '';
}

function showAuthError(msg) {
    const el = $('#authError');
    el.textContent = msg;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 8000);
}

function startAuthTimer(seconds) {
    clearInterval(authTimerInterval);
    const el = $('#authTimer');
    let remaining = seconds;
    function tick() {
        const m = Math.floor(remaining / 60);
        const s = remaining % 60;
        el.textContent = `${m}:${String(s).padStart(2, '0')}`;
        if (remaining <= 0) {
            clearInterval(authTimerInterval);
            el.textContent = '⏰ Время вышло';
            closeAuthModal();
            showToast('Время авторизации истекло. Нажмите "Запустить" снова.', 'error');
        }
        remaining--;
    }
    tick();
    authTimerInterval = setInterval(tick, 1000);
}

async function submitAuthPhone() {
    const phone = $('#authPhoneInput').value.trim();
    if (!phone) { showAuthError('Введите номер телефона'); return; }
    $('#authPhoneBtn').disabled = true;
    $('#authPhoneBtn').innerHTML = '<i class="bi bi-hourglass"></i> Отправляю...';
    try {
        const r = await (await fetch('/auth/phone', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone }),
        })).json();
        if (r.status === 'ok') {
            showAuthModal('code');
        } else {
            showAuthError(r.message || 'Ошибка');
        }
    } catch (e) {
        showAuthError('Ошибка отправки: ' + e.message);
    }
    $('#authPhoneBtn').disabled = false;
    $('#authPhoneBtn').innerHTML = '<i class="bi bi-send"></i> Отправить код';
}

async function submitAuthCode() {
    const code = $('#authCodeInput').value.trim();
    if (!code) { showAuthError('Введите код из Telegram'); return; }
    $('#authCodeBtn').disabled = true;
    $('#authCodeBtn').innerHTML = '<i class="bi bi-hourglass"></i> Проверяю...';
    try {
        const r = await (await fetch('/auth/code', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code }),
        })).json();
        if (r.status === 'ok') {
            // Ждём успешного сообщения через WebSocket
            showToast('Код отправлен. Проверка...', 'info');
            $('#authStepCode').style.display = 'none';
            $('#authDesc').textContent = 'Проверяю код...';
        } else {
            showAuthError(r.message || 'Ошибка');
        }
    } catch (e) {
        showAuthError('Ошибка: ' + e.message);
    }
    $('#authCodeBtn').disabled = false;
    $('#authCodeBtn').innerHTML = '<i class="bi bi-check-lg"></i> Подтвердить';
}

async function submitAuth2FA() {
    const password = $('#auth2FAInput').value.trim();
    if (!password) { showAuthError('Введите пароль'); return; }
    try {
        const r = await (await fetch('/auth/code', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: password }),
        })).json();
        if (r.status === 'ok') {
            showToast('Пароль отправлен', 'info');
            $('#authStep2FA').style.display = 'none';
            $('#authDesc').textContent = 'Проверяю...';
        } else {
            showAuthError(r.message || 'Ошибка');
        }
    } catch (e) {
        showAuthError('Ошибка: ' + e.message);
    }
}

async function checkAuthModal() {
    // Проверяем статус авторизации каждые 3 секунды
    setTimeout(async () => {
        try {
            const d = await (await fetch('/auth/status')).json();
            if (d.needs_phone) showAuthModal('phone');
            else if (d.needs_code) showAuthModal('code');
        } catch {}
    }, 3000);
}
