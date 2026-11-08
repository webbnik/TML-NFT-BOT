// Live prices, currency switcher, holdings calculator and theme toggle.
(() => {
    'use strict';

    const POLL_MS = 15000;          // how often to ask the server for new prices
    const STALE_MS = 2 * 60 * 1000; // data older than this is shown as "delayed"

    // localStorage can be unavailable (private mode etc.), so never let it throw
    const store = {
        get(key, fallback) {
            try {
                const value = localStorage.getItem(key);
                return value === null ? fallback : JSON.parse(value);
            } catch (e) {
                return fallback;
            }
        },
        set(key, value) {
            try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { }
        },
    };

    const $ = (selector, root = document) => root.querySelector(selector);
    const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

    let state = JSON.parse($('#initial-state').textContent);
    let pollFailed = false;
    const previousFloors = {};

    // Currency: ?currency= in the URL wins, then the last one the viewer picked
    let currencySymbol = document.body.dataset.currency;
    if (!new URLSearchParams(location.search).has('currency')) {
        const saved = store.get('tml.currency', null);
        if (state.currencies.some(c => c.symbol === saved)) currencySymbol = saved;
    }

    let holdings = store.get('tml.holdings', {});
    let holdingsOn = store.get('tml.holdingsOn', false);

    // ---------- Formatting ----------
    const currency = () => state.currencies.find(c => c.symbol === currencySymbol) || state.currencies[0];

    const number = (value, decimals) =>
        value.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

    const formatSol = value => `${number(value, value < 10 ? 3 : 2)} SOL`;

    // Decimals per quote currency: crypto needs more than fiat
    const CRYPTO_DECIMALS = { SOLETH: 4, SOLBTC: 5 };
    const RATE_DECIMALS = { SOLETH: 5, SOLBTC: 7 };

    function formatMoney(sol) {
        const c = currency();
        const value = sol * c.price;
        const decimals = CRYPTO_DECIMALS[c.symbol] ?? (value >= 1000 ? 0 : 2);
        return `${c.sign}${number(value, decimals)}`;
    }

    function formatAgo(ms) {
        const seconds = Math.max(0, Math.round(ms / 1000));
        if (seconds < 60) return `${seconds}s ago`;
        const minutes = Math.round(seconds / 60);
        if (minutes < 60) return `${minutes} min ago`;
        return `${Math.round(minutes / 60)} h ago`;
    }

    const setText = (el, text) => { if (el && el.textContent !== text) el.textContent = text; };

    function flash(el, direction) {
        el.classList.remove('flash-up', 'flash-down');
        void el.offsetWidth; // restart the animation
        el.classList.add(direction > 0 ? 'flash-up' : 'flash-down');
    }

    // ---------- Rendering ----------
    function render() {
        const c = currency();

        setText($('[data-total-sol]'), formatSol(state.total_floor));
        setText($('[data-total-fiat]'), formatMoney(state.total_floor));
        setText($('[data-rate]'), `${c.sign}${number(c.price, RATE_DECIMALS[c.symbol] ?? 2)}`);
        document.title = `${formatSol(state.total_floor)} · Tomorrowland NFTs`;

        $$('.segmented [data-currency]').forEach(link => {
            link.setAttribute('aria-pressed', String(link.dataset.currency === c.symbol));
        });

        let holdingsSol = 0;
        let holdingsCount = 0;

        state.nfts.forEach(nft => {
            const card = $(`.card[data-symbol="${CSS.escape(nft.symbol)}"]`);
            if (!card) return;
            const field = name => $(`[data-field="${name}"]`, card);

            const floorEl = field('floor');
            setText(floorEl, formatSol(nft.floor));
            const previous = previousFloors[nft.symbol];
            if (previous !== undefined && previous !== nft.floor) flash(floorEl, nft.floor - previous);
            previousFloors[nft.symbol] = nft.floor;

            setText(field('floor-fiat'), formatMoney(nft.floor));
            setText(field('listed'), nft.listed.toLocaleString());
            setText(field('avg24h'), nft.avg24h ? formatSol(nft.avg24h) : '–');

            const deltaEl = field('delta');
            if (nft.avg24h > 0) {
                const pct = (nft.floor - nft.avg24h) / nft.avg24h * 100;
                const rounded = Math.abs(pct) < 0.05 ? 0 : pct;
                setText(deltaEl, `${rounded > 0 ? '▲' : rounded < 0 ? '▼' : '•'} ${number(Math.abs(rounded), 1)}% vs 24h`);
                deltaEl.classList.toggle('up', rounded > 0);
                deltaEl.classList.toggle('down', rounded < 0);
            } else {
                setText(deltaEl, '');
            }

            renderMedia(card, nft);

            const qty = holdings[nft.symbol] || 0;
            const input = $('[data-qty]', card);
            if (document.activeElement !== input) input.value = qty;
            setText(field('holding-value'), qty ? formatMoney(qty * nft.floor) : '');
            holdingsSol += qty * nft.floor;
            holdingsCount += qty;
        });

        setText($('[data-holdings-sol]'), formatSol(holdingsSol));
        setText($('[data-holdings-fiat]'), formatMoney(holdingsSol));
        setText($('[data-holdings-count]'), holdingsCount ? `${holdingsCount} NFT${holdingsCount === 1 ? '' : 's'}` : 'set how many you own below');

        renderStatus();
    }

    // ---------- Floor NFT artwork ----------
    // Animations only play while a card is on screen, and never when the
    // viewer asked for reduced motion or less data usage.
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const saveData = navigator.connection && navigator.connection.saveData;
    const allowVideo = () => !reduceMotion.matches && !saveData;
    const visibleCards = new Set();

    function updateVideo(card) {
        const video = $('[data-media-video]', card);
        const src = video.dataset.src;
        const shouldPlay = src && allowVideo() && visibleCards.has(card) && !document.hidden;
        if (shouldPlay) {
            if (video.getAttribute('src') !== src) {
                video.classList.remove('is-playing');
                video.src = src;
            }
            video.play().catch(() => { }); // autoplay can be refused; the poster stays
        } else if (!video.paused) {
            video.pause();
        }
    }

    function renderMedia(card, nft) {
        const floorNft = nft.floor_nft;
        const image = $('[data-media-image]', card);
        const video = $('[data-media-video]', card);
        const caption = $('[data-media-caption]', card);

        const imageSrc = (floorNft && floorNft.image) || nft.image;
        if (image.getAttribute('src') !== imageSrc) image.src = imageSrc;
        image.alt = floorNft ? floorNft.name : nft.name;
        $$('[data-media-link]', card).forEach(link => { link.href = floorNft ? floorNft.url : nft.url; });
        caption.hidden = !floorNft;
        setText($('[data-media-name]', caption), floorNft ? floorNft.name : '');

        const videoSrc = (floorNft && floorNft.video) || '';
        if ((video.dataset.src || '') !== videoSrc) {
            // The floor NFT changed: drop the old animation and load the new one
            video.pause();
            video.classList.remove('is-playing');
            video.removeAttribute('src');
            video.load();
            if (videoSrc) video.dataset.src = videoSrc;
            else delete video.dataset.src;
            updateVideo(card);
        }
    }

    const cards = $$('.card');
    cards.forEach(card => {
        const video = $('[data-media-video]', card);
        video.addEventListener('playing', () => video.classList.add('is-playing'));
    });

    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) visibleCards.add(entry.target);
                else visibleCards.delete(entry.target);
                updateVideo(entry.target);
            });
        }, { threshold: 0.35 });
        cards.forEach(card => observer.observe(card));
    }
    document.addEventListener('visibilitychange', () => cards.forEach(updateVideo));
    reduceMotion.addEventListener?.('change', () => cards.forEach(updateVideo));

    // ---------- Card tilt + light reflection (mouse/pen only) ----------
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
    const MAX_TILT = 3; // degrees; cards are wide, so keep it subtle

    cards.forEach(card => {
        card.addEventListener('pointermove', event => {
            if (!finePointer.matches || reduceMotion.matches) return;
            const rect = card.getBoundingClientRect();
            const x = (event.clientX - rect.left) / rect.width;  // 0..1
            const y = (event.clientY - rect.top) / rect.height;  // 0..1
            card.classList.add('is-tilting');
            card.style.setProperty('--ry', `${(x - 0.5) * 2 * MAX_TILT}deg`);
            card.style.setProperty('--rx', `${(0.5 - y) * 2 * MAX_TILT}deg`);
            card.style.setProperty('--gx', `${x * 100}%`);
            card.style.setProperty('--gy', `${y * 100}%`);
        });
        card.addEventListener('pointerleave', () => {
            card.classList.remove('is-tilting');
            card.style.setProperty('--rx', '0deg');
            card.style.setProperty('--ry', '0deg');
        });
    });

    function renderStatus() {
        const el = $('[data-status]');
        const age = Date.now() - Date.parse(state.updated);
        const stale = age > STALE_MS;
        el.classList.toggle('is-offline', pollFailed);
        el.classList.toggle('is-stale', !pollFailed && stale);
        let text;
        if (pollFailed) text = 'Offline';
        else if (stale) text = 'Delayed';
        else text = 'Live';
        setText($('[data-status-label]'), text);
        setText($('[data-status-age]'), formatAgo(age));
        el.title = `Prices last fetched ${new Date(state.updated).toLocaleString()}`;
    }

    // ---------- Live updates ----------
    async function poll() {
        if (document.hidden) return;
        try {
            const response = await fetch('/api/prices', { cache: 'no-store' });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            state = await response.json();
            pollFailed = false;
            render();
        } catch (e) {
            pollFailed = true;
            renderStatus();
        }
    }

    setInterval(poll, POLL_MS);
    setInterval(renderStatus, 1000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });

    // ---------- Currency switcher ----------
    $$('.segmented [data-currency]').forEach(link => {
        link.addEventListener('click', event => {
            event.preventDefault();
            currencySymbol = link.dataset.currency;
            store.set('tml.currency', currencySymbol);
            const url = new URL(location.href);
            url.searchParams.set('currency', currencySymbol);
            history.replaceState(null, '', url);
            render();
        });
    });

    // ---------- Holdings calculator ----------
    const holdingsToggle = $('[data-holdings-toggle]');

    function applyHoldingsToggle() {
        document.body.classList.toggle('holdings-on', holdingsOn);
        holdingsToggle.setAttribute('aria-pressed', String(holdingsOn));
    }

    holdingsToggle.addEventListener('click', () => {
        holdingsOn = !holdingsOn;
        store.set('tml.holdingsOn', holdingsOn);
        applyHoldingsToggle();
    });

    function setQty(symbol, qty) {
        holdings[symbol] = Math.max(0, Math.floor(Number(qty) || 0));
        store.set('tml.holdings', holdings);
        render();
    }

    $$('.card').forEach(card => {
        const symbol = card.dataset.symbol;
        const input = $('[data-qty]', card);
        input.addEventListener('input', () => setQty(symbol, input.value));
        input.addEventListener('blur', () => { input.value = holdings[symbol] || 0; });
        $$('[data-step]', card).forEach(button => {
            button.addEventListener('click', () => {
                setQty(symbol, (holdings[symbol] || 0) + Number(button.dataset.step));
            });
        });
    });

    // ---------- Theme toggle: auto → light → dark ----------
    const THEMES = ['auto', 'light', 'dark'];
    const themeButton = $('[data-theme-toggle]');
    let theme = store.get('tml.theme', 'auto');
    if (!THEMES.includes(theme)) theme = 'auto';

    function applyTheme() {
        if (theme === 'auto') delete document.documentElement.dataset.theme;
        else document.documentElement.dataset.theme = theme;
        $('use', themeButton).setAttribute('href', `#i-theme-${theme}`);
        themeButton.setAttribute('aria-label', `Theme: ${theme} (click to change)`);
        themeButton.title = `Theme: ${theme}`;
    }

    themeButton.addEventListener('click', () => {
        theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
        store.set('tml.theme', theme);
        applyTheme();
    });

    applyTheme();
    applyHoldingsToggle();
    render();
})();
