'use strict';

// ================================================
//  HydroSmart — app.js
//  VERSION HTTP ONLY (sans WebSocket)
//  - L'ESP32 poll /api/commands toutes les 800ms
//  - Le navigateur poll /api/status toutes les 2s
//  - Timezone UTC (Fly.io)
// ================================================

const express  = require('express');
const path     = require('path');
const { Pool } = require('pg');

const app  = express();
const PORT = process.env.PORT || 3000;

// ── NeonDB ──────────────────────────────────────
const pool = new Pool({
  connectionString: process.env.DATABASE_URL ||
    'postgresql://neondb_owner:npg_jiCSoE8M7kxy@ep-quiet-field-aigwxbil-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require',
  ssl: { rejectUnauthorized: false },
  max: 5,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,
});
pool.on('error', err => console.error('Pool error:', err.message));

async function q(sql, p = []) {
  const c = await pool.connect();
  try { return (await c.query(sql, p)).rows; }
  finally { c.release(); }
}

// ── Init tables ──────────────────────────────────
async function initDB() {
  const c = await pool.connect();
  try {
    await c.query(`
      CREATE TABLE IF NOT EXISTS hs_sensors (
        id          SERIAL PRIMARY KEY,
        temp        REAL,
        hum         REAL,
        soil        INTEGER,
        recorded_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT
      );
      CREATE TABLE IF NOT EXISTS hs_commands (
        id  SERIAL PRIMARY KEY,
        sw1 BOOLEAN DEFAULT FALSE,
        sw2 BOOLEAN DEFAULT FALSE,
        updated_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT
      );
      CREATE TABLE IF NOT EXISTS hs_valves (
        id  SERIAL PRIMARY KEY,
        v1  BOOLEAN DEFAULT FALSE,
        v2  BOOLEAN DEFAULT FALSE,
        updated_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT
      );
      CREATE TABLE IF NOT EXISTS hs_schedule (
        id       SERIAL PRIMARY KEY,
        enabled  BOOLEAN DEFAULT FALSE,
        time_val TEXT    DEFAULT '15:00',
        duration INTEGER DEFAULT 10,
        valves   TEXT    DEFAULT '1',
        updated_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT
      );
      CREATE TABLE IF NOT EXISTS hs_status (
        id        SERIAL PRIMARY KEY,
        last_seen BIGINT DEFAULT 0
      );
    `);
    await c.query(`
      INSERT INTO hs_commands (sw1,sw2) SELECT false,false WHERE NOT EXISTS (SELECT 1 FROM hs_commands);
      INSERT INTO hs_valves   (v1,v2)  SELECT false,false WHERE NOT EXISTS (SELECT 1 FROM hs_valves);
      INSERT INTO hs_schedule (enabled,time_val,duration,valves) SELECT false,'15:00',10,'1' WHERE NOT EXISTS (SELECT 1 FROM hs_schedule);
      INSERT INTO hs_status   (last_seen) SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM hs_status);
    `);
    console.log('✅ NeonDB OK');
  } finally { c.release(); }
}

// ── Middlewares ──────────────────────────────────
app.use(express.json());
app.use(express.static(path.join(__dirname, 'templates')));
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin',  '*');
  res.header('Access-Control-Allow-Headers', 'Content-Type, x-api-key');
  res.header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

// ── Auth ESP32 ───────────────────────────────────
const ESP32_KEY = process.env.ESP32_KEY || 'hydrosmart-esp32-key-2024';
function authESP(req, res, next) {
  const key = req.headers['x-api-key'] || req.query.key;
  if (key !== ESP32_KEY) return res.status(401).json({ success: false, message: 'Cle invalide' });
  next();
}

// ================================================
//  ROUTES ESP32 — HTTP
// ================================================

