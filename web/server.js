const path = require('path');
const fs = require('fs');
require('dotenv').config({ path: path.join(__dirname, '..', '.env'), quiet: true });
const express = require('express');
const { Pool } = require('pg');
const { marked } = require('marked');

const ROOT = path.join(__dirname, '..');
const app = express();
app.use(express.static(path.join(__dirname, 'public')));
app.use('/exports', express.static(path.join(ROOT, 'exports')));
app.get('/schema.json', (req, res) => res.sendFile(path.join(ROOT, 'schema.json')));

const hostname = process.env.HOSTNAME || 'localhost';
const port     = process.env.PORT || 3000;
const dbUrl = new URL(process.env.DATABASE_URL);
dbUrl.searchParams.delete('sslmode');
const db = new Pool({
  connectionString: dbUrl.toString(),
  ssl: { rejectUnauthorized: false }
});
app.set('views', path.join(__dirname, 'views'));
app.set('view engine', 'ejs');

const META = {
  title: 'Poopmap Global Dataset',
  description: 'Otvoreni skup podataka o korisnicima platforme Poopmap i njihovim poopsima, ' +
               'preslikanima na naselja i države.',
  author: 'Toni Bajan'
};

const COLUMNS = [
  ['user_id', 'ID', 'Korisnik'],
  ['user_username', 'Username', 'Korisnik'],
  ['user_poopsCount', 'Poopsa', 'Korisnik'],
  ['user_pinColor', 'Boja pina', 'Korisnik'],
  ['user_createdAt', 'Kreiran', 'Korisnik'],
  ['user_badgesCount', 'Značke', 'Korisnik'],
  ['user_followersCount', 'Pratitelji', 'Korisnik'],
  ['user_followingsCount', 'Prati', 'Korisnik'],
  ['user_countryCount', 'Br. država', 'Korisnik'],
  ['user_isPro', 'Pro', 'Korisnik'],
  ['user_isPrivate', 'Privatan', 'Korisnik'],
  ['user_poopsPerDay', 'Poopsa/dan', 'Korisnik'],
  ['poop_id', 'ID', 'Poop'],
  ['poop_createdAt', 'Vrijeme', 'Poop'],
  ['poop_latitude', 'Lat', 'Poop'],
  ['poop_longitude', 'Lon', 'Poop'],
  ['poop_isAirplane', 'Avion', 'Poop'],
  ['poop_note', 'Bilješka', 'Poop'],
  ['poop_pinColor', 'Boja pina', 'Poop'],
  ['poop_place', 'Mjesto', 'Poop'],
  ['poop_rating', 'Ocjena', 'Poop'],
  ['poop_aroma', 'Aroma', 'Poop'],
  ['town_id', 'ID', 'Naselje'],
  ['town_name', 'Naziv', 'Naselje'],
  ['town_admin1', 'Regija', 'Naselje'],
  ['town_latitude', 'Lat', 'Naselje'],
  ['town_longitude', 'Lon', 'Naselje'],
  ['town_population', 'Stanovnika', 'Naselje'],
  ['country_code', 'Kod', 'Država'],
  ['country_name', 'Naziv', 'Država'],
  ['country_continent', 'Kontinent', 'Država'],
  ['country_population', 'Stanovnika', 'Država'],
  ['country_areaKm2', 'Površina km²', 'Država']
];
const COLUMN_NAMES = COLUMNS.map(c => c[0]);

function buildFilter(q, field) {
  q = (q || '').trim();
  if (q === '') return { where: '', params: [] };
  const pattern = '%' + q.replace(/[\\%_]/g, '\\$&') + '%';
  const wildcard = `search_text LIKE lower($1)`;
  if (COLUMN_NAMES.includes(field)) {
    const prefilter = /["\\(),]/.test(q) ? '' : `${wildcard} AND `;
    return { where: `WHERE ${prefilter}"${field}"::text ILIKE $1`, params: [pattern] };
  }
  return { where: `WHERE ${wildcard}`, params: [pattern] };
}
const SELECT_COLS = COLUMN_NAMES.map(c => `"${c}"`).join(', ');

function buildOrder(sort, dir) {
  const col = COLUMN_NAMES.includes(sort) ? sort : 'poop_id';
  const d = dir === 'asc' ? 'ASC' : 'DESC';
  if (col === 'poop_id') return `ORDER BY poop_id ${d}`;
  return `ORDER BY "${col}" ${d} NULLS LAST, poop_id DESC`;
}

let totalCount = null;
async function countRows(where, params) {
  if (where === '' && totalCount !== null) return totalCount;
  const n = (await db.query(`SELECT count(*)::int AS n FROM poopmap_flat ${where}`, params)).rows[0].n;
  if (where === '') totalCount = n;
  return n;
}

app.get('/', async (req, res) => {
  const readme = fs.readFileSync(path.join(ROOT, 'README.md'), 'utf-8');
  res.render('index', { meta: META, readme: marked.parse(readme) });
});

app.get('/datatable', async (req, res) => {
  res.render('datatable', { meta: META, columns: COLUMNS });
});

app.get('/api/poops', async (req, res) => {
  const { where, params } = buildFilter(req.query.q, req.query.field);
  const limit = Math.min(Math.max(parseInt(req.query.limit) || 50, 1), 500);
  const page  = Math.max(parseInt(req.query.page) || 1, 1);
  try {
    const total = await countRows(where, params);
    const rows = (await db.query(
      `SELECT ${SELECT_COLS} FROM poopmap_flat ${where} ${buildOrder(req.query.sort, req.query.dir)}
       LIMIT ${limit} OFFSET ${(page - 1) * limit}`, params)).rows;
    res.send({ total, page, limit, rows });
  } catch (err) {
    console.error(err);
    res.status(500).send({ error: 'Greška pri dohvatu podataka' });
  }
});

function csvValue(v) {
  if (v === null || v === undefined) return '';
  const s = String(v);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function nest(rows) {
  const pick = (row, prefix) => Object.fromEntries(
    Object.entries(row).filter(([k]) => k.startsWith(prefix)).map(([k, v]) => [k.slice(prefix.length), v]));
  const users = new Map();
  for (const row of rows) {
    if (!users.has(row.user_id)) users.set(row.user_id, { ...pick(row, 'user_'), poops: [] });
    const town = row.town_id === null ? null : {
      ...pick(row, 'town_'),
      country: row.country_code === null ? null : pick(row, 'country_')
    };
    users.get(row.user_id).poops.push({ ...pick(row, 'poop_'), town });
  }
  return [...users.values()];
}

app.get('/api/poops/download', async (req, res) => {
  const { where, params } = buildFilter(req.query.q, req.query.field);
  const format = req.query.format === 'json' ? 'json' : 'csv';
  try {
    const rows = (await db.query(
      `SELECT ${SELECT_COLS} FROM poopmap_flat ${where} ORDER BY user_id, "poop_createdAt" DESC`, params)).rows;
    res.attachment(`poopmap_filtered.${format}`);
    if (format === 'json') {
      res.type('application/json').send(JSON.stringify(nest(rows), null, 2));
    } else {
      const lines = [COLUMN_NAMES.join(',')];
      for (const row of rows) lines.push(COLUMN_NAMES.map(c => csvValue(row[c])).join(','));
      res.type('text/csv').send(lines.join('\n') + '\n');
    }
  } catch (err) {
    console.error(err);
    res.status(500).send({ error: 'Greška pri preuzimanju podataka' });
  }
});

app.listen(port, hostname, () => {
  console.log(`Server running at http://${hostname}:${port}/`);
});
