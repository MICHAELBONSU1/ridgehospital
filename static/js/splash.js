(function () {
    const REDIRECT_DELAY = 4500;
    let redirected = false;

    function goToLogin() {
        if (redirected) return;
        redirected = true;

        const splash = document.getElementById('splashScreen');
        splash.classList.add('exiting');

        setTimeout(() => {
            window.location.href = '/login';
        }, 650);
    }

    document.getElementById('enterBtn').addEventListener('click', goToLogin);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            goToLogin();
        }
    });

    setTimeout(goToLogin, REDIRECT_DELAY);
})();
