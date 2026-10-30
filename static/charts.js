// Shared Chart.js helpers for the employee and admin dashboards.
const BRAND = '#4f46e5';
const PALETTE = ['#4f46e5', '#0ea5e9', '#f59e0b', '#ef4444', '#10b981', '#8b5cf6', '#ec4899', '#64748b'];
const levelColor = v => (v >= 7 ? '#ef4444' : v >= 5 ? '#f59e0b' : '#10b981');
const yAxis = { min: 0, max: 10, title: { display: true, text: 'Stress (1-10)' } };

function lineChart(id, rows, threshold) {
  new Chart(document.getElementById(id), {
    type: 'line',
    data: {
      labels: rows.map(r => r.period),
      datasets: [
        { label: 'Avg stress', data: rows.map(r => r.avg), borderColor: BRAND, tension: 0.3, fill: false,
          pointBackgroundColor: rows.map(r => levelColor(r.avg)) },
        { label: 'Warning threshold', data: rows.map(() => threshold), borderColor: '#ef4444',
          borderDash: [6, 6], pointRadius: 0 },
      ],
    },
    options: { scales: { y: yAxis } },
  });
}

function barChart(id, rows) {
  new Chart(document.getElementById(id), {
    type: 'bar',
    data: { labels: rows.map(r => r.period),
      datasets: [{ label: 'Avg stress', data: rows.map(r => r.avg), backgroundColor: rows.map(r => levelColor(r.avg)) }] },
    options: { scales: { y: yAxis }, plugins: { legend: { display: false } } },
  });
}

function doughnut(id, labels, values) {
  new Chart(document.getElementById(id), {
    type: 'doughnut',
    data: { labels, datasets: [{ data: values, backgroundColor: PALETTE }] },
    options: { plugins: { legend: { position: 'bottom' } } },
  });
}
