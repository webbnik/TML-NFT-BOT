// Apply the saved theme before the page paints, to avoid a flash of the wrong theme.
// Loaded without defer/async in <head> on purpose.
try {
    const theme = JSON.parse(localStorage.getItem('tml.theme'));
    if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme;
} catch (e) { }
