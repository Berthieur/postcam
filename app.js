'use strict';

const express = require('express');
const cors = require('cors');
const { v4: uuidv4 } = require('uuid');
const session = require('express-session');
const path = require('path');

// === Configuration ===
const app = express();
const PORT = process.env.PORT || 8000;

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cors({ origin: '*' }));
app.use(session({
  secret: process.env.SECRET_KEY || '3fb5222037e2be9d7d09019e1b46e268ec470fa2974a3981',
  resave: false,
  saveUninitialized: false,
}));
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'templates'));

// === DB ===
const { initDb, getDb, DB_DRIVER } = require('./database');
const PLACEHOLDER = DB_DRIVER === 'sqlite' ? '?' : '$';

// Helper pour générer les placeholders PostgreSQL ($1, $2, ...)
function ph(index) {
  return DB_DRIVER === 'sqlite' ? '?' : `$${index}`;
}

function placeholders(n, start = 1) {
  return Array.from({ length: n }, (_, i) =>
    DB_DRIVER === 'sqlite' ? '?' : `$${start + i}`
  ).join(', ');
}

// === Logger simple ===
const logger = {
  info: (...args) => console.log('[INFO]', ...args),
  warn: (...args) => console.warn('[WARN]', ...args),
  error: (...args) => console.error('[ERROR]', ...args),
};

// === Init DB ===
(async () => {
  try {
    await initDb();
    logger.info('✅ Base initialisée');
  } catch (e) {
    logger.error('❌ Échec init DB:', e);
    process.exit(1);
  }
})();

// === Helpers ===
function timestampToDate(ts) {
  try {
    return new Date(parseInt(ts)).toLocaleDateString('fr-FR');
  } catch { return '-'; }
}

