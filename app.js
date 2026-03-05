'use strict';

/**
 * =====================================================
 *  HydroSmart — Serveur Node.js (SANS Firebase)
 *  - Reçoit les données capteurs de l'ESP32 via HTTP POST
 *  - Envoie les commandes valves à l'ESP32 via polling HTTP GET
 *  - Diffuse tout en temps réel au navigateur via WebSocket
 *  - Sert l'interface web statique (index.html)
 * =====================================================
 */

const express   = require('express');
const http      = require('http');
const WebSocket = require('ws');
const path      = require('path');

const app    = express();
const server = http.createServer(app);
const wss    = new WebSocket.Server({ server });
const PORT   = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// ─── État en mémoire (remplace Firebase) ──────────────
const state = {
  live:     { temp: null, hum: null, soil: null },
  status:   { lastSeen: null, v1: false, v2: false },
  manual:   { sw1: false, sw2: false },
  schedule: { enabled: false, time: '18:00', duration: 10, valves: [1] },
};

// ─── Broadcast WebSocket à tous les navigateurs ────────
function broadcast(payload) {
  const msg = JSON.stringify(payload);
  wss.clients.forEach(ws => {
    if (ws.readyState === WebSocket.OPEN) ws.send(msg);
  });
}

// ─── WebSocket : nouvelle connexion navigateur ─────────
wss.on('connection', (ws) => {
  console.log('🌐 Navigateur connecté');
  ws.send(JSON.stringify({ type: 'full_state', data: state }));
  ws.on('close', () => console.log('🌐 Navigateur déconnecté'));
});

// =====================================================
//  ROUTES ESP32 → SERVEUR
// =====================================================

// POST /api/sensors  — ESP32 envoie { temp, hum, soil } toutes les 2s
app.post('/api/sensors', (req, res) => {
  const { temp, hum, soil } = req.body;
  if (temp === undefined || hum === undefined || soil === undefined)
    return res.status(400).json({ success: false, message: 'Champs requis: temp, hum, soil' });

  state.live.temp      = Math.round(temp * 10) / 10;
  state.live.hum       = Math.round(hum  * 10) / 10;
  state.live.soil      = Math.round(soil);
  state.status.lastSeen = Date.now();

  console.log(`📡 Capteurs: T=${state.live.temp}°C  H=${state.live.hum}%  Sol=${state.live.soil}%`);
  broadcast({ type: 'sensors', data: state.live, lastSeen: state.status.lastSeen });
  res.json({ success: true });
});

// POST /api/valve-feedback  — ESP32 confirme l'état réel des vannes
// Body: { v1: bool, v2: bool }
app.post('/api/valve-feedback', (req, res) => {
  const { v1, v2 } = req.body;
  if (v1 !== undefined) state.status.v1 = !!v1;
  if (v2 !== undefined) state.status.v2 = !!v2;

  console.log(`🚿 Feedback vannes: V1=${state.status.v1}  V2=${state.status.v2}`);
  broadcast({ type: 'valve_status', v1: state.status.v1, v2: state.status.v2 });
  res.json({ success: true });
});

// GET /api/commands  — ESP32 poll toutes les 500ms pour lire les commandes
app.get('/api/commands', (req, res) => {
  res.json({ sw1: state.manual.sw1, sw2: state.manual.sw2 });
});

// =====================================================
//  ROUTES NAVIGATEUR → SERVEUR
// =====================================================

// POST /api/valve  — navigateur commande une vanne
// Body: { valve: 1|2, state: true|false }
app.post('/api/valve', (req, res) => {
  const { valve, state: vs } = req.body;
  if (valve !== 1 && valve !== 2)
    return res.status(400).json({ success: false, message: 'valve doit être 1 ou 2' });
  if (typeof vs !== 'boolean')
    return res.status(400).json({ success: false, message: 'state doit être true ou false' });

  state.manual[`sw${valve}`] = vs;
  console.log(`🎛️  Commande vanne ${valve} → ${vs ? 'ON' : 'OFF'}`);
  broadcast({ type: 'command_sent', valve, state: vs });
  res.json({ success: true, valve, state: vs });
});

// POST /api/schedule  — navigateur configure le planning
// Body: { time: "18:00", duration: 10, valves: [1,2] }
app.post('/api/schedule', (req, res) => {
  const { time, duration, valves } = req.body;
  if (!time || !duration || !Array.isArray(valves))
    return res.status(400).json({ success: false, message: 'Champs requis: time, duration, valves[]' });

  state.schedule = { enabled: true, time, duration: parseInt(duration), valves };
  console.log(`📅 Planning: ${time}, ${duration}min, vannes [${valves.join(',')}]`);
  broadcast({ type: 'schedule_updated', schedule: state.schedule });
  res.json({ success: true, schedule: state.schedule });
});

// DELETE /api/schedule  — désactiver le planning
app.delete('/api/schedule', (req, res) => {
  state.schedule.enabled = false;
  broadcast({ type: 'schedule_updated', schedule: state.schedule });
  res.json({ success: true });
});

// GET /api/status  — état complet (debug)
app.get('/api/status', (req, res) => res.json({ success: true, data: state }));

// =====================================================
//  SCHEDULING AUTOMATIQUE CÔTÉ SERVEUR
// =====================================================
let wateringActive = false;

setInterval(() => {
  const s = state.schedule;
  if (!s.enabled || !s.time) return;

  const now    = new Date();
  const nowStr = now.toTimeString().slice(0, 5);

  if (nowStr === s.time && !wateringActive) {
    wateringActive = true;
    console.log(`⏰ Arrosage automatique déclenché à ${nowStr}`);
    s.valves.forEach(v => { state.manual[`sw${v}`] = true; });
    broadcast({ type: 'auto_watering_start', valves: s.valves });

    setTimeout(() => {
      s.valves.forEach(v => { state.manual[`sw${v}`] = false; });
      wateringActive = false;
      console.log(`✅ Arrosage automatique terminé (${s.duration}min)`);
      broadcast({ type: 'auto_watering_stop' });
    }, s.duration * 60 * 1000);
  }

  if (nowStr !== s.time) wateringActive = false;
}, 15_000);

// ─── Démarrage ────────────────────────────────────────
server.listen(PORT, '0.0.0.0', () => {
  console.log(`\n🌿 HydroSmart Server démarré`);
  console.log(`   Interface web : http://localhost:${PORT}/`);
  console.log(`   API ESP32     : POST http://<VOTRE_IP>:${PORT}/api/sensors`);
  console.log(`   API ESP32     : GET  http://<VOTRE_IP>:${PORT}/api/commands\n`);
});
