'use strict';

// ================================================
//  HydroSmart — app.js
//  Node.js + NeonDB PostgreSQL + WebSocket
//  https://hydrosmart-groupe5.onrender.com
// ================================================

const express   = require('express');
const http      = require('http');
const WebSocket = require('ws');
const path      = require('path');
const { Pool }  = require('pg');

const app    = express();
const server = http.createServer(app);
const wss    = new WebSocket.Server({ server });
const PORT   = process.env.PORT || 3000;

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
        time_val TEXT    DEFAULT '18:00',
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
      INSERT INTO hs_schedule (enabled,time_val,duration,valves) SELECT false,'18:00',10,'1' WHERE NOT EXISTS (SELECT 1 FROM hs_schedule);
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

// ── WebSocket ────────────────────────────────────
function broadcast(obj) {
  const msg = JSON.stringify(obj);
  wss.clients.forEach(ws => { if (ws.readyState === WebSocket.OPEN) ws.send(msg); });
}

wss.on('connection', async ws => {
  console.log('🌐 Navigateur connecte');
  try {
    const [sensors] = await q('SELECT * FROM hs_sensors  ORDER BY id DESC LIMIT 1');
    const [valves]  = await q('SELECT * FROM hs_valves   ORDER BY id DESC LIMIT 1');
    const [cmds]    = await q('SELECT * FROM hs_commands ORDER BY id DESC LIMIT 1');
    const [sched]   = await q('SELECT * FROM hs_schedule ORDER BY id DESC LIMIT 1');
    const [status]  = await q('SELECT * FROM hs_status   ORDER BY id DESC LIMIT 1');
    ws.send(JSON.stringify({
      type:     'full_state',
      sensors:  sensors || null,
      valves:   valves  || { v1: false, v2: false },
      commands: cmds    || { sw1: false, sw2: false },
      schedule: sched   || {},
      lastSeen: status?.last_seen || 0,
    }));
  } catch(e) { console.error('WS init:', e.message); }
  ws.on('close', () => console.log('🌐 Navigateur deconnecte'));
});

// ================================================
//  ROUTES ESP32
// ================================================

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
    console.log(`📡 T=${temp}  H=${hum}  Sol=${soil}`);
    broadcast({ type: 'sensors', temp: +temp, hum: +hum, soil: Math.round(+soil), lastSeen: now });
    res.json({ success: true });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

app.post('/api/valve-feedback', authESP, async (req, res) => {
  const { v1, v2 } = req.body;
  try {
    await q('UPDATE hs_valves SET v1=$1, v2=$2, updated_at=$3', [!!v1, !!v2, Date.now()]);
    broadcast({ type: 'valve_status', v1: !!v1, v2: !!v2 });
    res.json({ success: true });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

app.get('/api/commands', authESP, async (req, res) => {
  try {
    const [cmds] = await q('SELECT sw1,sw2 FROM hs_commands ORDER BY id DESC LIMIT 1');
    res.json({ sw1: cmds?.sw1 || false, sw2: cmds?.sw2 || false });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

// ================================================
//  ROUTES NAVIGATEUR
// ================================================

app.post('/api/login', (req, res) => {
  const { email, password } = req.body;
  const ok_e = process.env.ADMIN_EMAIL    || 'admin@hydrosmart.io';
  const ok_p = process.env.ADMIN_PASSWORD || 'hydro2024';
  if (email === ok_e && password === ok_p) return res.json({ success: true });
  res.status(401).json({ success: false, message: 'Identifiants invalides' });
});

app.post('/api/valve', async (req, res) => {
  const { valve, state } = req.body;
  if (valve !== 1 && valve !== 2)
    return res.status(400).json({ success: false, message: 'valve 1 ou 2' });
  if (typeof state !== 'boolean')
    return res.status(400).json({ success: false, message: 'state boolean' });
  try {
    await q(`UPDATE hs_commands SET sw${valve}=$1, updated_at=$2`, [state, Date.now()]);
    console.log(`🎛️  Vanne ${valve} ${state ? 'ON' : 'OFF'}`);
    broadcast({ type: 'command_sent', valve, state });
    res.json({ success: true });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

app.post('/api/schedule', async (req, res) => {
  const { time, duration, valves } = req.body;
  if (!time || !duration || !Array.isArray(valves))
    return res.status(400).json({ success: false, message: 'time duration valves[] requis' });
  try {
    await q('UPDATE hs_schedule SET enabled=true,time_val=$1,duration=$2,valves=$3,updated_at=$4',
            [time, +duration, valves.join(','), Date.now()]);
    const sched = { enabled: true, time, duration, valves };
    console.log(`📅 ${time} ${duration}min [${valves}]`);
    broadcast({ type: 'schedule_updated', schedule: sched });
    res.json({ success: true, schedule: sched });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

app.delete('/api/schedule', async (req, res) => {
  try {
    await q('UPDATE hs_schedule SET enabled=false');
    broadcast({ type: 'schedule_updated', schedule: { enabled: false } });
    res.json({ success: true });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

app.get('/api/status', async (req, res) => {
  try {
    const [sensors] = await q('SELECT * FROM hs_sensors  ORDER BY id DESC LIMIT 1');
    const [valves]  = await q('SELECT * FROM hs_valves   ORDER BY id DESC LIMIT 1');
    const [sched]   = await q('SELECT * FROM hs_schedule ORDER BY id DESC LIMIT 1');
    const [status]  = await q('SELECT * FROM hs_status   ORDER BY id DESC LIMIT 1');
    res.json({ success: true, sensors, valves, schedule: sched, lastSeen: status?.last_seen });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

app.get('/health', (_, res) => res.json({ status: 'ok', ts: Date.now() }));

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'index.html'));
});

// ================================================
//  SCHEDULING AUTOMATIQUE
// ================================================
let wateringActive = false;
setInterval(async () => {
  try {
    const [s] = await q('SELECT * FROM hs_schedule ORDER BY id DESC LIMIT 1');
    if (!s?.enabled) return;
    const now = new Date().toTimeString().slice(0, 5);
    if (now === s.time_val && !wateringActive) {
      wateringActive = true;
      const valves = s.valves.split(',').map(Number);
      if (valves.includes(1)) await q('UPDATE hs_commands SET sw1=true');
      if (valves.includes(2)) await q('UPDATE hs_commands SET sw2=true');
      console.log(`⏰ Auto ${now} vannes [${valves}]`);
      broadcast({ type: 'auto_watering_start', valves });
      setTimeout(async () => {
        if (valves.includes(1)) await q('UPDATE hs_commands SET sw1=false');
        if (valves.includes(2)) await q('UPDATE hs_commands SET sw2=false');
        wateringActive = false;
        broadcast({ type: 'auto_watering_stop' });
        console.log('✅ Arrosage termine');
      }, s.duration * 60 * 1000);
    }
    if (now !== s.time_val) wateringActive = false;
  } catch(e) { console.error('Schedule:', e.message); }
}, 15000);

// ── Start ────────────────────────────────────────
initDB().then(() => {
  server.listen(PORT, '0.0.0.0', () => {
    console.log(`\n🌿 HydroSmart — https://hydrosmart-groupe5.onrender.com\n`);
  });
}).catch(err => { console.error('Start error:', err); process.exit(1); });
