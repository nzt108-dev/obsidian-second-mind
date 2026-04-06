/* ============================================
   Mission Control — App Logic
   ============================================ */

const CATEGORY_ICONS = {
    mobile:   '📱',
    web:      '🌐',
    saas:     '☁️',
    telegram: '🤖',
    other:    '📁',
};

const SERVICE_ICONS = {
    'Firebase':       '🔥',
    'Firestore':      '🔥',
    'Cloud Storage':  '🔥',
    'FCM':            '🔥',
    'Supabase':       '⚡',
    'Vercel':         '▲',
    'Docker':         '🐳',
    'VPS':            '🖥️',
    'GitHub':         '🐙',
    'GitHub Pages':   '🐙',
    'Redis':          '🔴',
    'Telegram API':   '🤖',
    'YouTube API':    '📺',
    'OpenRouter':     '🧠',
    'ElevenLabs':     '🎙️',
    'Turso':          '🗄️',
    'Zillow API':     '🏠',
};

let allProjects = [];
let activeStatusFilter = 'all';
let activeStackFilter = null;

// ---- Init ----
document.addEventListener('DOMContentLoaded', () => {
    updateClock();
    setInterval(updateClock, 1000);
    fetchProjects();
    setupFilters();
});

// ---- Clock ----
function updateClock() {
    const el = document.getElementById('headerTime');
    if (!el) return;
    const now = new Date();
    el.textContent = now.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    });
}

// ---- Fetch ----
async function fetchProjects() {
    try {
        const res = await fetch('/api/projects');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        allProjects = await res.json();

        // Sort: active first, then by name
        const statusOrder = { active: 0, mvp: 1, paused: 2, idea: 3, done: 4, unknown: 5 };
        allProjects.sort((a, b) => {
            const sa = statusOrder[a.status] ?? 5;
            const sb = statusOrder[b.status] ?? 5;
            if (sa !== sb) return sa - sb;
            return a.id.localeCompare(b.id);
        });

        renderStats();
        renderStackFilters();
        renderProjects();
    } catch (err) {
        const grid = document.getElementById('projectsGrid');
        grid.innerHTML = `<div class="empty-state">❌ Ошибка загрузки: ${err.message}</div>`;
    }
}

// ---- Stats ----
function renderStats() {
    document.getElementById('statTotal').textContent = allProjects.length;
    document.getElementById('statActive').textContent = allProjects.filter(p => p.status === 'active').length;
    document.getElementById('statPaused').textContent = allProjects.filter(p => p.status === 'paused').length;
    document.getElementById('statDone').textContent = allProjects.filter(p => p.status === 'done').length;
    document.getElementById('statIdea').textContent = allProjects.filter(p => p.status === 'idea').length;
}

// ---- Stack Filters ----
function renderStackFilters() {
    const stacks = new Set();
    allProjects.forEach(p => (p.stack || []).forEach(s => stacks.add(s)));

    const container = document.getElementById('filterStack');
    container.innerHTML = '';

    [...stacks].sort().forEach(stack => {
        const btn = document.createElement('button');
        btn.className = 'filter-btn filter-btn--stack';
        btn.dataset.stack = stack;
        btn.textContent = stack;
        btn.addEventListener('click', () => {
            if (activeStackFilter === stack) {
                activeStackFilter = null;
                btn.classList.remove('filter-btn--active');
            } else {
                document.querySelectorAll('.filter-btn--stack').forEach(b => b.classList.remove('filter-btn--active'));
                activeStackFilter = stack;
                btn.classList.add('filter-btn--active');
            }
            renderProjects();
        });
        container.appendChild(btn);
    });
}

// ---- Filters ----
function setupFilters() {
    // Status filters
    document.getElementById('filterTags').addEventListener('click', (e) => {
        const btn = e.target.closest('.filter-btn');
        if (!btn) return;

        document.querySelectorAll('#filterTags .filter-btn').forEach(b => b.classList.remove('filter-btn--active'));
        btn.classList.add('filter-btn--active');
        activeStatusFilter = btn.dataset.filter;
        renderProjects();
    });

    // Search
    document.getElementById('searchInput').addEventListener('input', () => {
        renderProjects();
    });
}