// POST /api/sensors — ESP32 envoie les données capteurs
app.post('/api/sensors', authESP, async (req, res) => {
  const { temp, hum, soil } = req.body;
  if (temp == null || hum == null || soil == null)
    return res.status(400).json({ success: false, message: 'temp hum soil requis' });
  try {
    const now = Date.now();
    await q('INSERT INTO hs_sensors (temp,hum,soil,recorded_at) VALUES ($1,$2,$3,$4)',
            [+temp, +hum, Math.round(+soil), now]);
    await q('UPDATE hs_status SET last_seen=$1', [now]);
    await q('DELETE FROM hs_sensors WHERE recorded_at < $1', [now - 86400000]);
    console.log(`📡 HTTP T=${temp}°C  H=${hum}%  Sol=${soil}%`);
    res.json({ success: true });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

// POST /api/valve-feedback — ESP32 confirme l'état des vannes
app.post('/api/valve-feedback', authESP, async (req, res) => {
  const { v1, v2 } = req.body;
  try {
    await q('UPDATE hs_valves SET v1=$1, v2=$2, updated_at=$3', [!!v1, !!v2, Date.now()]);
    console.log(`🚿 Feedback: V1=${v1}  V2=${v2}`);
    res.json({ success: true });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

// GET /api/commands — ESP32 poll les commandes (sw1/sw2)
app.get('/api/commands', authESP, async (req, res) => {
  try {
    const [cmds] = await q('SELECT sw1,sw2 FROM hs_commands ORDER BY id DESC LIMIT 1');
    res.json({ sw1: cmds?.sw1 || false, sw2: cmds?.sw2 || false });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

// ================================================
//  ROUTES NAVIGATEUR
// ================================================

// POST /api/login
app.post('/api/login', (req, res) => {
  const { email, password } = req.body;
  const ok_e = process.env.ADMIN_EMAIL    || 'hydrosmart@gmail.com';
  const ok_p = process.env.ADMIN_PASSWORD || 'groupe5';
  if (email === ok_e && password === ok_p) return res.json({ success: true });
  res.status(401).json({ success: false, message: 'Identifiants invalides' });
});

// POST /api/valve — navigateur commande une vanne
app.post('/api/valve', async (req, res) => {
  const { valve, state } = req.body;
  if (valve !== 1 && valve !== 2)
    return res.status(400).json({ success: false, message: 'valve 1 ou 2' });
  if (typeof state !== 'boolean')
    return res.status(400).json({ success: false, message: 'state boolean' });
  try {
    await q(`UPDATE hs_commands SET sw${valve}=$1, updated_at=$2`, [state, Date.now()]);
    console.log(`🎛️  Vanne ${valve} ${state ? 'ON' : 'OFF'}`);
    res.json({ success: true });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

// POST /api/schedule — navigateur configure le planning (heure déjà en UTC)
app.post('/api/schedule', async (req, res) => {
  const { time, duration, valves } = req.body;
  if (!time || !duration || !Array.isArray(valves))
    return res.status(400).json({ success: false, message: 'time duration valves[] requis' });
  try {
    await q('UPDATE hs_schedule SET enabled=true,time_val=$1,duration=$2,valves=$3,updated_at=$4',
            [time, +duration, valves.join(','), Date.now()]);
    const sched = { enabled: true, time, duration, valves };
    console.log(`📅 Planning UTC: ${time}  ${duration}min  [${valves}]`);
    res.json({ success: true, schedule: sched });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

// DELETE /api/schedule — désactiver le planning
app.delete('/api/schedule', async (req, res) => {
  try {
    await q('UPDATE hs_schedule SET enabled=false');
    res.json({ success: true });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

// GET /api/status — navigateur poll l'état complet
app.get('/api/status', async (req, res) => {
  try {
    const [sensors] = await q('SELECT * FROM hs_sensors  ORDER BY id DESC LIMIT 1');
    const [valves]  = await q('SELECT * FROM hs_valves   ORDER BY id DESC LIMIT 1');
    const [sched]   = await q('SELECT * FROM hs_schedule ORDER BY id DESC LIMIT 1');
    const [status]  = await q('SELECT * FROM hs_status   ORDER BY id DESC LIMIT 1');

    // ESP32 considéré en ligne si last_seen < 10s
    const esp32Online = status?.last_seen
      ? (Date.now() - Number(status.last_seen)) < 10000
      : false;

    res.json({
      success: true,
      sensors,
      valves,
      schedule: sched,
      lastSeen: status?.last_seen || 0,
      esp32Online,
    });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

// GET /health
app.get('/health', (_, res) => res.json({ status: 'ok', ts: Date.now() }));

// GET / — page principale
app.get('/', (req, res) => res.sendFile(path.join(__dirname, 'templates', 'index.html')));

// ================================================
//  SCHEDULING AUTOMATIQUE — UTC
// ================================================
let wateringActive     = false;
let lastScheduleMinute = '';

setInterval(async () => {
  try {
    const [s] = await q('SELECT * FROM hs_schedule ORDER BY id DESC LIMIT 1');
    if (!s?.enabled) return;

    const now    = new Date();
    const utcH   = String(now.getUTCHours()).padStart(2, '0');
    const utcM   = String(now.getUTCMinutes()).padStart(2, '0');
    const utcNow = `${utcH}:${utcM}`;

    if (utcNow === s.time_val && lastScheduleMinute !== utcNow && !wateringActive) {
      lastScheduleMinute = utcNow;
      wateringActive     = true;
      const valves       = s.valves.split(',').map(Number);

      if (valves.includes(1)) await q('UPDATE hs_commands SET sw1=true');
      if (valves.includes(2)) await q('UPDATE hs_commands SET sw2=true');

      console.log(`⏰ Auto UTC ${utcNow} → vannes [${valves}]`);

      setTimeout(async () => {
        if (valves.includes(1)) await q('UPDATE hs_commands SET sw1=false');
        if (valves.includes(2)) await q('UPDATE hs_commands SET sw2=false');
        wateringActive = false;
        console.log('✅ Arrosage automatique terminé');
      }, s.duration * 60 * 1000);
    }

    if (utcNow !== s.time_val) lastScheduleMinute = '';

  } catch(e) { console.error('Schedule error:', e.message); }
}, 1000);

// ── Start ────────────────────────────────────────
initDB().then(() => {
  app.listen(PORT, '0.0.0.0', () => {
    console.log(`\n🌿 HydroSmart — https://hydrosmart-groupe-iot.fly.dev`);
    console.log(`   Mode : HTTP ONLY (polling)`);
    console.log(`   Timezone serveur : UTC (Fly.io)\n`);
  });
}).catch(err => { console.error('Start error:', err); process.exit(1); });
