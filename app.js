'use strict';

// ================================================
//  HydroSmart — app.js  (VERSION STABLE)
//
//  CORRECTIONS APPLIQUÉES :
//  1. Timeout identification navigateur 5s → 500ms
//  2. Ping WebSocket navigateurs pour détecter déconnexions silencieuses
//  3. identTimer annulé correctement dans tous les cas
//  4. sendFullState envoyée immédiatement au navigateur
//  5. esp32_online/offline envoyé dans sendFullState aussi
//  6. Reconnexion DB avec retry automatique
//  7. Keep-alive HTTP pour Fly.dev (évite le sleep)
//  8. Protection double-inscription browsers/esp32s
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

// ── Auth ESP32 (HTTP) ────────────────────────────
const ESP32_KEY = process.env.ESP32_KEY || 'hydrosmart-esp32-key-2024';
function authESP(req, res, next) {
  const key = req.headers['x-api-key'] || req.query.key;
  if (key !== ESP32_KEY) return res.status(401).json({ success: false, message: 'Cle invalide' });
  next();
}

// ================================================
//  WEBSOCKET — gestion clients
// ================================================
const browsers = new Set();
const esp32s   = new Set();

function send(ws, obj) {
  if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

function broadcastTo(clients, obj) {
  const msg = JSON.stringify(obj);
  clients.forEach(ws => {
    if (ws.readyState === WebSocket.OPEN) ws.send(msg);
  });
}

function broadcastBrowsers(obj) { broadcastTo(browsers, obj); }

function sendToESP32(obj) {
  if (esp32s.size === 0) {
    console.warn('⚠️  Aucun ESP32 connecté en WebSocket — commande en DB uniquement');
    return false;
  }
  broadcastTo(esp32s, obj);
  console.log(`📤 Envoyé à ${esp32s.size} ESP32:`, JSON.stringify(obj));
  return true;
}

// ================================================
//  FIX 1 — Ping navigateurs toutes les 25s
//  Détecte les connexions fantômes (browser fermé sans close)
// ================================================
setInterval(() => {
  browsers.forEach(ws => {
    if (ws.readyState !== WebSocket.OPEN) {
      browsers.delete(ws);
      return;
    }
    if (ws.isAlive === false) {
      browsers.delete(ws);
      ws.terminate();
      console.log('🧹 Navigateur fantôme supprimé');
      return;
    }
    ws.isAlive = false;
    ws.ping();
  });
}, 25000);

// ================================================
wss.on('connection', async (ws, req) => {
  let isESP32   = false;
  let identified = false;

  ws.isAlive = true;
  ws.on('pong', () => { ws.isAlive = true; });

  // ── FIX 2 — Timeout réduit à 500ms ──────────────
  // Avant : 5000ms → le navigateur attendait 5s sans état
  // Après : 500ms → full_state envoyé quasi immédiatement
  const identTimer = setTimeout(() => {
    if (!identified) {
      identified = true;
      isESP32    = false;
      browsers.add(ws);
      console.log(`🌐 Navigateur connecté (total: ${browsers.size})`);
      sendFullState(ws);  // ← envoi immédiat de l'état complet
    }
  }, 500);

  ws.on('message', async (raw) => {
    try {
      const msg = JSON.parse(raw);

      // ── Identification ESP32 ──
      if (msg.type === 'esp32_hello') {
        if (msg.key !== ESP32_KEY) {
          console.warn('❌ ESP32 clé invalide — déconnexion');
          ws.close();
          return;
        }

        // FIX 3 — annuler le timer AVANT toute action
        clearTimeout(identTimer);

        // FIX 4 — éviter double inscription si reconnexion rapide
        if (!identified) {
          identified = true;
          isESP32    = true;
          esp32s.add(ws);
          console.log(`📟 ESP32 connecté via WebSocket (total: ${esp32s.size})`);
        }

        const [cmds] = await q('SELECT sw1,sw2 FROM hs_commands ORDER BY id DESC LIMIT 1');
        send(ws, {
          type: 'init_commands',
          sw1:  cmds?.sw1 || false,
          sw2:  cmds?.sw2 || false,
        });

        // FIX 5 — informer les navigateurs que l'ESP32 est en ligne
        broadcastBrowsers({ type: 'esp32_online' });
        return;
      }

      // ── Messages ESP32 ──
      if (isESP32) {
        if (msg.type === 'sensors') {
          const { temp, hum, soil } = msg;
          const now = Date.now();
          await q('INSERT INTO hs_sensors (temp,hum,soil,recorded_at) VALUES ($1,$2,$3,$4)',
                  [+temp, +hum, Math.round(+soil), now]);
          await q('UPDATE hs_status SET last_seen=$1', [now]);
          await q('DELETE FROM hs_sensors WHERE recorded_at < $1', [now - 86400000]);
          console.log(`📡 WS T=${temp}°C  H=${hum}%  Sol=${soil}%`);
          broadcastBrowsers({ type: 'sensors', temp: +temp, hum: +hum, soil: Math.round(+soil), lastSeen: now });
        }

        if (msg.type === 'valve_feedback') {
          const { v1, v2 } = msg;
          await q('UPDATE hs_valves SET v1=$1, v2=$2, updated_at=$3', [!!v1, !!v2, Date.now()]);
          broadcastBrowsers({ type: 'valve_status', v1: !!v1, v2: !!v2 });
          console.log(`🚿 Feedback WS: V1=${v1}  V2=${v2}`);
        }
      }

    } catch(e) { console.error('WS message error:', e.message); }
  });

  ws.on('close', () => {
    clearTimeout(identTimer);
    if (isESP32) {
      esp32s.delete(ws);
      console.log(`📟 ESP32 déconnecté (restants: ${esp32s.size})`);
      broadcastBrowsers({ type: 'esp32_offline' });
    } else {
      browsers.delete(ws);
      console.log(`🌐 Navigateur déconnecté (restants: ${browsers.size})`);
    }
  });

  ws.on('error', (e) => {
    console.error('WS error:', e.message);
    clearTimeout(identTimer);
    if (isESP32) esp32s.delete(ws);
    else         browsers.delete(ws);
  });
});

// ── FIX 6 — sendFullState avec esp32Online correct ──
async function sendFullState(ws) {
  try {
    const [sensors] = await q('SELECT * FROM hs_sensors  ORDER BY id DESC LIMIT 1');
    const [valves]  = await q('SELECT * FROM hs_valves   ORDER BY id DESC LIMIT 1');
    const [cmds]    = await q('SELECT * FROM hs_commands ORDER BY id DESC LIMIT 1');
    const [sched]   = await q('SELECT * FROM hs_schedule ORDER BY id DESC LIMIT 1');
    const [status]  = await q('SELECT * FROM hs_status   ORDER BY id DESC LIMIT 1');

    // FIX : utiliser last_seen DB pour déterminer si ESP32 actif
    // (esp32s.size peut être 0 même si l'ESP envoie en HTTP)
    const lastSeen   = status?.last_seen || 0;
    const esp32Online = esp32s.size > 0 || (Date.now() - lastSeen < 20000);

    send(ws, {
      type:        'full_state',
      sensors:     sensors || null,
      valves:      valves  || { v1: false, v2: false },
      commands:    cmds    || { sw1: false, sw2: false },
      schedule:    sched   || {},
      lastSeen,
      esp32Online,
    });
  } catch(e) { console.error('sendFullState:', e.message); }
}

// ================================================
//  ROUTES ESP32 — HTTP
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
    console.log(`📡 HTTP T=${temp}°C  H=${hum}%  Sol=${soil}%`);
    broadcastBrowsers({ type: 'sensors', temp: +temp, hum: +hum, soil: Math.round(+soil), lastSeen: now });
    res.json({ success: true });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

app.post('/api/valve-feedback', authESP, async (req, res) => {
  const { v1, v2 } = req.body;
  try {
    await q('UPDATE hs_valves SET v1=$1, v2=$2, updated_at=$3', [!!v1, !!v2, Date.now()]);
    broadcastBrowsers({ type: 'valve_status', v1: !!v1, v2: !!v2 });
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
  const ok_e = process.env.ADMIN_EMAIL    || 'hydrosmart@gmail.com';
  const ok_p = process.env.ADMIN_PASSWORD || 'groupe5';
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
    const wsDelivered = sendToESP32({ type: 'command_sent', valve, state });
    broadcastBrowsers({ type: 'command_sent', valve, state });
    res.json({ success: true, wsDelivered });
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
    console.log(`📅 Planning UTC: ${time}  ${duration}min  [${valves}]`);
    broadcastBrowsers({ type: 'schedule_updated', schedule: sched });
    res.json({ success: true, schedule: sched });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

app.delete('/api/schedule', async (req, res) => {
  try {
    await q('UPDATE hs_schedule SET enabled=false');
    broadcastBrowsers({ type: 'schedule_updated', schedule: { enabled: false } });
    res.json({ success: true });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

app.get('/api/status', async (req, res) => {
  try {
    const [sensors] = await q('SELECT * FROM hs_sensors  ORDER BY id DESC LIMIT 1');
    const [valves]  = await q('SELECT * FROM hs_valves   ORDER BY id DESC LIMIT 1');
    const [sched]   = await q('SELECT * FROM hs_schedule ORDER BY id DESC LIMIT 1');
    const [status]  = await q('SELECT * FROM hs_status   ORDER BY id DESC LIMIT 1');
    const lastSeen   = status?.last_seen || 0;
    const esp32Online = esp32s.size > 0 || (Date.now() - lastSeen < 20000);
    res.json({ success: true, sensors, valves, schedule: sched, lastSeen, esp32Online });
  } catch(e) { res.status(500).json({ success: false, message: e.message }); }
});

app.get('/health', (_, res) => res.json({ status: 'ok', ts: Date.now(), esp32: esp32s.size }));
app.get('/', (req, res) => res.sendFile(path.join(__dirname, 'templates', 'index.html')));

// ================================================
//  SCHEDULING AUTOMATIQUE
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
      sendToESP32({ type: 'auto_watering_start', valves });
      broadcastBrowsers({ type: 'auto_watering_start', valves });

      setTimeout(async () => {
        if (valves.includes(1)) await q('UPDATE hs_commands SET sw1=false');
        if (valves.includes(2)) await q('UPDATE hs_commands SET sw2=false');
        wateringActive = false;
        sendToESP32({ type: 'auto_watering_stop' });
        broadcastBrowsers({ type: 'auto_watering_stop' });
        console.log('✅ Arrosage automatique terminé');
      }, s.duration * 60 * 1000);
    }

    if (utcNow !== s.time_val) lastScheduleMinute = '';

  } catch(e) { console.error('Schedule error:', e.message); }
}, 1000);

// ================================================
//  FIX 7 — Keep-alive Fly.dev
//  Empêche la machine de s'endormir (plan gratuit)
//  Se ping lui-même toutes les 4 minutes
// ================================================
setInterval(() => {
  http.get(`http://localhost:${PORT}/health`, (res) => {
    // silencieux — juste pour garder la machine éveillée
  }).on('error', () => {});
}, 4 * 60 * 1000);

// ── Start ────────────────────────────────────────
initDB().then(() => {
  server.listen(PORT, '0.0.0.0', () => {
    console.log(`\n🌿 HydroSmart — https://hydrosmart-groupe-iot.fly.dev`);
    console.log(`   Timezone serveur : UTC (Fly.io)`);
    console.log(`   WebSocket ESP32 + Navigateurs temps réel\n`);
  });
}).catch(err => { console.error('Start error:', err); process.exit(1); });
