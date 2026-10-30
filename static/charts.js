// Shared Chart.js helpers for the employee and admin dashboards.
const C = { green: '#12805c', orange: '#f08a4b', red: '#c8473d', gold: '#d9a441', ink: '#3d3530', grid: 'rgba(61,53,48,.08)' };
const PALETTE = ['#12805c', '#f08a4b', '#d9a441', '#c8473d', '#7f9a55', '#6b4a3a', '#5b7fa6', '#b9a99b'];
const levelColor = v => (v >= 7 ? C.red : v >= 5 ? C.gold : C.green);
Chart.defaults.font.family = 'Urbanist, system-ui, sans-serif';
Chart.defaults.font.size = 13;
Chart.defaults.color = C.ink;
const yAxis = { min: 0, max: 10, ticks: { stepSize: 2 }, grid: { color: C.grid }, border: { display: false } };
const xAxis = { grid: { display: false }, ticks: { maxRotation: 40, autoSkipPadding: 12 } };
const charts = {};
function draw(id, config) {
  charts[id]?.destroy();
  charts[id] = new Chart(document.getElementById(id), { ...config,
    options: { responsive: true, maintainAspectRatio: false, ...config.options } });
}

function rolling(values, n = 7) {
  return values.map((_, i) => {
    const w = values.slice(Math.max(0, i - n + 1), i + 1);
    return +(w.reduce((a, b) => a + b, 0) / w.length).toFixed(2);
  });
}

function stressLine(id, rows, threshold, days) {
  const all = rolling(rows.map(r => r.avg));
  const from = new Date(Date.now() - days * 864e5).toISOString().slice(0, 10);
  const start = rows.findIndex(r => r.period >= from);
  const i = start < 0 ? rows.length : start;
  const shown = rows.slice(i);
  const label = p => new Date(p + 'T00:00').toLocaleDateString('en', { weekday: 'short', month: 'short', day: 'numeric' });
  draw(id, {
    type: 'line',
    data: {
      labels: shown.map(r => label(r.period)),
      datasets: [
        { label: 'Daily stress', data: shown.map(r => r.avg), borderColor: C.green, backgroundColor: '#fff',
          pointBorderColor: C.green, pointRadius: 3, borderWidth: 2.5, tension: 0.4 },
        { label: '7-day average', data: all.slice(i), borderColor: C.orange, backgroundColor: '#fff',
          pointRadius: 0, borderWidth: 2.5, tension: 0.4 },
        { label: 'Warning level', data: shown.map(() => threshold), borderColor: C.red, backgroundColor: C.red,
          borderDash: [6, 6], pointRadius: 0, borderWidth: 1.5 },
      ],
    },
    options: { scales: { y: yAxis, x: xAxis }, interaction: { mode: 'index', intersect: false },
      plugins: { legend: { position: 'top', align: 'start', labels: { usePointStyle: true, boxHeight: 7 } } } },
  });
}

function barChart(id, rows) {
  draw(id, {
    type: 'bar',
    data: { labels: rows.map(r => r.period),
      datasets: [{ label: 'Avg stress', data: rows.map(r => r.avg), backgroundColor: rows.map(r => levelColor(r.avg)),
        borderRadius: 6, maxBarThickness: 28 }] },
    options: { scales: { y: yAxis, x: xAxis }, plugins: { legend: { display: false } } },
  });
}

function doughnut(id, labels, values) {
  draw(id, {
    type: 'doughnut',
    data: { labels, datasets: [{ data: values, backgroundColor: PALETTE, borderWidth: 2, borderColor: '#fff' }] },
    options: { cutout: '62%', plugins: { legend: { position: 'right', labels: { usePointStyle: true, boxHeight: 7 } } } },
  });
}

function deltaText(id, delta, than) {
  const e = document.getElementById(id);
  if (delta === null || delta === undefined) { e.textContent = `No data for ${than} yet`; return; }
  e.textContent = `${delta > 0 ? '▲ +' : delta < 0 ? '▼ ' : ''}${delta} average stress since ${than}`;
  e.className = delta > 0 ? 'up' : delta < 0 ? 'down' : '';
}

function dayStrip(id, days) {
  document.getElementById(id).replaceChildren(...days.map((d) => {
    const c = document.createElement('span');
    c.className = 'day';
    if (d.avg !== null) c.style.background = levelColor(d.avg);
    c.classList.toggle('on', d.avg !== null);
    c.textContent = d.day;
    c.title = d.avg === null ? 'No check-in' : `Average ${d.avg}/10`;
    return c;
  }));
}
