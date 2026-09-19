// SIGNAL dashboard — Stage 1 scaffold
// No live data wiring yet. This file currently only handles navigation UX.
// Stage 3 (data integration) will add fetch calls to /data/*.json files
// produced by GitHub Actions, and will populate the ticker, exec summary,
// and section panels currently marked as placeholders.

document.addEventListener('DOMContentLoaded', () => {

  /* ---- Mobile rail toggle ---- */
  const railToggle = document.getElementById('railToggle');
  const rail = document.getElementById('rail');

  if (railToggle && rail) {
    railToggle.addEventListener('click', () => {
      const isOpen = rail.classList.toggle('is-open');
      railToggle.setAttribute('aria-expanded', String(isOpen));
    });

    // Close the rail after tapping a link on mobile
    rail.querySelectorAll('.rail-link').forEach(link => {
      link.addEventListener('click', () => {
        rail.classList.remove('is-open');
        railToggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  /* ---- Scroll-spy: highlight the nav link for the section in view ---- */
  const sections = Array.from(document.querySelectorAll('main section[id], main .panel[id]'));
  const navLinks = Array.from(document.querySelectorAll('.rail-link'));

  const setActive = (id) => {
    navLinks.forEach(link => {
      link.classList.toggle('is-active', link.getAttribute('href') === `#${id}`);
    });
  };

  if ('IntersectionObserver' in window && sections.length) {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter(e => e.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) setActive(visible.target.id);
    }, { rootMargin: '-20% 0px -70% 0px', threshold: [0, 0.25, 0.5, 1] });

    sections.forEach(section => observer.observe(section));
  }

  /* ---- Market data (Stage 3) ---- */
  loadMarketData();
});

const LABELS = {
  sp500: 'S&P 500', nasdaq: 'Nasdaq', dow: 'Dow', russell2000: 'Russell 2000', vix: 'VIX',
  us5y: '5-Year', us10y: '10-Year', us30y: '30-Year',
  wti_crude: 'WTI Crude', brent_crude: 'Brent Crude', natural_gas: 'Natural Gas',
  dollar_index: 'Dollar Index', eur_usd: 'EUR/USD',
};

function formatPrice(value, category) {
  if (value === null || value === undefined) return '—';
  if (category === 'yields') return `${value.toFixed(2)}%`;
  if (category === 'energy' || category === 'fx') return `$${value.toFixed(2)}`;
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatChange(change, pct) {
  if (change === null || change === undefined) return '';
  const sign = change >= 0 ? '+' : '';
  const pctStr = pct !== null && pct !== undefined ? ` (${sign}${pct.toFixed(2)}%)` : '';
  return `${sign}${change.toFixed(2)}${pctStr}`;
}

function changeClass(change) {
  if (change === null || change === undefined) return '';
  return change > 0 ? 'is-positive' : change < 0 ? 'is-negative' : '';
}

function renderTable(container, category, entries) {
  if (!entries || Object.keys(entries).length === 0) {
    container.innerHTML = '<p class="ph-block">No data available right now.</p>';
    return;
  }

  const rows = Object.entries(entries).map(([key, q]) => {
    const label = LABELS[key] || key;
    if (q.status === 'error') {
      return `<div class="data-row"><span class="data-label">${label}</span><span class="data-value is-muted">unavailable</span></div>`;
    }
    return `
      <div class="data-row">
        <span class="data-label">${label}</span>
        <span class="data-value">${formatPrice(q.price, category)}</span>
        <span class="data-change ${changeClass(q.change)}">${formatChange(q.change, q.percent_change)}</span>
      </div>`;
  }).join('');

  container.innerHTML = rows;
}

function updateTicker(data) {
  document.querySelectorAll('[data-field]').forEach(el => {
    const [category, key] = el.getAttribute('data-field').split('.');
    const q = data[category]?.[key];
    if (!q || q.status === 'error' || q.price === undefined) {
      el.textContent = '—';
      return;
    }
    const unit = el.getAttribute('data-unit');
    const value = unit === '%' ? `${q.price.toFixed(2)}%`
                : unit === '$' ? `$${q.price.toFixed(2)}`
                : formatPrice(q.price, category);
    const dir = q.change > 0 ? '▲' : q.change < 0 ? '▼' : '';
    el.textContent = `${value} ${dir}`;
    el.classList.remove('is-positive', 'is-negative');
    if (changeClass(q.change)) el.classList.add(changeClass(q.change));
  });
}

function setStatus(generatedAt, ok) {
  const statusText = document.getElementById('statusText');
  const statusDot = document.getElementById('statusDot');
  if (!statusText || !statusDot) return;

  if (!ok || !generatedAt) {
    statusText.textContent = 'Market data unavailable';
    statusDot.classList.remove('is-live');
    return;
  }

  const date = new Date(generatedAt);
  const label = date.toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  });
  statusText.textContent = `Market data updated ${label}`;
  statusDot.classList.add('is-live');
}

async function loadMarketData() {
  const equitiesTable = document.getElementById('equitiesTable');
  const yieldsTable = document.getElementById('yieldsTable');
  const energyTable = document.getElementById('energyTable');

  try {
    const res = await fetch('data/market.json', { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (!data.generated_at) {
      // Placeholder file — Action hasn't run yet.
      const msg = '<p class="ph-block">Waiting on the first automated data run.</p>';
      if (equitiesTable) equitiesTable.innerHTML = msg;
      if (yieldsTable) yieldsTable.innerHTML = msg;
      if (energyTable) energyTable.innerHTML = msg;
      setStatus(null, false);
      return;
    }

    if (equitiesTable) renderTable(equitiesTable, 'indices', data.indices);
    if (yieldsTable) renderTable(yieldsTable, 'yields', data.yields);
    if (energyTable) renderTable(energyTable, 'energy', data.energy);
    updateTicker(data);
    setStatus(data.generated_at, true);
  } catch (err) {
    console.error('Market data fetch failed:', err);
    const msg = '<p class="ph-block">Couldn\'t load market data right now.</p>';
    if (equitiesTable) equitiesTable.innerHTML = msg;
    if (yieldsTable) yieldsTable.innerHTML = msg;
    if (energyTable) energyTable.innerHTML = msg;
    setStatus(null, false);
  }
}
