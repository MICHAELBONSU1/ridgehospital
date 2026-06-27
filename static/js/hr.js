async function loadDashboard() {
    try {
        const data = await API.get('/api/hr/dashboard');
        renderDashboard(data);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function renderDashboard(data) {
    document.getElementById('pendingCount').textContent = data.pending_requests.length;
    document.getElementById('staffCount').textContent = data.total_staff;

    document.getElementById('pendingList').innerHTML = data.pending_requests.length
        ? data.pending_requests.map(r => `
            <div class="request-card">
                <div class="request-card-header">
                    <h4>${r.employee_name}</h4>
                    ${statusBadge(r.status)}
                </div>
                <div class="request-meta">
                    ${r.leave_type} · ${formatDate(r.start_date)} – ${formatDate(r.end_date)} · ${r.days_requested} day(s)
                </div>
                <div class="request-meta">${r.employee_department || ''} · ${r.employee_unit || ''}</div>
                ${r.reason ? `<p style="font-size:.9rem;margin-top:.5rem;">${r.reason}</p>` : ''}
                ${renderApprovals(r.approvals)}
                <div class="request-actions">
                    <button class="btn btn-sm btn-success" onclick="hrAction(${r.id}, 'approve')">Approve</button>
                    <button class="btn btn-sm btn-danger" onclick="hrAction(${r.id}, 'reject')">Reject</button>
                    <button class="btn btn-sm btn-warning" onclick="hrAction(${r.id}, 'return_to_supervisor')">Return to Supervisor</button>
                </div>
            </div>
        `).join('')
        : '<p style="color:#64748b;padding:1rem;">No pending HR approvals.</p>';
}

function renderApprovals(approvals) {
    if (!approvals || !approvals.length) return '';
    return `<div style="margin-top:.75rem;font-size:.85rem;color:#64748b;">
        ${approvals.map(a => `${a.approver_name} (${a.stage}): ${a.action}${a.comment ? ' — ' + a.comment : ''}`).join('<br>')}
    </div>`;
}

window.hrAction = async (id, action) => {
    let comment = '';
    if (action === 'reject' || action === 'return_to_supervisor') {
        comment = prompt(action === 'reject' ? 'Rejection reason:' : 'Reason for return:');
        if (comment === null) return;
    }
    try {
        await API.post(`/api/hr/leave/${id}/action`, { action, comment });
        showToast(`Leave ${action.replace(/_/g, ' ')}.`, action === 'approve' ? 'success' : 'info');
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    }
};

async function loadStaff() {
    try {
        const data = await API.get('/api/hr/staff');
        const tbody = document.querySelector('#staffTable tbody');
        tbody.innerHTML = data.staff.map(s => `
            <tr>
                <td>${s.full_name}</td>
                <td>${s.employee_id}</td>
                <td>${s.department || '-'}</td>
                <td>${s.unit || '-'}</td>
                <td>${s.supervisor_name || '-'}</td>
            </tr>
        `).join('');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function loadReports() {
    try {
        const data = await API.get('/api/hr/reports');
        document.getElementById('reportsContent').innerHTML = `
            <div class="report-card">
                <h4>Summary</h4>
                <div class="report-item"><span>Pending Approvals</span><strong>${data.pending_approvals}</strong></div>
                <div class="report-item"><span>Completed Leave</span><strong>${data.total_completed}</strong></div>
            </div>
            <div class="report-card">
                <h4>By Department</h4>
                ${data.by_department.map(d => `<div class="report-item"><span>${d.department}</span><strong>${d.count}</strong></div>`).join('') || '<p>No data</p>'}
            </div>
            <div class="report-card">
                <h4>By Leave Type</h4>
                ${data.by_type.map(t => `<div class="report-item"><span>${t.type}</span><strong>${t.count}</strong></div>`).join('') || '<p>No data</p>'}
            </div>
        `;
    } catch (err) {
        showToast(err.message, 'error');
    }
}

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        if (tab.dataset.tab === 'staff') loadStaff();
        if (tab.dataset.tab === 'reports') loadReports();
    });
});

document.addEventListener('DOMContentLoaded', loadDashboard);
