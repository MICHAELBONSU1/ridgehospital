let leaveTypes = [];
let dashboardData = null;

async function loadDashboard() {
    try {
        const [dash, types] = await Promise.all([
            API.get('/api/employee/dashboard'),
            API.get('/api/leave-types'),
        ]);
        dashboardData = dash;
        leaveTypes = types.leave_types;
        renderDashboard(dash);
        populateLeaveTypes();
        populateProfile(dash.user);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function renderDashboard(data) {
    const annual = data.leave_balances.find(b => b.leave_type === 'Annual Leave');
    document.getElementById('annualBalance').textContent = annual ? annual.remaining : '--';
    document.getElementById('pendingCount').textContent = data.pending_leave.length;
    document.getElementById('approvedCount').textContent = data.approved_leave.length;
    document.getElementById('rejectedCount').textContent = data.rejected_leave.length;

    const allRequests = [
        ...data.pending_leave,
        ...data.approved_leave,
        ...data.rejected_leave,
    ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    const tbody = document.querySelector('#leaveHistoryTable tbody');
    tbody.innerHTML = allRequests.map(r => `
        <tr>
            <td>${r.leave_type}</td>
            <td>${formatDate(r.start_date)}</td>
            <td>${formatDate(r.end_date)}</td>
            <td>${r.days_requested}</td>
            <td>${statusBadge(r.status)}</td>
            <td>${canCancel(r) ? `<button class="btn btn-sm btn-danger" onclick="cancelLeave(${r.id})">Cancel</button>` : ''}</td>
        </tr>
    `).join('') || '<tr><td colspan="6" style="text-align:center;color:#64748b;">No leave history</td></tr>';

    document.getElementById('balanceCards').innerHTML = data.leave_balances.map(b => `
        <div class="balance-card">
            <div class="type">${b.leave_type}</div>
            <div class="remaining">${b.remaining}</div>
            <div class="detail">${b.used} used / ${b.total} total</div>
        </div>
    `).join('');
}

function canCancel(r) {
    return ['draft', 'supervisor_pending', 'more_info_requested'].includes(r.status);
}

function populateLeaveTypes() {
    const select = document.getElementById('leaveType');
    select.innerHTML = leaveTypes.map(t =>
        `<option value="${t.id}">${t.name}${t.requires_document ? ' (doc required)' : ''}</option>`
    ).join('');
}

function populateProfile(user) {
    document.getElementById('profileName').value = user.full_name;
    document.getElementById('profileEmpId').value = user.employee_id;
    document.getElementById('profileEmail').value = user.email;
    document.getElementById('profilePhone').value = user.phone || '';
    document.getElementById('profileDept').value = user.department || '';
    document.getElementById('profileSupervisor').value = user.supervisor_name || 'None';
}

async function submitLeave(submit = true) {
    const payload = {
        leave_type_id: parseInt(document.getElementById('leaveType').value),
        start_date: document.getElementById('startDate').value,
        end_date: document.getElementById('endDate').value,
        reason: document.getElementById('leaveReason').value,
        submit,
    };

    try {
        const data = await API.post('/api/employee/leave', payload);
        showToast(submit ? 'Leave submitted successfully!' : 'Draft saved.', 'success');
        document.getElementById('leaveForm').reset();
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

window.cancelLeave = async (id) => {
    if (!confirm('Cancel this leave request?')) return;
    try {
        await API.post(`/api/employee/leave/${id}/cancel`);
        showToast('Leave cancelled.', 'success');
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    }
};

document.getElementById('leaveForm').addEventListener('submit', (e) => {
    e.preventDefault();
    submitLeave(true);
});

document.getElementById('saveDraft').addEventListener('click', () => submitLeave(false));

document.getElementById('profileForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
        await API.put('/api/employee/profile', {
            email: document.getElementById('profileEmail').value,
            phone: document.getElementById('profilePhone').value,
        });
        showToast('Profile updated.', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
});

document.addEventListener('DOMContentLoaded', loadDashboard);
