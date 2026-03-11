/**
 * KangaBase WebUI - JavaScript
 * Minimal JS for htmx integration and UI interactions
 */

// htmx configuration
document.addEventListener('DOMContentLoaded', function() {
    // Configure htmx
    if (typeof htmx !== 'undefined') {
        htmx.config.globalViewTransitions = true;
        htmx.config.defaultSwapStyle = 'innerHTML';
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K → Focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const search = document.getElementById('schema-search');
            if (search) search.focus();
        }

        // Escape → Close modals/details
        if (e.key === 'Escape') {
            closeAllDetails();
        }
    });
});

// Close all expanded details
function closeAllDetails() {
    document.querySelectorAll('[id^="detail-"]:not(.hidden)').forEach(el => {
        el.classList.add('hidden');
    });
    document.querySelectorAll('[id^="audit-detail-"]:not(.hidden)').forEach(el => {
        el.classList.add('hidden');
    });
    document.querySelectorAll('[id^="agent-detail-"]:not(.hidden)').forEach(el => {
        el.classList.add('hidden');
    });
    // Reset chevrons
    document.querySelectorAll('[id^="chevron-"], [id^="audit-chevron-"], [id^="agent-chevron-"]').forEach(el => {
        el.style.transform = '';
    });
}

// Copy text to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard');
    });
}

// Toast notification
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `fixed bottom-6 right-6 px-4 py-3 rounded-lg shadow-lg text-sm font-medium z-50 transition-all transform translate-y-0 opacity-100 ${
        type === 'success' ? 'bg-green-600 text-white' :
        type === 'error' ? 'bg-red-600 text-white' :
        'bg-gray-800 text-white'
    }`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(1rem)';
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

// htmx event handlers
document.body.addEventListener('htmx:afterRequest', function(evt) {
    if (evt.detail.failed) {
        showToast('Request failed', 'error');
    }
});

// Loading indicator
document.body.addEventListener('htmx:beforeRequest', function(evt) {
    const target = evt.detail.target;
    if (target) {
        target.style.opacity = '0.6';
    }
});

document.body.addEventListener('htmx:afterSwap', function(evt) {
    const target = evt.detail.target;
    if (target) {
        target.style.opacity = '1';
    }
});

// Table select helper for Explorer
function loadTable(tableName) {
    if (tableName) {
        htmx.ajax('GET', '/explorer/table/' + tableName, '#table-content');
    }
}
