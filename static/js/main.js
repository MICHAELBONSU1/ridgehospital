const API = {
    async request(url, options = {}) {
        const defaults = {
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
        };
        const res = await fetch(url, { ...defaults, ...options });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || 'Request failed');
        return data;
    },
    get(url) { return this.request(url); },
    post(url, body) { return this.request(url, { method: 'POST', body: JSON.stringify(body) }); },
    put(url, body) { return this.request(url, { method: 'PUT', body: JSON.stringify(body) }); },
    delete(url) { return this.request(url, { method: 'DELETE' }); },
};

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('en-GB', {
        day: '2-digit', month: 'short', year: 'numeric',
    });
}

function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('en-GB', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
    });
}

function statusBadge(status) {
    const label = status.replace(/_/g, ' ');
    return `<span class="badge-status ${status}">${label}</span>`;
}

function initTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            const content = document.getElementById(`tab-${target}`);
            if (content) content.classList.add('active');
        });
    });

    document.querySelectorAll('[data-tab-link]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const target = link.dataset.tabLink;
            const tab = document.querySelector(`.tab[data-tab="${target}"]`);
            if (tab) tab.click();
        });
    });
}

function initSidebar() {
    const toggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
    }

    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await API.post('/api/auth/logout');
            window.location.href = '/login';
        });
    }
}

async function loadUserHeader() {
    try {
        const data = await API.get('/api/auth/me');
        const user = data.user;
        const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
        setText('userName', user.full_name);
        setText('userDept', user.department || '');
        setText('userRole', user.role);
        const avatar = document.getElementById('userAvatar');
        if (avatar) avatar.textContent = user.full_name.charAt(0).toUpperCase();
    } catch {
        window.location.href = '/login';
    }
}

async function loadNotifications() {
    try {
        const data = await API.get('/api/notifications');
        const badge = document.getElementById('notifBadge');
        if (badge) {
            badge.textContent = data.unread_count;
            badge.style.display = data.unread_count > 0 ? 'block' : 'none';
        }
        const list = document.getElementById('notificationList');
        if (!list) return;
        if (data.notifications.length === 0) {
            list.innerHTML = '<p style="padding:1rem;color:#64748b;text-align:center;">No notifications</p>';
            return;
        }
        list.innerHTML = data.notifications.map(n => `
            <div class="notif-item ${n.is_read ? '' : 'unread'}" data-id="${n.id}">
                <strong>${n.title}</strong>
                <p>${n.message}</p>
                <small>${formatDateTime(n.created_at)}</small>
            </div>
        `).join('');

        list.querySelectorAll('.notif-item').forEach(item => {
            item.addEventListener('click', async () => {
                await API.post(`/api/notifications/${item.dataset.id}/read`);
                loadNotifications();
            });
        });
    } catch { /* ignore */ }
}

function initNotifications() {
    const bell = document.getElementById('notificationBell');
    const panel = document.getElementById('notificationPanel');
    const markAll = document.getElementById('markAllRead');

    if (bell && panel) {
        bell.addEventListener('click', () => {
            panel.classList.toggle('hidden');
            loadNotifications();
        });
    }
    if (markAll) {
        markAll.addEventListener('click', async () => {
            await API.post('/api/notifications/read-all');
            loadNotifications();
        });
    }
    loadNotifications();
    setInterval(loadNotifications, 30000);
}

function initModal() {
    const modal = document.getElementById('modal');
    const closeBtn = document.getElementById('modalClose');
    if (!modal) return;

    const close = () => modal.classList.add('hidden');
    if (closeBtn) closeBtn.addEventListener('click', close);
    modal.querySelector('.modal-backdrop')?.addEventListener('click', close);
    window.showModal = (title, body) => {
        document.getElementById('modalTitle').textContent = title;
        document.getElementById('modalBody').innerHTML = body;
        modal.classList.remove('hidden');
    };
    window.closeModal = close;
}

document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initTabs();
    initNotifications();
    initModal();
    if (document.getElementById('userName')) loadUserHeader();
});
