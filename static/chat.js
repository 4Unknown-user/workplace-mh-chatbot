const log = document.getElementById('log');
const rate = document.getElementById('rate');
const box = document.getElementById('msg');
const csrf = document.querySelector('meta[name=csrf]').content;
log.scrollTop = log.scrollHeight;
rate.oninput = () => (document.getElementById('rateVal').textContent = rate.value === '0' ? '–' : rate.value);

// el() always uses textContent: user and model text is never injected as HTML
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function add(sender, text, extraClass = '') {
  const m = el('div', `msg ${sender} ${extraClass}`);
  const ic = el('span', 'who-ic');
  ic.appendChild(el('i', `bi ${sender === 'bot' ? 'bi-flower1' : 'bi-person'}`));
  const b = el('div', 'bubble', text);
  m.append(ic, b);
  log.appendChild(m);
  log.scrollTop = log.scrollHeight;
  return b;
}

function insight(bubble, d, recs, disclaimer) {
  const card = el('div', 'insight');
  const head = el('div', 'insight-head');
  head.append(el('b', '', d.label), el('span', `lvl lvl-${d.stress_level >= 8 ? 'high' : d.stress_level >= 5 ? 'mid' : 'low'}`, `Stress ${d.stress_level}/10`));
  const bar = el('div', 'conf');
  const fill = el('i');
  fill.style.width = `${d.confidence * 100}%`;
  bar.appendChild(fill);
  const ul = el('ul', 'recs');
  recs.forEach((r) => ul.appendChild(el('li', '', r)));
  card.append(head, bar, el('small', '', `Model confidence ${(d.confidence * 100).toFixed(0)}%`), ul, el('small', 'muted', disclaimer));
  bubble.appendChild(card);
  log.scrollTop = log.scrollHeight;
}

document.querySelectorAll('.topic').forEach((t) => {
  t.onclick = () => { box.value = t.dataset.starter; box.focus(); };
});

box.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); document.getElementById('chatForm').requestSubmit(); }
});

document.getElementById('chatForm').onsubmit = async (e) => {
  e.preventDefault();
  const text = box.value.trim();
  if (!text) return;
  add('user', text);
  box.value = '';
  const typing = add('bot', 'typing…', 'typing').parentElement;
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
    insight(add('bot', data.reply), data.detection, data.recommendations, data.disclaimer);
    data.warnings.forEach((w) => add('bot', `Early warning: ${w} See your Alerts page.`, 'warn'));
  } catch {
    typing.remove();
    add('bot', 'Network error, please try again.');
  }
};
