async function loadDashboard() {
    try {
        const data = await API.get('/api/supervisor/dashboard');
        renderDashboard(data);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function renderDashboard(data) {
    document.getElementById('pendingCount').textContent = data.pending_requests.length;
    document.getElementById('todayCount').textContent = data.today_requests.length;
    document.getElementById('teamCount').textContent = data.subordinates.length;

    document.getElementById('pendingList').innerHTML = renderRequestList(
        data.pending_requests, true
    );
    document.getElementById('teamCalendar').innerHTML = renderRequestList(
        data.team_calendar, false, true
    );
    document.getElementById('approvedList').innerHTML = renderRequestList(data.approved, false);
    document.getElementById('rejectedList').innerHTML = renderRequestList(data.rejected, false);

    document.getElementById('teamList').innerHTML = data.subordinates.map(s => `
        <div class="team-card">
            <strong>${s.full_name}</strong>
            <div class="request-meta">${s.position || ''} · ${s.unit || ''}</div>
        </div>
    `).join('') || '<p style="color:#64748b;">No team members assigned.</p>';
}

function renderRequestList(requests, showActions = false, calendar = false) {
    if (!requests.length) {
        return `<p style="color:#64748b;padding:1rem;">No ${calendar ? 'upcoming leave' : 'requests'}.</p>`;
    }
    return requests.map(r => `
        <div class="request-card" id="request-${r.id}">
            <div class="request-card-header">
                <h4>${r.employee_name}</h4>
                ${statusBadge(r.status)}
            </div>
            <div class="request-meta">
                ${r.leave_type} · ${formatDate(r.start_date)} – ${formatDate(r.end_date)} · ${r.days_requested} day(s)
            </div>
            <div class="request-meta">${r.employee_department || ''} · ${r.employee_unit || ''}</div>
            ${r.reason ? `<p style="font-size:.9rem;margin-top:.5rem;">${r.reason}</p>` : ''}
            ${showActions ? `
                <div class="request-actions">
                    <button class="btn btn-sm btn-success" onclick="handleAction(${r.id}, 'approve')">Approve</button>
                    <button class="btn btn-sm btn-danger" onclick="handleAction(${r.id}, 'reject')">Reject</button>
                    <button class="btn btn-sm btn-warning" onclick="handleAction(${r.id}, 'more_info')">Request Info</button>
                </div>
            ` : ''}
        </div>
    `).join('');
}

window.handleAction = async (id, action) => {
    let comment = '';
    if (action === 'reject' || action === 'more_info') {
        comment = prompt(action === 'reject' ? 'Rejection reason:' : 'What information do you need?');
        if (comment === null) return;
    }
    try {
        await API.post(`/api/supervisor/leave/${id}/action`, { action, comment });
        showToast(`Leave ${action.replace('_', ' ')}.`, action === 'approve' ? 'success' : 'info');
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    }
};

document.addEventListener('DOMContentLoaded', loadDashboard);
