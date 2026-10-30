const log = document.getElementById('log');
const rate = document.getElementById('rate');
const csrf = document.querySelector('meta[name=csrf]').content;
log.scrollTop = log.scrollHeight;
rate.oninput = () => (document.getElementById('rateVal').textContent = rate.value === '0' ? '–' : rate.value);

function add(sender, text, extraClass = '') {
  const d = document.createElement('div');
  d.className = `msg ${sender} ${extraClass}`;
  d.textContent = text; // textContent: never inject user text as HTML
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
  return d;
}

function levelClass(l) { return l >= 8 ? 'danger' : l >= 5 ? 'warning' : 'success'; }

document.getElementById('chatForm').onsubmit = async (e) => {
  e.preventDefault();
  const box = document.getElementById('msg');
  const text = box.value.trim();
  if (!text) return;
  add('user', text);
  box.value = '';
  const typing = add('bot', 'typing…', 'typing');
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF': csrf },
      body: JSON.stringify({ message: text, self_rating: rate.value === '0' ? null : rate.value }),
    });
    const data = await res.json();
    typing.remove();
    if (!res.ok) return add('bot', data.error || 'Something went wrong.');
    if (data.crisis) return add('bot', data.reply, 'crisis');

    add('bot', data.reply + '\n- ' + data.recommendations.join('\n- '));
    const d = data.detection;
    const a = document.getElementById('analysis');
    a.className = '';
    a.innerHTML = `<div class="fs-5 fw-semibold"></div>
      <div class="small text-muted mb-2">Confidence ${(d.confidence * 100).toFixed(0)}%</div>
      <div class="progress mb-1" role="progressbar" aria-label="confidence"><div class="progress-bar bg-brand" style="width:${d.confidence * 100}%"></div></div>
      <span class="badge text-bg-${levelClass(d.stress_level)} mt-2">Stress level ${d.stress_level}/10</span>
      <div class="small text-muted mt-2">${data.disclaimer}</div>`;
    a.firstElementChild.textContent = d.label;
    const ul = document.getElementById('recs');
    ul.innerHTML = '';
    data.recommendations.forEach((r) => { const li = document.createElement('li'); li.textContent = r; ul.appendChild(li); });
    data.warnings.forEach((w) => add('bot', '⚠ Early warning: ' + w + ' See the Alerts page.', 'warn'));
  } catch {
    typing.remove();
    add('bot', 'Network error — please try again.');
  }
};
