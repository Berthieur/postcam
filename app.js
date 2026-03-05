'use strict';

/**
 * =====================================================
 *  HydroSmart — Serveur Node.js + NeonDB (PostgreSQL)
 *  Déployable sur Render / Railway / Fly.io
 *  ESP32 + Web communiquent tous les deux via internet
 * =====================================================
 */

const express   = require('express');
const http      = require('http');
const WebSocket = require('ws');
const path      = require('path');
const { Pool }  = require('pg');

const app    = express();
const server = http.createServer(app);
const wss    = new WebSocket.Server({ server });
const PORT   = process.env.PORT || 3000;

// ─── NeonDB PostgreSQL ─────────────────────────────────
const pool = new Pool({
  connectionString: process.env.DATABASE_URL ||
    'postgresql://neondb_owner:npg_jiCSoE8M7kxy@ep-quiet-field-aigwxbil-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require',
  ssl: { rejectUnauthorized: false },
  max: 5,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,
});

pool.on('error', (err) => console.error('❌ Pool NeonDB error:', err.message));

// ─── Init tables ──────────────────────────────────────
async function initDB() {
  const client = await pool.connect();
  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS sensors (
        id        SERIAL PRIMARY KEY,
        temp      REAL,
        hum       REAL,
        soil      INTEGER,
        recorded_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000
      );

      CREATE TABLE IF NOT EXISTS valve_states (
        id         SERIAL PRIMARY KEY,
        v1         BOOLEAN NOT NULL DEFAULT FALSE,
        v2         BOOLEAN NOT NULL DEFAULT FALSE,
        updated_at BIGINT  NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000
      );

      CREATE TABLE IF NOT EXISTS commands (
        id         SERIAL PRIMARY KEY,
        sw1        BOOLEAN NOT NULL DEFAULT FALSE,
        sw2        BOOLEAN NOT NULL DEFAULT FALSE,
        updated_at BIGINT  NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000
      );

      CREATE TABLE IF NOT EXISTS schedule (
        id       SERIAL PRIMARY KEY,
        enabled  BOOLEAN NOT NULL DEFAULT FALSE,
        time_val TEXT    NOT NULL DEFAULT '18:00',
        duration INTEGER NOT NULL DEFAULT 10,
        valves   TEXT    NOT NULL DEFAULT '1',
        updated_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000
      );

      CREATE TABLE IF NOT EXISTS esp32_status (
        id        SERIAL PRIMARY KEY,
        last_seen BIGINT  NOT NULL DEFAULT 0,
        updated_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW()) * 1000
      );
    `);

    // Seed lignes uniques si vides
    await client.query(`
      INSERT INTO valve_states  (v1, v2)            SELECT false, false WHERE NOT EXISTS (SELECT 1 FROM valve_states);
      INSERT INTO commands      (sw1, sw2)           SELECT false, false WHERE NOT EXISTS (SELECT 1 FROM commands);
      INSERT INTO schedule      (enabled, time_val, duration, valves) SELECT false, '18:00', 10, '1' WHERE NOT EXISTS (SELECT 1 FROM schedule);
      INSERT INTO esp32_status  (last_seen)          SELECT 0           WHERE NOT EXISTS (SELECT 1 FROM esp32_status);
    `);

    console.log('✅ NeonDB tables initialisées');
  } finally {
    client.release();
  }
}

// ─── Helpers DB ───────────────────────────────────────
async function dbQuery(sql, params = []) {
  const client = await pool.connect();
  try {
    const result = await client.query(sql, params);
    return result.rows;
  } finally {
    client.release();
  }
}

// ─── Middlewares ──────────────────────────────────────
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// CORS pour ESP32 et clients distants
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

// ─── Clé API simple pour l'ESP32 ─────────────────────
const ESP32_KEY = process.env.ESP32_KEY || 'hydrosmart-esp32-key-2024';

function checkEsp32Key(req, res, next) {
  const key = req.headers['x-api-key'] || req.query.key;
  if (key !== ESP32_KEY) {
    return res.status(401).json({ success: false, message: 'Clé API invalide' });
  }
  next();
}

// ─── WebSocket : connexion navigateur ─────────────────
function broadcast(payload) {
  const msg = JSON.stringify(payload);
  wss.clients.forEach(ws => {
    if (ws.readyState === WebSocket.OPEN) ws.send(msg);
  });
}

wss.on('connection', async (ws) => {
  console.log('🌐 Navigateur connecté');

  try {
    // Envoyer l'état complet à la connexion
    const [sensors]  = await dbQuery('SELECT * FROM sensors   ORDER BY id DESC LIMIT 1');
    const [valves]   = await dbQuery('SELECT * FROM valve_states ORDER BY id DESC LIMIT 1');
    const [cmds]     = await dbQuery('SELECT * FROM commands   ORDER BY id DESC LIMIT 1');
    const [sched]    = await dbQuery('SELECT * FROM schedule   ORDER BY id DESC LIMIT 1');
    const [status]   = await dbQuery('SELECT * FROM esp32_status ORDER BY id DESC LIMIT 1');

    ws.send(JSON.stringify({
      type: 'full_state',
      sensors:  sensors || null,
      valves:   valves  || { v1: false, v2: false },
      commands: cmds    || { sw1: false, sw2: false },
      schedule: sched   || {},
      lastSeen: status?.last_seen || 0,
    }));
  } catch (e) {
    console.error('❌ WS full_state:', e.message);
  }

  ws.on('close', () => console.log('🌐 Navigateur déconnecté'));
});

// =====================================================
//  ROUTES ESP32 → SERVEUR
// =====================================================

/**
 * POST /api/sensors
 * ESP32 envoie { temp, hum, soil } toutes les 2s
 * Header: x-api-key: <ESP32_KEY>
 */
app.post('/api/sensors', checkEsp32Key, async (req, res) => {
  const { temp, hum, soil } = req.body;

  if (temp === undefined || hum === undefined || soil === undefined)
    return res.status(400).json({ success: false, message: 'Champs requis: temp, hum, soil' });

  try {
    const now = Date.now();

    // Sauvegarder dans NeonDB
    await dbQuery(
      'INSERT INTO sensors (temp, hum, soil, recorded_at) VALUES ($1, $2, $3, $4)',
      [Math.round(temp * 10) / 10, Math.round(hum * 10) / 10, Math.round(soil), now]
    );

    // Nettoyer les anciennes mesures (garder 24h)
    await dbQuery('DELETE FROM sensors WHERE recorded_at < $1', [now - 86400000]);

    // Mettre à jour lastSeen
    await dbQuery('UPDATE esp32_status SET last_seen = $1, updated_at = $2', [now, now]);

    console.log(`📡 Capteurs: T=${temp}°C  H=${hum}%  Sol=${soil}%`);

    // Diffuser aux navigateurs
    broadcast({ type: 'sensors', temp, hum, soil, lastSeen: now });

    res.json({ success: true });
  } catch (e) {
    console.error('❌ /api/sensors:', e.message);
    res.status(500).json({ success: false, message: e.message });
  }
});

/**
 * POST /api/valve-feedback
 * ESP32 confirme l'état réel des vannes
 * Body: { v1: bool, v2: bool }
 */
app.post('/api/valve-feedback', checkEsp32Key, async (req, res) => {
  const { v1, v2 } = req.body;

  try {
    const now = Date.now();
    await dbQuery(
      'UPDATE valve_states SET v1 = $1, v2 = $2, updated_at = $3',
      [!!v1, !!v2, now]
    );

    console.log(`🚿 Feedback vannes: V1=${v1}  V2=${v2}`);
    broadcast({ type: 'valve_status', v1: !!v1, v2: !!v2 });

    res.json({ success: true });
  } catch (e) {
    console.error('❌ /api/valve-feedback:', e.message);
    res.status(500).json({ success: false, message: e.message });
  }
});

/**
 * GET /api/commands
 * ESP32 poll toutes les 500ms pour lire les commandes
 * Répond avec { sw1: bool, sw2: bool }
 */
app.get('/api/commands', checkEsp32Key, async (req, res) => {
  try {
    const [cmds] = await dbQuery('SELECT sw1, sw2 FROM commands ORDER BY id DESC LIMIT 1');
    res.json({ sw1: cmds?.sw1 || false, sw2: cmds?.sw2 || false });
  } catch (e) {
    console.error('❌ /api/commands:', e.message);
    res.status(500).json({ success: false, message: e.message });
  }
});

// =====================================================
//  ROUTES NAVIGATEUR → SERVEUR
// =====================================================

/**
 * POST /api/login
 * Authentification simple (email + mot de passe)
 */
app.post('/api/login', async (req, res) => {
  const { email, password } = req.body;

  // Identifiants en variables d'env ou valeurs par défaut
  const validEmail = process.env.ADMIN_EMAIL    || 'admin@hydrosmart.io';
  const validPass  = process.env.ADMIN_PASSWORD || 'hydro2024';

  if (email === validEmail && password === validPass) {
    return res.json({ success: true, token: 'hs-session-ok' });
  }
  res.status(401).json({ success: false, message: 'Email ou mot de passe invalide' });
});

/**
 * POST /api/valve
 * Navigateur commande une vanne
 * Body: { valve: 1|2, state: true|false }
 */
app.post('/api/valve', async (req, res) => {
  const { valve, state } = req.body;

  if (valve !== 1 && valve !== 2)
    return res.status(400).json({ success: false, message: 'valve doit être 1 ou 2' });
  if (typeof state !== 'boolean')
    return res.status(400).json({ success: false, message: 'state doit être true ou false' });

  try {
    const now  = Date.now();
    const col  = `sw${valve}`;
    await dbQuery(`UPDATE commands SET ${col} = $1, updated_at = $2`, [state, now]);

    console.log(`🎛️  Commande vanne ${valve} → ${state ? 'ON' : 'OFF'}`);
    broadcast({ type: 'command_sent', valve, state });

    res.json({ success: true, valve, state });
  } catch (e) {
    console.error('❌ /api/valve:', e.message);
    res.status(500).json({ success: false, message: e.message });
  }
});

/**
 * POST /api/schedule
 * Navigateur configure le planning
 * Body: { time: "18:00", duration: 10, valves: [1,2] }
 */
app.post('/api/schedule', async (req, res) => {
  const { time, duration, valves } = req.body;

  if (!time || !duration || !Array.isArray(valves))
    return res.status(400).json({ success: false, message: 'Champs requis: time, duration, valves[]' });

  try {
    const now       = Date.now();
    const valvesStr = valves.join(',');
    await dbQuery(
      'UPDATE schedule SET enabled = true, time_val = $1, duration = $2, valves = $3, updated_at = $4',
      [time, parseInt(duration), valvesStr, now]
    );

    const schedObj = { enabled: true, time, duration, valves };
    console.log(`📅 Planning: ${time}, ${duration}min, vannes [${valvesStr}]`);
    broadcast({ type: 'schedule_updated', schedule: schedObj });

    res.json({ success: true, schedule: schedObj });
  } catch (e) {
    console.error('❌ /api/schedule:', e.message);
    res.status(500).json({ success: false, message: e.message });
  }
});

/**
 * DELETE /api/schedule — désactiver le planning
 */
app.delete('/api/schedule', async (req, res) => {
  try {
    await dbQuery('UPDATE schedule SET enabled = false');
    broadcast({ type: 'schedule_updated', schedule: { enabled: false } });
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

/**
 * GET /api/status — état complet (debug + reconnexion WS)
 */
app.get('/api/status', async (req, res) => {
  try {
    const [sensors]  = await dbQuery('SELECT * FROM sensors       ORDER BY id DESC LIMIT 1');
    const [valves]   = await dbQuery('SELECT * FROM valve_states  ORDER BY id DESC LIMIT 1');
    const [cmds]     = await dbQuery('SELECT * FROM commands      ORDER BY id DESC LIMIT 1');
    const [sched]    = await dbQuery('SELECT * FROM schedule      ORDER BY id DESC LIMIT 1');
    const [status]   = await dbQuery('SELECT * FROM esp32_status  ORDER BY id DESC LIMIT 1');

    res.json({ success: true, sensors, valves, commands: cmds, schedule: sched, lastSeen: status?.last_seen });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

/**
 * GET /api/history?limit=50 — historique capteurs
 */
app.get('/api/history', async (req, res) => {
  const limit = parseInt(req.query.limit) || 50;
  try {
    const rows = await dbQuery(
      'SELECT * FROM sensors ORDER BY recorded_at DESC LIMIT $1', [limit]
    );
    res.json({ success: true, history: rows });
  } catch (e) {
    res.status(500).json({ success: false, message: e.message });
  }
});

// =====================================================
//  SCHEDULING AUTOMATIQUE CÔTÉ SERVEUR
// =====================================================
let wateringActive = false;

setInterval(async () => {
  try {
    const [sched] = await dbQuery('SELECT * FROM schedule ORDER BY id DESC LIMIT 1');
    if (!sched?.enabled || !sched.time_val) return;

    const now    = new Date();
    const nowStr = now.toTimeString().slice(0, 5);

    if (nowStr === sched.time_val && !wateringActive) {
      wateringActive = true;
      const valves = sched.valves.split(',').map(Number);

      console.log(`⏰ Arrosage automatique à ${nowStr} — vannes [${valves}]`);

      // Activer les vannes
      if (valves.includes(1)) await dbQuery('UPDATE commands SET sw1 = true');
      if (valves.includes(2)) await dbQuery('UPDATE commands SET sw2 = true');
      broadcast({ type: 'auto_watering_start', valves });

      // Éteindre après durée
      setTimeout(async () => {
        if (valves.includes(1)) await dbQuery('UPDATE commands SET sw1 = false');
        if (valves.includes(2)) await dbQuery('UPDATE commands SET sw2 = false');
        wateringActive = false;
        console.log(`✅ Arrosage automatique terminé (${sched.duration}min)`);
        broadcast({ type: 'auto_watering_stop' });
      }, sched.duration * 60 * 1000);
    }

    if (nowStr !== sched.time_val) wateringActive = false;
  } catch (e) {
    console.error('❌ Schedule loop:', e.message);
  }
}, 15_000);

// ─── Health check (pour Render/Railway) ───────────────
app.get('/health', (req, res) => res.json({ status: 'ok', ts: Date.now() }));

// ─── Démarrage ────────────────────────────────────────
initDB().then(() => {
  server.listen(PORT, '0.0.0.0', () => {
    console.log(`\n🌿 HydroSmart Server — Port ${PORT}`);
    console.log(`   Web       : https://VOTRE-APP.onrender.com/`);
    console.log(`   ESP32 key : ${ESP32_KEY}\n`);
  });
}).catch(err => {
  console.error('❌ Impossible de démarrer:', err);
  process.exit(1);
});
