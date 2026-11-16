const state = { q: '', field: 'all', page: 1, limit: 50, sort: 'poop_id', dir: 'desc', total: 0 };

const tbody    = document.querySelector('#table tbody');
const status   = document.getElementById('status');
const pageinfo = document.getElementById('pageinfo');
const dlCsv    = document.getElementById('dl-csv');
const dlJson   = document.getElementById('dl-json');

function filterParams() {
  const p = new URLSearchParams();
  if (state.q) { p.set('q', state.q); p.set('field', state.field); }
  return p;
}

function formatCell(col, v) {
  if (v === null || v === undefined || v === '') return '';
  if (typeof v === 'boolean') return v ? 'da' : 'ne';
  if (col.endsWith('createdAt')) return v.replace('T', ' ').slice(0, 19);
  if (col.endsWith('itude') || col.endsWith('PerDay')) return Number(v).toFixed(4);
  return String(v);
}

function render(rows) {
  tbody.replaceChildren();
  if (rows.length === 0) {
    const tr = tbody.insertRow();
    const td = tr.insertCell();
    td.colSpan = COLUMNS.length;
    td.className = 'empty';
    td.textContent = 'Nema podataka za zadani filtar.';
    return;
  }
  for (const row of rows) {
    const tr = tbody.insertRow();
    for (const col of COLUMNS) {
      const td = tr.insertCell();
      td.textContent = formatCell(col, row[col]);   // textContent: bez XSS-a iz bilješki
      if (col.endsWith('pinColor') && row[col]) {
        const dot = document.createElement('span');
        dot.className = 'dot';
        dot.style.background = row[col];
        td.prepend(dot);
      }
      if (col === 'town_name' && row[col] === 'wilderness') td.classList.add('wild');
    }
  }
}

async function load() {
  const p = filterParams();
  p.set('page', state.page);
  p.set('limit', state.limit);
  p.set('sort', state.sort);
  p.set('dir', state.dir);
  status.textContent = 'Učitavanje…';
  try {
    const res = await fetch('/api/poops?' + p);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    state.total = data.total;
    render(data.rows);
    const pages = Math.max(Math.ceil(data.total / state.limit), 1);
    const from = data.total ? (state.page - 1) * state.limit + 1 : 0;
    const to = Math.min(state.page * state.limit, data.total);
    status.textContent = `${data.total.toLocaleString('hr-HR')} zapisa` + (state.q ? ` za "${state.q}"` : '');
    pageinfo.textContent = `${from}–${to} · stranica ${state.page} / ${pages}`;
    document.getElementById('prev').disabled = state.page <= 1;
    document.getElementById('next').disabled = state.page >= pages;
  } catch (err) {
    status.textContent = 'Greška: ' + err.message;
  }
  const fp = filterParams().toString();
  dlCsv.href  = '/api/poops/download?format=csv'  + (fp ? '&' + fp : '');
  dlJson.href = '/api/poops/download?format=json' + (fp ? '&' + fp : '');
  document.querySelectorAll('th[data-col]').forEach(th => {
    th.classList.toggle('sorted', th.dataset.col === state.sort);
    th.dataset.dir = th.dataset.col === state.sort ? state.dir : '';
  });
}

document.getElementById('filter').addEventListener('submit', e => {
  e.preventDefault();
  state.q = document.getElementById('q').value.trim();
  state.field = document.getElementById('field').value;
  state.page = 1;
  load();
});

document.getElementById('reset').addEventListener('click', () => {
  document.getElementById('q').value = '';
  document.getElementById('field').value = 'all';
  state.q = ''; state.field = 'all'; state.page = 1;
  load();
});

document.getElementById('prev').addEventListener('click', () => { state.page--; load(); });
document.getElementById('next').addEventListener('click', () => { state.page++; load(); });
document.getElementById('limit').addEventListener('change', e => {
  state.limit = parseInt(e.target.value); state.page = 1; load();
});

document.querySelectorAll('th[data-col]').forEach(th => th.addEventListener('click', () => {
  const col = th.dataset.col;
  state.dir = state.sort === col && state.dir === 'desc' ? 'asc' : 'desc';
  state.sort = col;
  state.page = 1;
  load();
}));

load();
