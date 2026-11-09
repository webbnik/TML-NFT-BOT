// Price history page: floor price charts per collection (no chart library).
(() => {
    'use strict';

    const RANGES = [7, 30, 90, 365, 3650];
    const REFRESH_MS = 5 * 60 * 1000;
    const W = 600, H = 200, PAD = 12;          // SVG drawing area (scaled to the box)
    const SVG_NS = 'http://www.w3.org/2000/svg';

    const $ = (selector, root = document) => root.querySelector(selector);
    const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
    const store = {
        get(key, fallback) {
            try {
                const value = localStorage.getItem(key);
                return value === null ? fallback : JSON.parse(value);
            } catch (e) { return fallback; }
        },
        set(key, value) {
            try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { }
        },
    };

    const state = JSON.parse($('#initial-state').textContent);
    let days = RANGES.includes(store.get('tml.historyRange', 7)) ? store.get('tml.historyRange', 7) : 7;
    let unit = store.get('tml.historyUnit', 'SOL');
    if (unit !== 'SOL' && !state.currencies.some(c => c.symbol === unit)) unit = 'SOL';
    let data = null;

    // ---------- Formatting ----------
    const number = (value, decimals) =>
        value.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    const CRYPTO_DECIMALS = { SOLETH: 4, SOLBTC: 5 };

    function formatValue(value) {
        if (unit === 'SOL') return `${number(value, value < 10 ? 3 : 2)} SOL`;
        const currency = state.currencies.find(c => c.symbol === unit);
        const decimals = CRYPTO_DECIMALS[unit] ?? (Math.abs(value) >= 1000 ? 0 : 2);
        return `${currency.sign}${number(value, decimals)}`;
    }

    function formatTime(ms, withTime) {
        const options = { day: 'numeric', month: 'short' };
        if (days > 365) options.year = 'numeric';
        if (withTime) Object.assign(options, { hour: '2-digit', minute: '2-digit' });
        return new Date(ms).toLocaleString(undefined, options);
    }

    // ---------- Data ----------
    const toPoints = series => (series || [])
        .map(([time, value]) => [Date.parse(time), value])
        .filter(([time, value]) => !Number.isNaN(time) && Number.isFinite(value))
        .sort((a, b) => a[0] - b[0]);

    // Exchange rate in effect at a time: the last recorded rate before it
    function rateAt(rates, time, fallback) {
        if (!rates.length) return fallback;
        let lo = 0, hi = rates.length - 1;
        if (time < rates[0][0]) return rates[0][1];
        while (lo < hi) {
            const mid = Math.ceil((lo + hi) / 2);
            if (rates[mid][0] <= time) lo = mid; else hi = mid - 1;
        }
        return rates[lo][1];
    }

    // Floor history of one collection in SOL, ending at the current live floor
    function solSeries(nft) {
        const since = Date.now() - days * 86400 * 1000;
        const points = toPoints(data.history[nft.symbol]);
        const live = Date.parse(nft.fetched);
        if (!Number.isNaN(live) && live >= since) points.push([live, nft.floor]);
        return points.filter(([time]) => time >= since);
    }

    // Full set: the sum of each included collection's floor at every point in time,
    // starting once every collection has a recorded floor
    function fullSetSeries() {
        const parts = state.nfts.filter(nft => nft.include_in_total).map(solSeries);
        if (!parts.length || parts.some(p => !p.length)) return [];
        const start = Math.max(...parts.map(p => p[0][0]));
        const times = [...new Set(parts.flatMap(p => p.map(([time]) => time)))]
            .filter(time => time >= start)
            .sort((a, b) => a - b);
        const index = parts.map(() => 0);
        return times.map(time => [time, parts.reduce((sum, part, i) => {
            while (index[i] < part.length - 1 && part[index[i] + 1][0] <= time) index[i]++;
            return sum + part[index[i]][1];
        }, 0)]);
    }

    function inUnit(points) {
        if (unit === 'SOL') return points;
        const current = state.currencies.find(c => c.symbol === unit).price;
        const rates = toPoints((data.rates || {})[unit]);
        return points.map(([time, value]) => [time, value * rateAt(rates, time, current)]);
    }

    // ---------- Drawing ----------
    function svgElement(name, attributes) {
        const el = document.createElementNS(SVG_NS, name);
        Object.entries(attributes).forEach(([key, value]) => el.setAttribute(key, value));
        return el;
    }

    function div(className, text) {
        const el = document.createElement('div');
        el.className = className;
        if (text !== undefined) el.textContent = text;
        return el;
    }

    function drawChart(box, points) {
        const t0 = points[0][0], t1 = points[points.length - 1][0];
        const values = points.map(p => p[1]);
        let min = Math.min(...values), max = Math.max(...values);
        if (min === max) { min *= 0.99; max *= 1.01; }
        const x = t => (t1 === t0 ? W : (t - t0) / (t1 - t0) * W);
        const y = v => PAD + (1 - (v - min) / (max - min)) * (H - 2 * PAD);

        // Step line: a floor price holds until it changes
        let d = `M${x(points[0][0]).toFixed(2)} ${y(points[0][1]).toFixed(2)}`;
        for (let i = 1; i < points.length; i++) {
            d += ` H${x(points[i][0]).toFixed(2)} V${y(points[i][1]).toFixed(2)}`;
        }

        const svg = svgElement('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'none', 'aria-hidden': 'true' });
        for (const v of [max, (min + max) / 2, min]) {
            svg.append(svgElement('line', { class: 'grid', x1: 0, x2: W, y1: y(v).toFixed(2), y2: y(v).toFixed(2) }));
        }
        svg.append(svgElement('path', { class: 'area', d: `${d} V${H} H0 Z` }), svgElement('path', { class: 'line', d }));

        const labels = div('chart-labels');
        labels.append(div('chart-y chart-y-max', formatValue(max)), div('chart-y chart-y-min', formatValue(min)));
        const axis = div('chart-x');
        const withTime = days <= 2 || t1 - t0 < 2 * 86400 * 1000;
        axis.append(div('', formatTime(t0, withTime)), div('', formatTime(t1, withTime)));

        const cursor = div('chart-cursor');
        const dot = div('chart-dot');
        const tip = div('chart-tip');
        [cursor, dot, tip].forEach(el => { el.hidden = true; });

        box.replaceChildren(svg, labels, cursor, dot, tip, axis);
        box.setAttribute('role', 'img');
        box.setAttribute('aria-label',
            `Floor price from ${formatTime(t0, false)} to ${formatTime(t1, false)}: between ${formatValue(min)} and ${formatValue(max)}`);

        // Crosshair + tooltip for the value at the pointer
        function showAt(clientX) {
            const rect = svg.getBoundingClientRect();
            const fraction = Math.min(Math.max((clientX - rect.left) / rect.width, 0), 1);
            const time = t0 + fraction * (t1 - t0);
            let index = 0;
            while (index < points.length - 1 && points[index + 1][0] <= time) index++;
            const [, value] = points[index];
            const left = `${fraction * 100}%`;
            cursor.style.setProperty('left', left);
            dot.style.setProperty('left', left);
            dot.style.setProperty('top', `${y(value) / H * 100}%`);
            tip.textContent = `${formatValue(value)} · ${formatTime(time, true)}`;
            tip.style.setProperty('left', left);
            tip.classList.toggle('flip', fraction > 0.6);
            [cursor, dot, tip].forEach(el => { el.hidden = false; });
        }
        const hide = () => [cursor, dot, tip].forEach(el => { el.hidden = true; });
        box.onpointermove = event => showAt(event.clientX);
        box.onpointerdown = event => showAt(event.clientX);
        box.onpointerleave = hide;
    }

    function render() {
        $$('[data-range]').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.range) === days)));
        $$('[data-unit]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.unit === unit)));
        if (!data) return;

        let earliest = Infinity;
        const charts = [{ symbol: 'full-set', points: fullSetSeries() }]
            .concat(state.nfts.map(nft => ({ symbol: nft.symbol, points: solSeries(nft) })));
        charts.forEach(chart => {
            const card = $(`.chart-card[data-symbol="${CSS.escape(chart.symbol)}"]`);
            if (!card) return;
            const box = $('[data-chart]', card);
            const points = inUnit(chart.points);
            const change = $('[data-chart-change]', card);
            if (points.length < 3) {
                box.replaceChildren(div('chart-empty', 'Collecting data… The chart appears once a few points have been recorded.'));
                box.removeAttribute('role');
                $('[data-chart-last]', card).textContent = '';
                change.textContent = '';
                return;
            }
            earliest = Math.min(earliest, points[0][0]);
            drawChart(box, points);

            const first = points[0][1], last = points[points.length - 1][1];
            const pct = first ? (last - first) / first * 100 : 0;
            $('[data-chart-last]', card).textContent = formatValue(last);
            change.textContent = `${pct > 0.05 ? '▲' : pct < -0.05 ? '▼' : '•'} ${number(Math.abs(pct), 1)}%`;
            change.classList.toggle('up', pct > 0.05);
            change.classList.toggle('down', pct < -0.05);
            change.title = `Change over the selected period`;
        });

        const coverage = $('[data-coverage]');
        coverage.textContent = Number.isFinite(earliest)
            ? `Showing data since ${formatTime(earliest, true)}. Floor prices are recorded on every change and at least every 5 minutes.`
            : 'Floor prices are recorded on every change and at least every 5 minutes. Charts appear once a few points have been recorded.';
    }

    async function load() {
        try {
            const response = await fetch(`/api/history?days=${days}&rates=1&points=300`);
            if (!response.ok) return;
            data = await response.json();
            render();
        } catch (e) { /* keep what is shown */ }
    }

    $$('[data-range]').forEach(button => button.addEventListener('click', event => {
        event.preventDefault();
        days = Number(button.dataset.range);
        store.set('tml.historyRange', days);
        render();
        load();
    }));
    $$('[data-unit]').forEach(button => button.addEventListener('click', event => {
        event.preventDefault();
        unit = button.dataset.unit;
        store.set('tml.historyUnit', unit);
        render();
    }));

    render();
    load();
    setInterval(() => { if (!document.hidden) load(); }, REFRESH_MS);
})();
