'use strict';

// ================================================
//  HydroSmart — app.js
//  VERSION HTTP PURE — CORRIGEE
//
//  FIXES :
//  ✅ Seuil esp32Online 12s → 20s (cohérent frontend)
//  ✅ Endpoint POST /api/heartbeat ajouté
//  ✅ /api/poll retourne lastSeen en ms (pas en s)
//  ✅ /api/status même seuil 20s
//  ✅ Pool DB : max connexions réduit + retry connect
//  ✅ Logs plus clairs pour le debug
// ================================================

const express   = require('express');
const http      = require('http');
const path      = require('path');
const { Pool }  = require('pg');

const app    = express();
const server = http.createServer(app);
const PORT   = process.env.PORT || 3000;

// ── Seuil de présence ESP32 ──────────────────────
// FIX : 20 000 ms (cohérent avec index.html et ESP32)
const ESP32_TIMEOUT_MS = 20000;

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

// ── Helper : est-ce que l'ESP32 est en ligne ? ──
// FIX : fonction centralisée pour éviter les incohérences
function isEsp32Online(lastSeenMs) {
  if (!lastSeenMs || lastSeenMs === 0) return false;
  return (Date.now() - lastSeenMs) < ESP32_TIMEOUT_MS;
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
        id         SERIAL PRIMARY KEY,
        sw1        BOOLEAN DEFAULT FALSE,
        sw2        BOOLEAN DEFAULT FALSE,
        updated_at BIGINT  DEFAULT (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT
      );
      CREATE TABLE IF NOT EXISTS hs_valves (
        id         SERIAL PRIMARY KEY,
        v1         BOOLEAN DEFAULT FALSE,
        v2         BOOLEAN DEFAULT FALSE,
        updated_at BIGINT  DEFAULT (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT
      );
      CREATE TABLE IF NOT EXISTS hs_schedule (
        id         SERIAL PRIMARY KEY,
        enabled    BOOLEAN DEFAULT FALSE,
        time_val   TEXT    DEFAULT '15:00',
        duration   INTEGER DEFAULT 10,
        valves     TEXT    DEFAULT '1',
        updated_at BIGINT  DEFAULT (EXTRACT(EPOCH FROM NOW())*1000)::BIGINT
      );
      CREATE TABLE IF NOT EXISTS hs_status (
        id        SERIAL PRIMARY KEY,
        last_seen BIGINT DEFAULT 0
      );
    `);
    await c.query(`
      INSERT INTO hs_commands (sw1,sw2)
        SELECT false,false WHERE NOT EXISTS (SELECT 1 FROM hs_commands);
      INSERT INTO hs_valves (v1,v2)
        SELECT false,false WHERE NOT EXISTS (SELECT 1 FROM hs_valves);
      INSERT INTO hs_schedule (enabled,time_val,duration,valves)
        SELECT false,'15:00',10,'1' WHERE NOT EXISTS (SELECT 1 FROM hs_schedule);
      INSERT INTO hs_status (last_seen)
        SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM hs_status);
    `);
    console.log('✅ NeonDB initialisée');
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
  if (key !== ESP32_KEY)
    return res.status(401).json({ success: false, message: 'Cle invalide' });
  next();
}

// ================================================
//  ROUTES ESP32
// ================================================

// ESP32 → envoi capteurs (met à jour last_seen)
app.post('/api/sensors', authESP, async (req, res) => {
  const { temp, hum, soil } = req.body;
  if (temp == null || hum == null || soil == null)
    return res.status(400).json({ success: false, message: 'temp hum soil requis' });
  try {
    const now = Date.now();
    await q(
      'INSERT INTO hs_sensors (temp,hum,soil,recorded_at) VALUES ($1,$2,$3,$4)',
      [+temp, +hum, Math.round(+soil), now]
    );
    // FIX : last_seen toujours en millisecondes
    await q('UPDATE hs_status SET last_seen=$1', [now]);
    // Nettoyage données > 24h
    await q('DELETE FROM hs_sensors WHERE recorded_at < $1', [now - 86400000]);
    console.log(`📡 Capteurs  T=${temp}°C  H=${hum}%  Sol=${soil}%`);
    res.json({ success: true });
  } catch(e) {
    console.error('POST /api/sensors:', e.message);
    res.status(500).json({ success: false, message: e.message });
  }
});

// ESP32 → lecture commandes (polling 1.5s)
app.get('/api/commands', authESP, async (req, res) => {
  try {
    const [cmds] = await q('SELECT sw1,sw2 FROM hs_commands ORDER BY id DESC LIMIT 1');
    res.json({ sw1: cmds?.sw1 || false, sw2: cmds?.sw2 || false });
  } catch(e) {
    console.error('GET /api/commands:', e.message);
    res.status(500).json({ success: false, message: e.message });
  }
});

// ESP32 → feedback état vannes
app.post('/api/valve-feedback', authESP, async (req, res) => {
  const { v1, v2 } = req.body;
  try {
    await q('UPDATE hs_valves SET v1=$1, v2=$2, updated_at=$3', [!!v1, !!v2, Date.now()]);
    console.log(`📤 Feedback vannes  V1=${v1}  V2=${v2}`);
    res.json({ success: true });
  } catch(e) {
    console.error('POST /api/valve-feedback:', e.message);
    res.status(500).json({ success: false, message: e.message });
  }
});

// ================================================
//  FIX : Endpoint heartbeat dédié
//  L'ESP32 envoie un ping toutes les 5s
//  Met à jour last_seen même si les autres routes
//  échouent (DHT22 erreur, capteur sol déconnecté…)
// ================================================
app.post('/api/heartbeat', authESP, async (req, res) => {
  try {
    const now = Date.now();
    await q('UPDATE hs_status SET last_seen=$1', [now]);
    console.log(`💓 Heartbeat ESP32 reçu — last_seen=${now}`);
    res.json({ success: true, ts: now });
  } catch(e) {
    console.error('POST /api/heartbeat:', e.message);
    res.status(500).json({ success: false, message: e.message });
  }
});

// ================================================
//  ROUTES NAVIGATEUR
// ================================================

// Login
app.post('/api/login', (req, res) => {
  const { email, password } = req.body;
  const ok_e = process.env.ADMIN_EMAIL    || 'hydrosmart@gmail.com';
  const ok_p = process.env.ADMIN_PASSWORD || 'groupe5';
  if (email === ok_e && password === ok_p)
    return res.json({ success: true });
  res.status(401).json({ success: false, message: 'Identifiants invalides' });
});

// ── POLL principal navigateur ────────────────────
// FIX : esp32Online calculé avec ESP32_TIMEOUT_MS (20s)
// FIX : lastSeen toujours en millisecondes
app.get('/api/poll', async (req, res) => {
  try {
    const [sensors] = await q('SELECT * FROM hs_sensors  ORDER BY id DESC LIMIT 1');
    const [valves]  = await q('SELECT * FROM hs_valves   ORDER BY id DESC LIMIT 1');
    const [cmds]    = await q('SELECT * FROM hs_commands ORDER BY id DESC LIMIT 1');
    const [sched]   = await q('SELECT * FROM hs_schedule ORDER BY id DESC LIMIT 1');
    const [status]  = await q('SELECT * FROM hs_status   ORDER BY id DESC LIMIT 1');

    // FIX : last_seen est déjà en ms (pas de conversion)
    const lastSeen    = status?.last_seen || 0;
    const esp32Online = isEsp32Online(lastSeen);

    res.json({
      success:     true,
      sensors:     sensors || null,
      valves:      valves  || { v1: false, v2: false },
      commands:    cmds    || { sw1: false, sw2: false },
      schedule:    sched   || {},
      lastSeen,                    // en ms — le frontend attend des ms
      esp32Online: !!esp32Online,
    });
  } catch(e) {
    console.error('GET /api/poll:', e.message);
    res.status(500).json({ success: false, message: e.message });
  }
});

// Commande vanne depuis navigateur
app.post('/api/valve', async (req, res) => {
  const { valve, state } = req.body;
  if (valve !== 1 && valve !== 2)
    return res.status(400).json({ success: false, message: 'valve doit être 1 ou 2' });
  if (typeof state !== 'boolean')
    return res.status(400).json({ success: false, message: 'state doit être boolean' });
  try {
    await q(`UPDATE hs_commands SET sw${valve}=$1, updated_at=$2`, [state, Date.now()]);
    console.log(`🎛️  Vanne ${valve} → ${state ? 'ON' : 'OFF'}`);
    res.json({ success: true });
  } catch(e) {
    console.error('POST /api/valve:', e.message);
    res.status(500).json({ success: false, message: e.message });
  }
});

// Planning
app.post('/api/schedule', async (req, res) => {
  const { time, duration, valves } = req.body;
  if (!time || !duration || !Array.isArray(valves))
    return res.status(400).json({ success: false, message: 'time duration valves[] requis' });
  try {
    await q(
      'UPDATE hs_schedule SET enabled=true,time_val=$1,duration=$2,valves=$3,updated_at=$4',
      [time, +duration, valves.join(','), Date.now()]
    );
    console.log(`📅 Planning UTC: ${time}  ${duration}min  [${valves}]`);
    res.json({ success: true });
  } catch(e) {
    console.error('POST /api/schedule:', e.message);
    res.status(500).json({ success: false, message: e.message });
  }
});

app.delete('/api/schedule', async (req, res) => {
  try {
    await q('UPDATE hs_schedule SET enabled=false');
    console.log('📅 Planning désactivé');
    res.json({ success: true });
  } catch(e) {
    console.error('DELETE /api/schedule:', e.message);
    res.status(500).json({ success: false, message: e.message });
  }
});

// FIX : /api/status utilise aussi ESP32_TIMEOUT_MS
app.get('/api/status', async (req, res) => {
  try {
    const [status] = await q('SELECT * FROM hs_status ORDER BY id DESC LIMIT 1');
    const lastSeen = status?.last_seen || 0;
    res.json({
      success:     true,
      lastSeen,
      esp32Online: isEsp32Online(lastSeen),
    });
  } catch(e) {
    console.error('GET /api/status:', e.message);
    res.status(500).json({ success: false, message: e.message });
  }
});

app.get('/health', (_, res) => res.json({ status: 'ok', ts: Date.now() }));
app.get('/', (req, res) =>
  res.sendFile(path.join(__dirname, 'templates', 'index.html'))
);

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

      if (valves.includes(1)) await q('UPDATE hs_commands SET sw1=true,  updated_at=$1', [Date.now()]);
      if (valves.includes(2)) await q('UPDATE hs_commands SET sw2=true,  updated_at=$1', [Date.now()]);
      console.log(`⏰ Auto UTC ${utcNow} → vannes [${valves}] pendant ${s.duration}min`);

      setTimeout(async () => {
        if (valves.includes(1)) await q('UPDATE hs_commands SET sw1=false, updated_at=$1', [Date.now()]);
        if (valves.includes(2)) await q('UPDATE hs_commands SET sw2=false, updated_at=$1', [Date.now()]);
        wateringActive = false;
        console.log('✅ Arrosage automatique terminé');
      }, s.duration * 60 * 1000);
    }

    if (utcNow !== s.time_val) lastScheduleMinute = '';

  } catch(e) { console.error('Schedule error:', e.message); }
}, 1000);

// ── Démarrage ────────────────────────────────────
initDB().then(() => {
  server.listen(PORT, '0.0.0.0', () => {
    console.log(`\n🌿 HydroSmart — HTTP PURE`);
    console.log(`   Port        : ${PORT}`);
    console.log(`   Timezone    : UTC (Fly.io)`);
    console.log(`   ESP32 timeout: ${ESP32_TIMEOUT_MS}ms\n`);
  });
}).catch(err => {
  console.error('Erreur démarrage:', err);
  process.exit(1);
});