// ---- Render ----
function renderProjects() {
    const grid = document.getElementById('projectsGrid');
    const search = document.getElementById('searchInput').value.toLowerCase().trim();

    let filtered = allProjects;

    // Status filter
    if (activeStatusFilter !== 'all') {
        filtered = filtered.filter(p => p.status === activeStatusFilter);
    }

    // Stack filter
    if (activeStackFilter) {
        filtered = filtered.filter(p => (p.stack || []).includes(activeStackFilter));
    }

    // Search
    if (search) {
        filtered = filtered.filter(p =>
            p.id.toLowerCase().includes(search) ||
            (p.description || '').toLowerCase().includes(search) ||
            (p.title || '').toLowerCase().includes(search) ||
            (p.stack || []).some(s => s.toLowerCase().includes(search)) ||
            (p.services || []).some(s => s.toLowerCase().includes(search))
        );
    }

    if (filtered.length === 0) {
        grid.innerHTML = '<div class="empty-state">Нет проектов по заданным фильтрам</div>';
        document.getElementById('footerCount').textContent = '0 проектов';
        return;
    }

    grid.innerHTML = filtered.map(p => renderCard(p)).join('');
    document.getElementById('footerCount').textContent = `${filtered.length} из ${allProjects.length} проектов`;
}

function renderCard(p) {
    const icon = CATEGORY_ICONS[p.category] || CATEGORY_ICONS.other;

    // Clean title
    const displayTitle = (p.title || p.id)
        .replace(/— PRD$/, '').replace(/— prd$/i, '').trim();

    // Stack badges
    const stackHTML = (p.stack || [])
        .map(s => `<span class="badge badge--stack">${s}</span>`)
        .join('');

    // Service badges
    const servicesHTML = (p.services || [])
        .map(s => {
            const icon = SERVICE_ICONS[s] || '•';
            return `<span class="badge badge--service">${icon} ${s}</span>`;
        })
        .join('');

    // Whats next
    let tasksHTML = '';
    if (p.whats_next && p.whats_next.length > 0) {
        const items = p.whats_next.map(t => `<div class="project-card__task">${t}</div>`).join('');
        tasksHTML = `
            <div class="project-card__tasks">
                <div class="project-card__tasks-title">Что дальше</div>
                ${items}
            </div>`;
    }

    // Git info
    let gitHTML = '';
    if (p.last_commit) {
        const date = p.last_commit.date ? formatTimeAgo(p.last_commit.date) : '';
        gitHTML = `
            <div class="project-card__git">
                <span class="project-card__git-hash">${p.last_commit.hash || ''}</span>
                <span class="project-card__git-msg" title="${escapeHtml(p.last_commit.message || '')}">${escapeHtml(p.last_commit.message || '')}</span>
                <span class="project-card__git-date">${date}</span>
            </div>`;
    }

    // Actions
    const ideBtn = p.path
        ? `<a href="antigravity://file${p.path}" class="action-btn action-btn--ide">🚀 Open in IDE</a>`
        : `<span class="action-btn action-btn--ide" style="opacity:0.3;cursor:default">⚠️ Путь не указан</span>`;

    const ghBtn = p.github_url
        ? `<a href="${p.github_url}" target="_blank" class="action-btn action-btn--github">🐙 GitHub</a>`
        : '';

    return `
        <div class="project-card project-card--${p.status}">
            <div class="project-card__header">
                <div class="project-card__info">
                    <span class="project-card__icon">${icon}</span>
                    <div class="project-card__titles">
                        <div class="project-card__name">${escapeHtml(displayTitle)}</div>
                        <div class="project-card__slug">${p.id}</div>
                    </div>
                </div>
                <span class="project-card__status project-card__status--${p.status}">${p.status}</span>
            </div>

            ${p.description ? `<div class="project-card__desc">${escapeHtml(p.description)}</div>` : ''}

            ${stackHTML ? `<div class="project-card__stack">${stackHTML}</div>` : ''}
            ${servicesHTML ? `<div class="project-card__services">${servicesHTML}</div>` : ''}

            ${tasksHTML}
            ${gitHTML}

            <div class="project-card__actions">
                ${ideBtn}
                ${ghBtn}
            </div>
        </div>
    `;
}

// ---- Helpers ----
function formatTimeAgo(dateStr) {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now - d;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHrs = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'сейчас';
    if (diffMins < 60) return `${diffMins}м`;
    if (diffHrs < 24) return `${diffHrs}ч`;
    if (diffDays < 7) return `${diffDays}д`;
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
