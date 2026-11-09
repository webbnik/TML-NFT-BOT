// Theme and collectibles: apply the saved choices before the page paints (this
// file is loaded without defer/async in <head> on purpose), then wire up the buttons.
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

    // Collectibles (collections outside the full set) are hidden unless switched on
    let collectibles = false;
    try { collectibles = JSON.parse(localStorage.getItem('tml.showCollectibles')) === true; } catch (e) { }

    function applyCollectibles() {
        if (collectibles) document.documentElement.dataset.collectibles = 'on';
        else delete document.documentElement.dataset.collectibles;
        document.querySelectorAll('[data-collectibles-toggle]').forEach(button => {
            button.setAttribute('aria-pressed', String(collectibles));
            const label = collectibles ? button.dataset.labelOn : button.dataset.labelOff;
            if (label) button.textContent = label;
        });
    }

    applyTheme();
    applyCollectibles();
    document.addEventListener('DOMContentLoaded', () => {
        applyCollectibles();
        document.querySelectorAll('[data-collectibles-toggle]').forEach(button => {
            button.addEventListener('click', event => {
                event.preventDefault();
                collectibles = !collectibles;
                try { localStorage.setItem('tml.showCollectibles', JSON.stringify(collectibles)); } catch (e) { }
                applyCollectibles();
            });
        });
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
