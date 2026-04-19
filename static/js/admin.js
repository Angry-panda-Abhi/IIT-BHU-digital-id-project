/**
 * Admin Dashboard JavaScript
 * Search filtering and confirmation dialogs
 */
document.addEventListener('DOMContentLoaded', () => {
    // Auto-submit status filter on change
    const statusFilter = document.getElementById('status-filter');
    if (statusFilter) {
        statusFilter.addEventListener('change', () => {
            statusFilter.closest('form').submit();
        });
    }

    // Highlight search term in table
    const searchInput = document.getElementById('search-input');
    if (searchInput && searchInput.value.trim()) {
        const term = searchInput.value.trim().toLowerCase();
        const cells = document.querySelectorAll('#students-table tbody td');
        cells.forEach(cell => {
            const text = cell.textContent.toLowerCase();
            if (text.includes(term) && !cell.querySelector('img') && !cell.querySelector('form')) {
                cell.style.background = 'rgba(108, 99, 255, 0.08)';
            }
        });
    }

    // Animate stat values on load
    document.querySelectorAll('.stat-value').forEach(el => {
        const target = parseInt(el.textContent, 10);
        if (isNaN(target) || target === 0) return;

        let current = 0;
        const step = Math.max(1, Math.ceil(target / 30));
        const interval = setInterval(() => {
            current += step;
            if (current >= target) {
                current = target;
                clearInterval(interval);
            }
            el.textContent = current;
        }, 30);
    });
});
