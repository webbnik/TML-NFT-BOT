// Theme: apply the saved theme before the page paints (this file is loaded
// without defer/async in <head> on purpose), then wire up the theme button.
(() => {
    'use strict';
    const THEMES = ['auto', 'light', 'dark'];
    let theme = 'auto';
    try {
        const saved = JSON.parse(localStorage.getItem('tml.theme'));
        if (THEMES.includes(saved)) theme = saved;
    } catch (e) { }

    function applyTheme() {
        if (theme === 'auto') delete document.documentElement.dataset.theme;
        else document.documentElement.dataset.theme = theme;
        const button = document.querySelector('[data-theme-toggle]');
        if (!button) return;
        button.querySelector('use').setAttribute('href', `#i-theme-${theme}`);
        button.setAttribute('aria-label', `Theme: ${theme} (click to change)`);
        button.title = `Theme: ${theme}`;
    }

    applyTheme();
    document.addEventListener('DOMContentLoaded', () => {
        applyTheme();
        const button = document.querySelector('[data-theme-toggle]');
        if (!button) return;
        button.addEventListener('click', () => {
            theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
            try { localStorage.setItem('tml.theme', JSON.stringify(theme)); } catch (e) { }
            applyTheme();
        });
    });
})();