function timestampToDateFull(ts) {
  try {
    const d = new Date(parseInt(ts));
    return d.toLocaleDateString('fr-FR') + ' à ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  } catch { return '-'; }
}

async function dbAll(sql, params = []) {
  const db = await getDb();
  return new Promise((resolve, reject) => {
    if (DB_DRIVER === 'sqlite') {
      db.all(sql, params, (err, rows) => {
        db.close();
        if (err) reject(err); else resolve(rows);
      });
    } else {
      db.query(sql, params).then(r => { db.release(); resolve(r.rows); }).catch(e => { db.release(); reject(e); });
    }
  });
}

async function dbRun(sql, params = []) {
  const db = await getDb();
  return new Promise((resolve, reject) => {
    if (DB_DRIVER === 'sqlite') {
      db.run(sql, params, function (err) {
        db.close();
        if (err) reject(err); else resolve({ changes: this.changes, lastID: this.lastID });
      });
    } else {
      db.query(sql, params).then(r => { db.release(); resolve(r); }).catch(e => { db.release(); reject(e); });
    }
  });
}

async function dbGet(sql, params = []) {
  const rows = await dbAll(sql, params);
  return rows[0] || null;
}

// === RSSI → Distance ===
function rssiToDistance(rssi, txPower = -59, n = 2.5) {
  if (rssi === 0) return -1.0;
  rssi = Math.max(-100, Math.min(-30, rssi));
  const ratio = (txPower - rssi) / (10 * n);
  return Math.round(Math.min(Math.pow(10, ratio), 15.0) * 100) / 100;
}

// === Trilatération basique ===
function trilateration(anchors) {
  if (anchors.length < 3) return [anchors[0].x, anchors[0].y];

  const sorted = [...anchors].sort((a, b) => a.distance - b.distance).slice(0, 3);
  const [a1, a2, a3] = sorted;
  const [x1, y1, r1] = [a1.x, a1.y, a1.distance];
  const [x2, y2, r2] = [a2.x, a2.y, a2.distance];
  const [x3, y3, r3] = [a3.x, a3.y, a3.distance];

  const A = 2 * (x2 - x1), B = 2 * (y2 - y1);
  const C = r1 ** 2 - r2 ** 2 - x1 ** 2 + x2 ** 2 - y1 ** 2 + y2 ** 2;
  const D = 2 * (x3 - x2), E = 2 * (y3 - y2);
  const F = r2 ** 2 - r3 ** 2 - x2 ** 2 + x3 ** 2 - y2 ** 2 + y3 ** 2;

  const denom = A * E - B * D;
  if (Math.abs(denom) < 1e-6) return [x1, y1];

  let x = (C * E - B * F) / denom;
  let y = (A * F - C * D) / denom;

  x = Math.max(0, Math.min(6.0, x));
  y = Math.max(0, Math.min(5.0, y));

  return [Math.round(x * 100) / 100, Math.round(y * 100) / 100];
}

// === Calculer et diffuser positions ===
async function calculateAndBroadcastPositions() {
  const threshold = Math.floor((Date.now() / 1000 - 8) * 1000);

  const measurements = await dbAll(
    `SELECT employee_id, anchor_id, anchor_x, anchor_y, rssi FROM rssi_measurements WHERE timestamp > ${ph(1)}`,
    [threshold]
  );

  if (!measurements.length) return;

  const employeeData = {};
  for (const row of measurements) {
    const empId = row.employee_id;
    const distance = rssiToDistance(row.rssi);
    if (distance > 0) {
      if (!employeeData[empId]) employeeData[empId] = [];
      employeeData[empId].push({
        anchor_id: row.anchor_id,
        x: row.anchor_x,
        y: row.anchor_y,
        distance,
        rssi: row.rssi,
      });
    }
  }

  for (const [empId, anchors] of Object.entries(employeeData)) {
    if (anchors.length < 3) continue;

    // Moyenner par ancre
    const anchorMap = {};
    for (const a of anchors) {
      if (!anchorMap[a.anchor_id]) {
        anchorMap[a.anchor_id] = { x: a.x, y: a.y, distances: [], rssis: [] };
      }
      anchorMap[a.anchor_id].distances.push(a.distance);
      anchorMap[a.anchor_id].rssis.push(a.rssi);
    }

    const averaged = Object.entries(anchorMap).map(([aid, d]) => ({
      anchor_id: aid,
      x: d.x,
      y: d.y,
      distance: d.distances.reduce((a, b) => a + b, 0) / d.distances.length,
      rssi: d.rssis.reduce((a, b) => a + b, 0) / d.rssis.length,
    }));

    if (averaged.length < 3) continue;

    const avgRssi = averaged.reduce((s, a) => s + a.rssi, 0) / averaged.length;
    let alpha, movementThreshold;

    if (avgRssi > -60) { alpha = 0.20; movementThreshold = 0.05; }
    else if (avgRssi > -70) { alpha = 0.15; movementThreshold = 0.10; }
    else { alpha = 0.10; movementThreshold = 0.20; }

    const [newX, newY] = trilateration(averaged);

    const oldPos = await dbGet(
      `SELECT last_position_x, last_position_y FROM employees WHERE id = ${ph(1)}`,
      [empId]
    );

    let posX = newX, posY = newY;

    if (oldPos?.last_position_x != null && oldPos?.last_position_y != null) {
      posX = Math.round((alpha * newX + (1 - alpha) * oldPos.last_position_x) * 100) / 100;
      posY = Math.round((alpha * newY + (1 - alpha) * oldPos.last_position_y) * 100) / 100;

      const moved = Math.sqrt((posX - oldPos.last_position_x) ** 2 + (posY - oldPos.last_position_y) ** 2);
      if (moved < movementThreshold) continue;
    }

    await dbRun(
      `UPDATE employees SET last_position_x = ${ph(1)}, last_position_y = ${ph(2)}, last_seen = ${ph(3)} WHERE id = ${ph(4)}`,
      [posX, posY, Date.now(), empId]
    );

    logger.info(`📍 Position employé ${empId}: (${posX}, ${posY})`);
  }
}

// =====================
// === ROUTES WEB ======
// =====================

app.get(['/', '/login'], (req, res) => {
  res.render('login');
});

app.get('/logout', (req, res) => {
  req.session.destroy();
  res.redirect('/login');
});

app.get('/dashboard', async (req, res) => {
  if (!req.session.logged_in) return res.redirect('/login');

  try {
    const payments = await dbAll(`
      SELECT s.id, s.employee_id, s.employee_name, s.amount, s.hours_worked,
             s.type AS payment_type, s.period, s.date,
             e.nom, e.prenom, e.type,
             e.email, e.telephone, e.taux_horaire, e.frais_ecolage,
             e.date_naissance, e.lieu_naissance
      FROM salaries s
      LEFT JOIN employees e ON e.id = s.employee_id
      ORDER BY s.date DESC
    `);
    res.render('dashboard', {
      payments,
      timestampToDate,
      timestampToDateFull,
    });
  } catch (e) {
    logger.error('❌ dashboard:', e);
    res.status(500).json({ success: false, message: e.message });
  }
});

// =====================
// === API LOGIN =======
// =====================

app.post('/api/login', (req, res) => {
  const data = req.body;
  if (!data) return res.status(400).json({ success: false, message: 'Données manquantes' });

  const { username, password } = data;
  if (username === 'admin' && password === '1234') {
    req.session.logged_in = true;
    return res.json({
      success: true,
      token: 'fake-jwt-token-123',
      role: 'admin',
      redirect_url: '/dashboard',
    });
  }
  return res.status(401).json({ success: false, message: 'Identifiants invalides' });
});

// ========================
// === API EMPLOYÉS =======
// ========================

app.get('/api/employees', async (req, res) => {
  try {
    const employees = await dbAll('SELECT * FROM employees ORDER BY nom, prenom');
    res.json({ success: true, employees });
  } catch (e) {
    logger.error('❌ get_all_employees:', e);
    res.status(500).json({ success: false, message: e.message });
  }
});

app.post('/api/employees', async (req, res) => {
  const record = req.body;
  for (const field of ['nom', 'prenom', 'type']) {
    if (!record?.[field]) return res.status(400).json({ success: false, message: `Champ manquant: ${field}` });
  }

  try {
    const id = uuidv4();
    const createdAt = Date.now();

    await dbRun(`
      INSERT INTO employees (
        id, nom, prenom, type, is_active, created_at,
        email, telephone, taux_horaire, frais_ecolage,
        profession, date_naissance, lieu_naissance
      ) VALUES (${placeholders(13)})
    `, [
      id, record.nom, record.prenom, record.type,
      record.is_active ?? 1, createdAt,
      record.email ?? null, record.telephone ?? null, record.taux_horaire ?? null,
      record.frais_ecolage ?? null, record.profession ?? null,
      record.date_naissance ?? null, record.lieu_naissance ?? null,
    ]);

    res.status(201).json({ success: true, message: 'Employé ajouté avec succès', id });
  } catch (e) {
    logger.error('❌ add_employee:', e);
    res.status(500).json({ success: false, message: e.message });
  }
});

app.put('/api/employees/:id', async (req, res) => {
  const record = req.body;
  if (!record) return res.status(400).json({ success: false, message: 'Requête vide' });

  try {
    await dbRun(`
      UPDATE employees
      SET nom = ${ph(1)}, prenom = ${ph(2)}, type = ${ph(3)}, is_active = ${ph(4)},
          email = ${ph(5)}, telephone = ${ph(6)},
          taux_horaire = ${ph(7)}, frais_ecolage = ${ph(8)},
          profession = ${ph(9)}, date_naissance = ${ph(10)}, lieu_naissance = ${ph(11)}
      WHERE id = ${ph(12)}
    `, [
      record.nom, record.prenom, record.type, record.is_active ?? 1,
      record.email ?? null, record.telephone ?? null,
      record.taux_horaire ?? null, record.frais_ecolage ?? null,
      record.profession ?? null, record.date_naissance ?? null,
      record.lieu_naissance ?? null, req.params.id,
    ]);

    res.json({ success: true, message: 'Employé modifié' });
  } catch (e) {
    logger.error('❌ update_employee:', e);
    res.status(500).json({ success: false, message: e.message });
  }
});

app.delete('/api/employees/:id', async (req, res) => {
  const id = req.params.id;
  try {
    await dbRun(`DELETE FROM pointages WHERE employee_id = ${ph(1)}`, [id]);
    await dbRun(`DELETE FROM rssi_measurements WHERE employee_id = ${ph(1)}`, [id]);
    await dbRun(`DELETE FROM salaries WHERE employee_id = ${ph(1)}`, [id]);
    const result = await dbRun(`DELETE FROM employees WHERE id = ${ph(1)}`, [id]);

    if ((result.changes ?? result.rowCount ?? 1) === 0) {
      return res.status(404).json({ success: false, message: 'Employé non trouvé' });
    }

    logger.info(`✅ Employé ${id} supprimé`);
    res.json({ success: true, message: 'Employé supprimé avec succès' });
  } catch (e) {
    logger.error('❌ delete_employee:', e);
    res.status(500).json({ success: false, message: e.message });
  }
});

app.get('/api/employees/active', async (req, res) => {
  try {
    const employees = await dbAll(`
      SELECT id, nom, prenom, type, is_active, created_at,
             email, telephone, taux_horaire, frais_ecolage,
             profession, date_naissance, lieu_naissance,
             last_position_x, last_position_y, last_seen
      FROM employees WHERE is_active = 1 ORDER BY nom, prenom
    `);
    res.json({ success: true, employees });
  } catch (e) {
    logger.error('❌ get_active_employees:', e);
    res.status(500).json({ success: false, message: e.message });
  }
});

// =====================
// === API SALAIRES ====
// =====================

app.post('/api/salary', async (req, res) => {
  const data = req.body;
  logger.info('📥 Données reçues:', data);

  if (!data) return res.status(400).json({ success: false, message: 'Requête vide' });

  let { employeeId, employee_id, employeeName, employee_name, amount, type: recordType, hoursWorked, hours_worked } = data;
  const employeeIdFinal = employeeId || employee_id;
  const employeeNameFinal = (employeeName || employee_name || '').trim();
  const hoursWorkedFinal = hoursWorked || hours_worked || 0.0;

  if (!employeeNameFinal) return res.status(400).json({ success: false, message: 'Champ manquant ou vide: employeeName' });
  if (!amount) return res.status(400).json({ success: false, message: 'Champ manquant ou vide: amount' });
  if (!recordType) return res.status(400).json({ success: false, message: 'Champ manquant ou vide: type' });

  const amountNum = parseFloat(amount);
  if (isNaN(amountNum) || amountNum <= 0) {
    return res.status(400).json({ success: false, message: 'Le montant doit être supérieur à 0' });
  }

  try {
    let empId = employeeIdFinal;

    if (empId) {
      const emp = await dbGet(`SELECT id FROM employees WHERE id = ${ph(1)}`, [empId]);
      if (!emp) logger.warn(`⚠️ Employé ${empId} non trouvé`);
    } else {
      const emp = await dbGet(`
        SELECT id FROM employees 
        WHERE (nom || ' ' || prenom) = ${ph(1)} OR (prenom || ' ' || nom) = ${ph(2)}
        LIMIT 1
      `, [employeeNameFinal, employeeNameFinal]);

      if (emp) {
        empId = emp.id;
      } else {
        logger.warn(`⚠️ Employé '${employeeNameFinal}' non trouvé, création automatique`);
        const parts = employeeNameFinal.split(' ');
        const prenom = parts[0] || 'Inconnu';
        const nom = parts.slice(1).join(' ') || employeeNameFinal;
        empId = uuidv4();

        await dbRun(`
          INSERT INTO employees (id, nom, prenom, type, is_active, created_at)
          VALUES (${placeholders(6)})
        `, [empId, nom, prenom, 'employe', 1, Date.now()]);
      }
    }

    const salaryDate = parseInt(data.date || Date.now());
    const period = data.period || new Date().toISOString().slice(0, 7);
    const salaryId = data.id || uuidv4();

    const existing = await dbGet(`SELECT id FROM salaries WHERE id = ${ph(1)}`, [salaryId]);

    let action;
    if (existing) {
      await dbRun(`
        UPDATE salaries 
        SET employee_id = ${ph(1)}, employee_name = ${ph(2)}, amount = ${ph(3)},
            hours_worked = ${ph(4)}, type = ${ph(5)}, period = ${ph(6)}, date = ${ph(7)}
        WHERE id = ${ph(8)}
      `, [empId, employeeNameFinal, amountNum, hoursWorkedFinal, recordType, period, salaryDate, salaryId]);
      action = 'mis à jour';
    } else {
      await dbRun(`
        INSERT INTO salaries (id, employee_id, employee_name, amount, hours_worked, type, period, date)
        VALUES (${placeholders(8)})
      `, [salaryId, empId, employeeNameFinal, amountNum, hoursWorkedFinal, recordType, period, salaryDate]);
      action = 'créé';
    }

    logger.info(`✅ Salaire ${action}: ${salaryId}`);
    res.status(action === 'créé' ? 201 : 200).json({
      success: true,
      message: `Salaire ${action} avec succès`,
      id: salaryId,
      employeeId: empId,
      action,
    });
  } catch (e) {
    logger.error('❌ add_salary:', e);
    res.status(500).json({ success: false, message: e.message });
  }
});

app.get('/api/salary/history', async (req, res) => {
  try {
    const salaries = await dbAll(`
      SELECT s.id, s.employee_id, s.employee_name, s.amount, s.hours_worked,
             s.type, s.period, s.date,
             e.email, e.telephone, e.taux_horaire, e.frais_ecolage,
             e.date_naissance, e.lieu_naissance
      FROM salaries s
      LEFT JOIN employees e ON e.id = s.employee_id
      WHERE s.employee_id IS NOT NULL AND s.employee_name IS NOT NULL 
        AND s.employee_name != '' AND s.amount > 0
      ORDER BY s.date DESC
    `);

    for (const r of salaries) {
      if (r.hours_worked == null) r.hours_worked = 0.0;
      if (r.period == null) r.period = '';
    }

    logger.info(`📤 Historique salaires: ${salaries.length} enregistrements`);
    res.json({ success: true, salaries });
  } catch (e) {
    logger.error('❌ get_salary_history:', e);
    res.status(500).json({ success: false, message: e.message });
  }
});

// ======================
// === API POINTAGES ====
// ======================

app.post('/api/pointages', async (req, res) => {
  const data = req.body;
  logger.info('📥 Pointage reçu:', data);

  if (!data) return res.status(400).json({ success: false, message: 'Requête vide' });

  const { employeeId, type, timestamp, date } = data;
  if (!employeeId) return res.status(400).json({ success: false, message: 'Champ manquant: employeeId' });
  if (!type) return res.status(400).json({ success: false, message: 'Champ manquant: type' });
  if (!timestamp || !date) return res.status(400).json({ success: false, message: 'Champs manquants: timestamp ou date' });

  try {
    const employee = await dbGet(`SELECT id, nom, prenom, type FROM employees WHERE id = ${ph(1)}`, [employeeId]);
    if (!employee) {
      return res.status(404).json({ success: false, message: `Employé ${employeeId} non trouvé. Veuillez synchroniser les employés.` });
    }

    const employeeName = `${employee.nom} ${employee.prenom}`;
    const empType = employee.type;

    let normalized = type.toLowerCase().trim();
    if (['entree', 'entrée', 'entry', 'in'].includes(normalized)) normalized = 'arrivee';
    else if (['sortie', 'exit', 'out'].includes(normalized)) normalized = 'sortie';
    else if (!['arrivee', 'sortie'].includes(normalized)) {
      return res.status(400).json({ success: false, message: `Type de pointage invalide: '${type}'. Utilisez 'arrivee' ou 'sortie'.` });
    }

    const newIsActive = normalized === 'arrivee' ? 1 : 0;
    await dbRun(
      `UPDATE employees SET is_active = ${ph(1)}, last_seen = ${ph(2)} WHERE id = ${ph(3)}`,
      [newIsActive, parseInt(timestamp), employeeId]
    );

    const pointageId = uuidv4();
    await dbRun(`
      INSERT INTO pointages (id, employee_id, employee_name, type, timestamp, date)
      VALUES (${placeholders(6)})
    `, [pointageId, employeeId, employeeName, normalized, parseInt(timestamp), date]);

    logger.info(`✅ Pointage: ${employeeName} - ${normalized}`);
    res.status(201).json({
      success: true,
      message: `Pointage ${normalized} enregistré avec succès`,
      pointageId,
      employeeName,
      employeeType: empType,
      type: normalized,
      is_active: newIsActive,
    });
  } catch (e) {
    logger.error('❌ add_pointage:', e);
    res.status(500).json({ success: false, message: `Erreur serveur: ${e.message}` });
  }
});

app.get('/api/pointages/recent', async (req, res) => {
  try {
    const threshold = Date.now() - 10000;
    const row = await dbGet(`
      SELECT p.id, p.employee_name, p.type, p.timestamp,
             e.nom, e.prenom
      FROM pointages p
      LEFT JOIN employees e ON e.id = p.employee_id
      WHERE p.timestamp > ${ph(1)}
      ORDER BY p.timestamp DESC
      LIMIT 1
    `, [threshold]);

    const pointages = row ? [row] : [];
    if (row) logger.info(`📺 Pointage récent: ${row.prenom} ${row.nom} - ${row.type}`);
    res.json({ success: true, pointages });
  } catch (e) {
    logger.error('❌ get_recent_pointages:', e);
    res.status(500).json({ success: false, message: e.message });
  }
});

app.get('/api/pointages/history', async (req, res) => {
  try {
    const pointages = await dbAll(`
      SELECT p.id, p.employee_id, p.employee_name, p.type, p.timestamp, p.date,
             e.email, e.telephone
      FROM pointages p
      LEFT JOIN employees e ON e.id = p.employee_id
      ORDER BY p.timestamp DESC
    `);
    res.json({ success: true, pointages });
  } catch (e) {
    logger.error('❌ get_pointage_history:', e);
    res.status(500).json({ success: false, message: e.message });
  }
});

// =====================
// === API RSSI ========
// =====================

app.post('/api/rssi-data', async (req, res) => {
  const data = req.body;
  if (!data) return res.status(400).json({ success: false, message: 'Données vides' });

  logger.info(`📡 RSSI reçu via HTTP de l'Ancre #${data.anchor_id}`);

  const { anchor_id, anchor_x, anchor_y, badges = [] } = data;

  if (anchor_id == null || anchor_x == null || anchor_y == null) {
    return res.status(400).json({ success: false, message: 'Champs manquants: anchor_id, anchor_x, anchor_y' });
  }

  try {
    let processed = 0;

    for (const badge of badges) {
      const { ssid, mac, rssi } = badge;
      if (!ssid || typeof ssid !== 'string' || !ssid.trim()) continue;

      const employeeName = ssid.trim();
      const employee = await dbGet(`
        SELECT id FROM employees 
        WHERE (nom || ' ' || prenom) = ${ph(1)} OR (prenom || ' ' || nom) = ${ph(2)}
        LIMIT 1
      `, [employeeName, employeeName]);

      if (!employee) {
        logger.warn(`   ⚠️ Employé '${employeeName}' non trouvé en BDD`);
        continue;
      }

      await dbRun(`
        INSERT INTO rssi_measurements (employee_id, anchor_id, anchor_x, anchor_y, rssi, mac, timestamp)
        VALUES (${placeholders(7)})
      `, [employee.id, anchor_id, anchor_x, anchor_y, rssi, mac, Date.now()]);

      processed++;
      logger.info(`   ✅ ${employeeName} → ${rssi} dBm`);
    }

    if (processed > 0) {
      await calculateAndBroadcastPositions();
      logger.info(`   📍 Positions recalculées`);
    }

    res.json({
      success: true,
      message: `${processed}/${badges.length} mesures enregistrées`,
      processed,
      anchor_id,
    });
  } catch (e) {
    logger.error('❌ receive_rssi_data_http:', e);
    res.status(500).json({ success: false, message: e.message });
  }
});

// === Démarrage ===
app.listen(PORT, '0.0.0.0', () => {
  logger.info(`✅ Serveur démarré sur le port ${PORT}`);
});

module.exports = app;
