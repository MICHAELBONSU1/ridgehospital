let formData = { departments: [], units: [], positions: [], roles: [], supervisors: [] };

async function loadDashboard() {
    try {
        const data = await API.get('/api/it/dashboard');
        document.getElementById('totalUsers').textContent = data.total_users;
        document.getElementById('totalNurses').textContent = data.total_nurses;
        document.getElementById('totalDoctors').textContent = data.total_doctors;
        document.getElementById('lockedAccounts').textContent = data.locked_accounts;

        renderLoginTable(data.recent_logins);
        renderAuditTable(data.recent_audits);
        await loadUsers();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function loadUsers() {
    const data = await API.get('/api/it/users');
    const tbody = document.querySelector('#usersTable tbody');
    tbody.innerHTML = data.users.map(u => `
        <tr>
            <td>${u.username}</td>
            <td>${u.full_name}</td>
            <td>${u.department || '-'}</td>
            <td>${u.role}</td>
            <td>${u.is_locked ? '<span class="badge-status rejected">Locked</span>' : u.is_active ? '<span class="badge-status completed">Active</span>' : '<span class="badge-status cancelled">Inactive</span>'}</td>
            <td>
                <button class="btn btn-sm btn-secondary" onclick="resetPassword(${u.id})">Reset PW</button>
                <button class="btn btn-sm ${u.is_locked ? 'btn-success' : 'btn-warning'}" onclick="toggleLock(${u.id}, ${!u.is_locked})">${u.is_locked ? 'Unlock' : 'Lock'}</button>
                <button class="btn btn-sm btn-danger" onclick="deleteUser(${u.id})">Delete</button>
            </td>
        </tr>
    `).join('');
}

function renderLoginTable(logins) {
    const tbody = document.querySelector('#loginTable tbody');
    if (!tbody) return;
    tbody.innerHTML = logins.map(l => `
        <tr>
            <td>${l.username}</td>
            <td>${l.success ? '✓' : '✗'}</td>
            <td>${l.ip_address || '-'}</td>
            <td>${formatDateTime(l.created_at)}</td>
        </tr>
    `).join('');
}

function renderAuditTable(audits) {
    const tbody = document.querySelector('#auditTable tbody');
    if (!tbody) return;
    tbody.innerHTML = audits.map(a => `
        <tr>
            <td>${a.user_name}</td>
            <td>${a.action}</td>
            <td>${a.details || '-'}</td>
            <td>${formatDateTime(a.created_at)}</td>
        </tr>
    `).join('');
}

window.resetPassword = async (id) => {
    if (!confirm('Reset password to default (Welcome@123)?')) return;
    try {
        const data = await API.post(`/api/it/users/${id}/reset-password`);
        showToast(data.message, 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
};

window.toggleLock = async (id, lock) => {
    try {
        await API.post(`/api/it/users/${id}/lock`, { lock });
        showToast(`Account ${lock ? 'locked' : 'unlocked'}.`, 'success');
        loadUsers();
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    }
};

window.deleteUser = async (id) => {
    if (!confirm('Deactivate this user account?')) return;
    try {
        await API.delete(`/api/it/users/${id}`);
        showToast('User deactivated.', 'success');
        loadUsers();
    } catch (err) {
        showToast(err.message, 'error');
    }
};

async function loadFormOptions() {
    const [depts, positions, roles, supervisors] = await Promise.all([
        API.get('/api/it/departments'),
        API.get('/api/it/positions'),
        API.get('/api/it/roles'),
        API.get('/api/it/supervisors'),
    ]);
    formData.departments = depts.departments;
    formData.positions = positions.positions;
    formData.roles = roles.roles;
    formData.supervisors = supervisors.supervisors;

    document.getElementById('department').innerHTML = depts.departments.map(d =>
        `<option value="${d.id}">${d.name}</option>`
    ).join('');

    document.getElementById('position').innerHTML = positions.positions.map(p =>
        `<option value="${p.id}">${p.title}</option>`
    ).join('');

    document.getElementById('role').innerHTML = roles.roles.map(r =>
        `<option value="${r.id}">${r.name}</option>`
    ).join('');

    document.getElementById('supervisor').innerHTML =
        '<option value="">None</option>' +
        supervisors.supervisors.map(s =>
            `<option value="${s.id}">${s.full_name} (${s.username})</option>`
        ).join('');
}

document.getElementById('department')?.addEventListener('change', async (e) => {
    const data = await API.get(`/api/it/units?department_id=${e.target.value}`);
    document.getElementById('unit').innerHTML =
        '<option value="">None</option>' +
        data.units.map(u => `<option value="${u.id}">${u.name}</option>`).join('');
});

document.getElementById('createUserForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
        employee_id: document.getElementById('empId').value,
        staff_number: document.getElementById('staffNumber').value,
        username: document.getElementById('username').value,
        full_name: document.getElementById('fullName').value,
        email: document.getElementById('email').value,
        phone: document.getElementById('phone').value,
        department_id: parseInt(document.getElementById('department').value),
        unit_id: document.getElementById('unit').value ? parseInt(document.getElementById('unit').value) : null,
        position_id: parseInt(document.getElementById('position').value),
        employment_type: document.getElementById('employmentType').value,
        supervisor_id: document.getElementById('supervisor').value ? parseInt(document.getElementById('supervisor').value) : null,
        role_id: parseInt(document.getElementById('role').value),
        password: document.getElementById('defaultPassword').value,
    };

    try {
        await API.post('/api/it/users', payload);
        showToast('Account created successfully!', 'success');
        document.getElementById('createUserForm').reset();
        document.getElementById('defaultPassword').value = 'Welcome@123';
        loadUsers();
    } catch (err) {
        showToast(err.message, 'error');
    }
});

async function loadReports() {
    try {
        const data = await API.get('/api/it/reports');
        document.getElementById('reportsContent').innerHTML = `
            <div class="report-card">
                <h4>Overview</h4>
                <div class="report-item"><span>Active Users</span><strong>${data.total_active}</strong></div>
                <div class="report-item"><span>Locked Accounts</span><strong>${data.total_locked}</strong></div>
            </div>
            <div class="report-card">
                <h4>By Role</h4>
                ${data.by_role.map(r => `<div class="report-item"><span>${r.role}</span><strong>${r.count}</strong></div>`).join('')}
            </div>
            <div class="report-card">
                <h4>By Department</h4>
                ${data.by_department.map(d => `<div class="report-item"><span>${d.department}</span><strong>${d.count}</strong></div>`).join('')}
            </div>
        `;
    } catch (err) {
        showToast(err.message, 'error');
    }
}

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        if (tab.dataset.tab === 'create') loadFormOptions();
        if (tab.dataset.tab === 'reports') loadReports();
    });
});

document.addEventListener('DOMContentLoaded', loadDashboard);
