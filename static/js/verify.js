/**
 * Verification Page JavaScript
 * Real-time timestamp and animated badge
 */
document.addEventListener('DOMContentLoaded', () => {
    const timestampEl = document.getElementById('verify-timestamp');

    function updateTimestamp() {
        if (!timestampEl) return;
        const now = new Date();
        const options = {
            year: 'numeric', month: 'short', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
            hour12: true, timeZoneName: 'short'
        };
        timestampEl.textContent = `Verified at ${now.toLocaleString('en-IN', options)}`;
    }

    updateTimestamp();
    setInterval(updateTimestamp, 1000);

    // Animate the verification card entrance
    const card = document.querySelector('.verify-card');
    if (card) {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px) scale(0.98)';
        requestAnimationFrame(() => {
            card.style.transition = 'opacity 0.6s cubic-bezier(0.34, 1.56, 0.64, 1), transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0) scale(1)';
        });
    }

    // Pulse animation for active status badge
    const statusBadge = document.querySelector('.verify-status-active');
    if (statusBadge) {
        let pulseCount = 0;
        const pulseInterval = setInterval(() => {
            statusBadge.style.transform = 'scale(1.05)';
            setTimeout(() => {
                statusBadge.style.transform = 'scale(1)';
            }, 200);
            pulseCount++;
            if (pulseCount >= 3) clearInterval(pulseInterval);
        }, 800);
    }
});
