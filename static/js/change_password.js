document.getElementById('changePasswordForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errorEl = document.getElementById('passwordError');
    errorEl.classList.add('hidden');

    const old_password = document.getElementById('old_password').value;
    const new_password = document.getElementById('new_password').value;
    const confirm = document.getElementById('confirm_password').value;

    if (new_password !== confirm) {
        errorEl.textContent = 'Passwords do not match.';
        errorEl.classList.remove('hidden');
        return;
    }

    try {
        const data = await API.post('/api/auth/change-password', { old_password, new_password });
        showToast(data.message, 'success');
        setTimeout(() => { window.location.href = data.redirect; }, 1000);
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.classList.remove('hidden');
    }
});
