import os
import logging
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime
import uuid
import math
from collections import defaultdict, deque
from statistics import median, stdev
from functools import lru_cache
from typing import Dict, List, Tuple, Optional
import time

# === Import NumPy/SciPy ===
try:
    import numpy as np
    from scipy.optimize import least_squares
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# === Configuration Flask ===
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "3fb5222037e2be9d7d09019e1b46e268ec470fa2974a3981")
CORS(app, resources={r"/api/*": {"origins": "*"}})

# === Logging ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

if NUMPY_AVAILABLE:
    logger.info("✅ NumPy/SciPy disponibles - Mode haute performance")
else:
    logger.warning("⚠️ NumPy/SciPy absents - Mode dégradé")

# === DB ===
try:
    from database import init_db, get_db, verify_schema, DB_DRIVER
    logger.info("✅ Module database chargé")
except Exception as e:
    logger.error(f"❌ Erreur import database: {e}")
    raise

PLACEHOLDER = "?" if DB_DRIVER == "sqlite" else "%s"

try:
    init_db()
    verify_schema()
    logger.info("✅ Base initialisée")
except Exception as e:
    logger.error(f"❌ Erreur init DB: {e}")
    raise

# ========== CONFIGURATION DÉMO 1m² ==========

class TriangulationConfig:
    """Configuration OPTIMISÉE pour démo 1m×1m"""
    
    ZONE_WIDTH = 1.0
    ZONE_HEIGHT = 1.0
    MEASUREMENT_WINDOW = 1.5
    
    # ⚠️ À CALIBRER sur votre setup
    RSSI_TX_POWER = -45
    RSSI_PATH_LOSS = 2.2
    RSSI_MIN = -75
    RSSI_MAX = -25
    MAX_DISTANCE = 1.5
    
    EXCELLENT_RSSI = -50
    GOOD_RSSI = -60
    
    ALPHA_EXCELLENT = 0.70
    ALPHA_GOOD = 0.55
    ALPHA_WEAK = 0.35
    
    THRESHOLD_EXCELLENT = 0.01  # 1cm
    THRESHOLD_GOOD = 0.02       # 2cm
    THRESHOLD_WEAK = 0.03       # 3cm
    
    OUTLIER_SIGMA = 1.5
    MIN_ANCHORS = 3
    
    CACHE_SIZE = 32
    BATCH_SIZE = 10
    
    PROCESS_NOISE = 0.02
    MEASUREMENT_NOISE = 0.05

config = TriangulationConfig()

# ========== CACHE ==========

class PositionCache:
    def __init__(self, maxsize: int = 32, ttl: int = 3):
        self.cache: Dict[str, Tuple[float, float, float]] = {}
        self.maxsize = maxsize
        self.ttl = ttl
        self.access_order = deque()
    
    def get(self, emp_id: str) -> Optional[Tuple[float, float]]:
        if emp_id in self.cache:
            x, y, timestamp = self.cache[emp_id]
            if time.time() - timestamp < self.ttl:
                if emp_id in self.access_order:
                    self.access_order.remove(emp_id)
                self.access_order.append(emp_id)
                return (x, y)
            else:
                del self.cache[emp_id]
        return None
    
    def set(self, emp_id: str, x: float, y: float):
        if len(self.cache) >= self.maxsize:
            if self.access_order:
                oldest = self.access_order.popleft()
                if oldest in self.cache:
                    del self.cache[oldest]
        
        self.cache[emp_id] = (x, y, time.time())
        if emp_id in self.access_order:
            self.access_order.remove(emp_id)
        self.access_order.append(emp_id)
    
    def invalidate(self, emp_id: str):
        if emp_id in self.cache:
            del self.cache[emp_id]
        if emp_id in self.access_order:
            self.access_order.remove(emp_id)

position_cache = PositionCache(maxsize=config.CACHE_SIZE, ttl=2)

# ========== FILTRES JINJA2 ==========

@app.template_filter("timestamp_to_datetime")
def timestamp_to_datetime_filter(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp) / 1000).strftime("%d/%m/%Y")
    except:
        return "-"

@app.template_filter("timestamp_to_datetime_full")
def timestamp_to_datetime_full_filter(timestamp):
    try:
        dt = datetime.fromtimestamp(int(timestamp) / 1000)
        return dt.strftime("%d/%m/%Y à %H:%M")
    except:
        return "-"

# ========== FONCTIONS CALCUL ==========

@lru_cache(maxsize=1024)
def rssi_to_distance(rssi: int, tx_power: int = None, n: float = None) -> float:
    if rssi == 0:
        return -1.0
    
    tx_power = tx_power or config.RSSI_TX_POWER
    n = n or config.RSSI_PATH_LOSS
    
    rssi = max(config.RSSI_MIN, min(config.RSSI_MAX, rssi))
    
    ratio = (tx_power - rssi) / (10 * n)
    distance = math.pow(10, ratio)
    
    return round(min(distance, config.MAX_DISTANCE), 3)

def filter_outliers_iqr(distances: List[float]) -> List[float]:
    if len(distances) < 4:
        return distances
    
    sorted_dist = sorted(distances)
    n = len(sorted_dist)
    
    q1 = sorted_dist[n // 4]
    q3 = sorted_dist[3 * n // 4]
    iqr = q3 - q1
    
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    
    filtered = [d for d in distances if lower <= d <= upper]
    return filtered if filtered else [median(distances)]

def filter_outliers_sigma(distances: List[float], sigma: float = None) -> List[float]:
    if len(distances) < 3:
        return distances
    
    sigma = sigma or config.OUTLIER_SIGMA
    
    med = median(distances)
    std = stdev(distances)
    
    filtered = [d for d in distances if abs(d - med) <= sigma * std]
    return filtered if filtered else [med]

def get_adaptive_params(avg_rssi: float) -> Tuple[float, float, str]:
    if avg_rssi > config.EXCELLENT_RSSI:
        return (config.ALPHA_EXCELLENT, config.THRESHOLD_EXCELLENT, "excellent")
    elif avg_rssi > config.GOOD_RSSI:
        return (config.ALPHA_GOOD, config.THRESHOLD_GOOD, "good")
    else:
        return (config.ALPHA_WEAK, config.THRESHOLD_WEAK, "weak")

def trilateration_weighted_lsq(anchors: List[Dict]) -> Tuple[float, float]:
    if len(anchors) < config.MIN_ANCHORS:
        return (anchors[0]['x'], anchors[0]['y'])
    
    positions = np.array([[a['x'], a['y']] for a in anchors])
    distances = np.array([a['distance'] for a in anchors])
    rssis = np.array([a.get('rssi', -70) for a in anchors])
    
    weights = 1.0 / (1.0 + np.exp((rssis + 60) / 5))
    weights = weights / np.sum(weights)
    
    def residuals_weighted(p, positions, distances, weights):
        x, y = p
        predicted = np.sqrt((positions[:, 0] - x)**2 + (positions[:, 1] - y)**2)
        return (predicted - distances) * weights * 10
    
    x_init = np.sum(positions[:, 0] * weights)
    y_init = np.sum(positions[:, 1] * weights)
    
    x_init = np.clip(x_init, 0, config.ZONE_WIDTH)
    y_init = np.clip(y_init, 0, config.ZONE_HEIGHT)
    
    try:
        result = least_squares(
            residuals_weighted,
            [x_init, y_init],
            args=(positions, distances, weights),
            bounds=([0, 0], [config.ZONE_WIDTH, config.ZONE_HEIGHT]),
            method='trf',
            ftol=1e-5,
            xtol=1e-5,
            max_nfev=25
        )
        
        return round(float(result.x[0]), 3), round(float(result.x[1]), 3)
    
    except Exception as e:
        logger.warning(f"⚠️ LSQ échoué: {e}")
        return round(float(x_init), 3), round(float(y_init), 3)

def trilateration_geometric(anchors: List[Dict]) -> Tuple[float, float]:
    if len(anchors) < config.MIN_ANCHORS:
        return (anchors[0]['x'], anchors[0]['y'])
    
    anchors_sorted = sorted(anchors, key=lambda a: a['distance'])[:3]
    
    (x1, y1, r1) = (anchors_sorted[0]['x'], anchors_sorted[0]['y'], anchors_sorted[0]['distance'])
    (x2, y2, r2) = (anchors_sorted[1]['x'], anchors_sorted[1]['y'], anchors_sorted[1]['distance'])
    (x3, y3, r3) = (anchors_sorted[2]['x'], anchors_sorted[2]['y'], anchors_sorted[2]['distance'])
    
    A = 2 * (x2 - x1)
    B = 2 * (y2 - y1)
    C = r1**2 - r2**2 - x1**2 + x2**2 - y1**2 + y2**2
    D = 2 * (x3 - x2)
    E = 2 * (y3 - y2)
    F = r2**2 - r3**2 - x2**2 + x3**2 - y2**2 + y3**2
    
    denom = A * E - B * D
    
    if abs(denom) < 1e-9:
        x = (x1 + x2 + x3) / 3
        y = (y1 + y2 + y3) / 3
    else:
        x = (C * E - B * F) / denom
        y = (A * F - C * D) / denom
    
    x = max(0.0, min(config.ZONE_WIDTH, x))
    y = max(0.0, min(config.ZONE_HEIGHT, y))
    
    return round(x, 3), round(y, 3)

def trilateration(anchors: List[Dict]) -> Tuple[float, float]:
    if NUMPY_AVAILABLE:
        try:
            return trilateration_weighted_lsq(anchors)
        except Exception as e:
            logger.debug(f"LSQ échoué: {e}")
            return trilateration_geometric(anchors)
    else:
        return trilateration_geometric(anchors)

def kalman_filter_simple(new_pos: Tuple[float, float], 
                         old_pos: Tuple[float, float], 
                         process_noise: float, 
                         measurement_noise: float) -> Tuple[float, float]:
    new_x, new_y = new_pos
    old_x, old_y = old_pos
    
    K = process_noise / (process_noise + measurement_noise)
    
    filt_x = old_x + K * (new_x - old_x)
    filt_y = old_y + K * (new_y - old_y)
    
    return round(filt_x, 3), round(filt_y, 3)

def calculate_and_broadcast_positions(cursor):
    """Calcul positions optimisé pour démo 1m²"""
    start_time = time.time()
    
    threshold = int((datetime.now().timestamp() - config.MEASUREMENT_WINDOW) * 1000)
    
    cursor.execute(f"""
        SELECT employee_id, anchor_id, anchor_x, anchor_y, rssi
        FROM rssi_measurements
        WHERE timestamp > {PLACEHOLDER}
    """, (threshold,))
    
    measurements = cursor.fetchall()
    
    if not measurements:
        logger.info("ℹ️ Aucune mesure RSSI récente (fenêtre 1.5s)")
        return
    
    logger.info(f"📊 {len(measurements)} mesure(s) RSSI")
    
    employee_data = defaultdict(list)
    
    for row in measurements:
        emp_id = row[0] if DB_DRIVER == "sqlite" else row['employee_id']
        anchor_id = row[1] if DB_DRIVER == "sqlite" else row['anchor_id']
        anchor_x = row[2] if DB_DRIVER == "sqlite" else row['anchor_x']
        anchor_y = row[3] if DB_DRIVER == "sqlite" else row['anchor_y']
        rssi = row[4] if DB_DRIVER == "sqlite" else row['rssi']
        
        distance = rssi_to_distance(rssi)
        
        if distance > 0:
            employee_data[emp_id].append({
                'anchor_id': anchor_id,
                'x': anchor_x,
                'y': anchor_y,
                'distance': distance,
                'rssi': rssi
            })
    
    positions_updated = 0
    
    for emp_id, anchors in employee_data.items():
        logger.info(f"👤 Employé {emp_id[:8]}: {len(anchors)} mesure(s)")
        
        if len(anchors) < config.MIN_ANCHORS:
            logger.warning(f"   ⚠️ Insuffisant: {len(anchors)} < {config.MIN_ANCHORS}")
            continue
        
        anchor_averages = defaultdict(lambda: {
            'x': 0, 'y': 0, 'distances': [], 'rssis': []
        })
        
        for anchor in anchors:
            aid = anchor['anchor_id']
            anchor_averages[aid]['x'] = anchor['x']
            anchor_averages[aid]['y'] = anchor['y']
            anchor_averages[aid]['distances'].append(anchor['distance'])
            anchor_averages[aid]['rssis'].append(anchor['rssi'])
        
        averaged_anchors = []
        all_rssis = []
        
        for aid, data in anchor_averages.items():
            if len(data['distances']) >= 4:
                filtered = filter_outliers_iqr(data['distances'])
            else:
                filtered = filter_outliers_sigma(data['distances'])
            
            avg_distance = sum(filtered) / len(filtered)
            avg_rssi = sum(data['rssis']) / len(data['rssis'])
            
            averaged_anchors.append({
                'anchor_id': aid,
                'x': data['x'],
                'y': data['y'],
                'distance': avg_distance,
                'rssi': avg_rssi
            })
            all_rssis.append(avg_rssi)
            
            logger.info(f"   🔹 Ancre #{aid}: RSSI={avg_rssi:.0f}dBm → {avg_distance*100:.1f}cm")
        
        if len(averaged_anchors) < config.MIN_ANCHORS:
            logger.warning(f"   ⚠️ Après moyennage: {len(averaged_anchors)} < {config.MIN_ANCHORS}")
            continue
        
        logger.info(f"   📐 {len(averaged_anchors)} ancre(s) prêtes")
        
        avg_rssi = sum(all_rssis) / len(all_rssis)
        alpha, threshold, quality = get_adaptive_params(avg_rssi)
        
        new_x, new_y = trilateration(averaged_anchors)
        
        cursor.execute(f"""
            SELECT last_position_x, last_position_y 
            FROM employees 
            WHERE id = {PLACEHOLDER}
        """, (emp_id,))
        
        old_pos_row = cursor.fetchone()
        
        if old_pos_row:
            if DB_DRIVER == "sqlite":
                old_x = old_pos_row[0]
                old_y = old_pos_row[1]
            else:
                old_x = old_pos_row['last_position_x']
                old_y = old_pos_row['last_position_y']
            
            if old_x is not None and old_y is not None:
                old_x, old_y = float(old_x), float(old_y)
                
                kalman_x, kalman_y = kalman_filter_simple(
                    (new_x, new_y),
                    (old_x, old_y),
                    config.PROCESS_NOISE,
                    config.MEASUREMENT_NOISE
                )
                
                pos_x = round(alpha * kalman_x + (1 - alpha) * old_x, 3)
                pos_y = round(alpha * kalman_y + (1 - alpha) * old_y, 3)
                
                distance_moved = math.sqrt((pos_x - old_x)**2 + (pos_y - old_y)**2)
                
                if distance_moved < threshold:
                    logger.info(
                        f"   🔒 Mouvement {distance_moved*100:.1f}cm < {threshold*100:.1f}cm "
                        f"[{quality}] → maintenu"
                    )
                    continue
                
                logger.info(
                    f"   📍 POSITION MISE À JOUR: ({pos_x*100:.1f}cm, {pos_y*100:.1f}cm) "
                    f"[Δ={distance_moved*100:.1f}cm, RSSI={avg_rssi:.0f}dBm, "
                    f"α={alpha:.2f}, {quality}]"
                )
            else:
                pos_x, pos_y = new_x, new_y
                logger.info(f"   📍 Position réinit: ({pos_x*100:.1f}cm, {pos_y*100:.1f}cm)")
        else:
            pos_x, pos_y = new_x, new_y
            logger.info(f"   📍 PREMIÈRE POSITION: ({pos_x*100:.1f}cm, {pos_y*100:.1f}cm)")
        
        logger.info(f"   💾 Enregistrement BDD...")
        
        cursor.execute(f"""
            UPDATE employees
            SET last_position_x = {PLACEHOLDER}, 
                last_position_y = {PLACEHOLDER}, 
                last_seen = {PLACEHOLDER}
            WHERE id = {PLACEHOLDER}
        """, [
            float(pos_x), 
            float(pos_y), 
            int(datetime.now().timestamp() * 1000), 
            emp_id
        ])
        
        position_cache.set(emp_id, pos_x, pos_y)
        
        positions_updated += 1
    
    elapsed = (time.time() - start_time) * 1000
    
    if positions_updated > 0:
        logger.info(
            f"✅ {positions_updated} position(s) en {elapsed:.1f}ms"
        )

# ========== ROUTES WEB ==========

@app.route("/")
@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login_page"))

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or request.form
    if not data:
        return jsonify({"success": False, "message": "Données manquantes"}), 400

    username = data.get("username")
    password = data.get("password")

    if username == "admin" and password == "1234":
        session["logged_in"] = True
        return jsonify({
            "success": True,
            "token": "fake-jwt-token-123",
            "role": "admin",
            "redirect_url": url_for("dashboard")
        })

    return jsonify({"success": False, "message": "Identifiants invalides"}), 401

# ========== API EMPLOYÉS ==========

@app.route("/api/employees", methods=["GET"])
def get_all_employees():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM employees ORDER BY nom, prenom")
        rows = cursor.fetchall()

        employees = (
            [dict(row) for row in rows] if DB_DRIVER == "postgres"
            else [dict(zip([col[0] for col in cursor.description], row)) for row in rows]
        )

        conn.close()
        return jsonify({"success": True, "employees": employees})
    except Exception as e:
        logger.error(f"get_all_employees: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/employees", methods=["POST"])
def add_employee():
    record = request.get_json(silent=True)
    required = ["nom", "prenom", "type"]
    
    for field in required:
        if not record or field not in record:
            return jsonify({"success": False, "message": f"Champ manquant: {field}"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        new_id = str(uuid.uuid4())
        created_at = int(datetime.now().timestamp() * 1000)

        cursor.execute(f"""
            INSERT INTO employees (
                id, nom, prenom, type, is_active, created_at,
                email, telephone, taux_horaire, frais_ecolage,
                profession, date_naissance, lieu_naissance
            )
            VALUES (
                {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER},
                {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER},
                {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}
            )
        """, [
            new_id, record["nom"], record["prenom"], record["type"],
            record.get("is_active", 1), created_at,
            record.get("email"), record.get("telephone"), record.get("taux_horaire"),
            record.get("frais_ecolage"), record.get("profession"),
            record.get("date_naissance"), record.get("lieu_naissance")
        ])

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Employé ajouté",
            "id": new_id
        }), 201

    except Exception as e:
        logger.error(f"add_employee: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/employees/<id>", methods=["PUT"])
def update_employee(id):
    record = request.get_json(silent=True)
    if not record:
        return jsonify({"success": False, "message": "Requête vide"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(f"""
            UPDATE employees
            SET nom = {PLACEHOLDER}, prenom = {PLACEHOLDER}, type = {PLACEHOLDER}, is_active = {PLACEHOLDER},
                email = {PLACEHOLDER}, telephone = {PLACEHOLDER},
                taux_horaire = {PLACEHOLDER}, frais_ecolage = {PLACEHOLDER},
                profession = {PLACEHOLDER}, date_naissance = {PLACEHOLDER}, lieu_naissance = {PLACEHOLDER}
            WHERE id = {PLACEHOLDER}
        """, [
            record.get("nom"), record.get("prenom"), record.get("type"), record.get("is_active", 1),
            record.get("email"), record.get("telephone"),
            record.get("taux_horaire"), record.get("frais_ecolage"),
            record.get("profession"), record.get("date_naissance"), record.get("lieu_naissance"),
            id
        ])

        conn.commit()
        position_cache.invalidate(id)
        
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Employé modifié"}), 200
    except Exception as e:
        logger.error(f"update_employee: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/employees/<id>", methods=["DELETE"])
def delete_employee(id):
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(f"DELETE FROM pointages WHERE employee_id = {PLACEHOLDER}", [id])
        cur.execute(f"DELETE FROM rssi_measurements WHERE employee_id = {PLACEHOLDER}", [id])
        cur.execute(f"DELETE FROM salaries WHERE employee_id = {PLACEHOLDER}", [id])
        cur.execute(f"DELETE FROM employees WHERE id = {PLACEHOLDER}", [id])

        conn.commit()
        position_cache.invalidate(id)
        
        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Employé non trouvé"}), 404
        
        cur.close()
        conn.close()
        
        logger.info(f"Employé {id[:8]} supprimé")
        return jsonify({"success": True, "message": "Employé supprimé"}), 200
        
    except Exception as e:
        logger.error(f"delete_employee: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/employees/active", methods=["GET"])
def get_active_employees():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, nom, prenom, type, is_active, created_at,
                   email, telephone, taux_horaire, frais_ecolage,
                   profession, date_naissance, lieu_naissance,
                   last_position_x, last_position_y, last_seen
            FROM employees 
            WHERE is_active = 1
            ORDER BY nom, prenom
        """)
        rows = cursor.fetchall()

        employees = (
            [dict(row) for row in rows] if DB_DRIVER == "postgres"
            else [dict(zip([col[0] for col in cursor.description], row)) for row in rows]
        )

        conn.close()
        return jsonify({"success": True, "employees": employees}), 200
    except Exception as e:
        logger.error(f"get_active_employees: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ========== API SALAIRES ==========

@app.route("/api/salary", methods=["POST"])
def add_salary():
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({"success": False, "message": "Requête vide"}), 400

    employee_id = data.get("employeeId") or data.get("employee_id")
    employee_name = data.get("employeeName") or data.get("employee_name")
    amount = data.get("amount")
    record_type = data.get("type")
    hours_worked = data.get("hoursWorked") or data.get("hours_worked", 0.0)

    if not employee_name or not isinstance(employee_name, str) or not employee_name.strip():
        return jsonify({"success": False, "message": "employeeName manquant"}), 400

    if not amount or not record_type:
        return jsonify({"success": False, "message": "Champs manquants"}), 400

    try:
        amount = float(amount)
        if amount <= 0:
            return jsonify({"success": False, "message": "Montant invalide"}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Montant non numérique"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        employee_name = employee_name.strip()

        if employee_id:
            cur.execute(f"SELECT id, nom, prenom FROM employees WHERE id = {PLACEHOLDER}", (employee_id,))
            employee = cur.fetchone()
        else:
            if DB_DRIVER == "sqlite":
                cur.execute(f"""
                    SELECT id FROM employees 
                    WHERE LOWER(nom || ' ' || prenom) = LOWER({PLACEHOLDER})
                       OR LOWER(prenom || ' ' || nom) = LOWER({PLACEHOLDER})
                    LIMIT 1
                """, (employee_name, employee_name))
            else:
                cur.execute(f"""
                    SELECT id FROM employees 
                    WHERE LOWER(CONCAT(nom, ' ', prenom)) = LOWER({PLACEHOLDER})
                       OR LOWER(CONCAT(prenom, ' ', nom)) = LOWER({PLACEHOLDER})
                    LIMIT 1
                """, (employee_name, employee_name))
            
            employee = cur.fetchone()
            
            if employee:
                employee_id = employee[0] if DB_DRIVER == "sqlite" else employee['id']
            else:
                emp_name_parts = employee_name.split(" ", 1)
                prenom = emp_name_parts[0] if emp_name_parts else "Inconnu"
                nom = emp_name_parts[1] if len(emp_name_parts) > 1 else employee_name
                
                employee_id = str(uuid.uuid4())
                
                cur.execute(f"""
                    INSERT INTO employees (id, nom, prenom, type, is_active, created_at)
                    VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
                """, [employee_id, nom, prenom, "employe", 1, int(datetime.now().timestamp() * 1000)])

        salary_date = int(data.get("date", datetime.now().timestamp() * 1000))
        period = data.get("period") or datetime.now().strftime("%Y-%m")
        salary_id = data.get("id") or str(uuid.uuid4())

        cur.execute(f"SELECT id FROM salaries WHERE id = {PLACEHOLDER}", (salary_id,))
        existing = cur.fetchone()

        if existing:
            cur.execute(f"""
                UPDATE salaries 
                SET employee_id = {PLACEHOLDER}, employee_name = {PLACEHOLDER}, 
                    amount = {PLACEHOLDER}, hours_worked = {PLACEHOLDER}, 
                    type = {PLACEHOLDER}, period = {PLACEHOLDER}, date = {PLACEHOLDER}
                WHERE id = {PLACEHOLDER}
            """, [employee_id, employee_name, amount, hours_worked, record_type, period, salary_date, salary_id])
            action = "mis à jour"
        else:
            cur.execute(f"""
                INSERT INTO salaries (id, employee_id, employee_name, amount, hours_worked, type, period, date)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
            """, [salary_id, employee_id, employee_name, amount, hours_worked, record_type, period, salary_date])
            action = "créé"

        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True, 
            "message": f"Salaire {action}",
            "id": salary_id,
            "employeeId": employee_id,
            "action": action
        }), 201 if action == "créé" else 200

    except Exception as e:
        logger.error(f"add_salary: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/salary/history", methods=["GET"])
def get_salary_history():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(f"""
            SELECT s.id, s.employee_id, s.employee_name, s.amount, s.hours_worked, 
                   s.type, s.period, s.date,
                   e.email, e.telephone, e.taux_horaire, e.frais_ecolage,
                   e.date_naissance, e.lieu_naissance
            FROM salaries s
            LEFT JOIN employees e ON e.id = s.employee_id
            WHERE s.employee_id IS NOT NULL 
              AND s.employee_name IS NOT NULL 
              AND s.employee_name != ''
              AND s.amount > 0
            ORDER BY s.date DESC
        """)
        rows = cur.fetchall()

        salaries = (
            [dict(row) for row in rows] if DB_DRIVER == "postgres"
            else [dict(zip([col[0] for col in cur.description], row)) for row in rows]
        )

        for record in salaries:
            if record.get("hours_worked") is None:
                record["hours_worked"] = 0.0
            if record.get("period") is None:
                record["period"] = ""

        cur.close()
        conn.close()
        return jsonify({"success": True, "salaries": salaries}), 200

    except Exception as e:
        logger.error(f"get_salary_history: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ========== API RSSI ==========

@app.route("/api/rssi-data", methods=["POST"])
def receive_rssi_data_http():
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({"success": False, "message": "Données vides"}), 400
    
    try:
        anchor_id = data.get("anchor_id")
        anchor_x = data.get("anchor_x")
        anchor_y = data.get("anchor_y")
        badges = data.get("badges", [])
        
        if anchor_id is None or anchor_x is None or anchor_y is None:
            return jsonify({"success": False, "message": "Champs manquants"}), 400
        
        logger.info(f"📡 Ancre #{anchor_id} ({anchor_x*100:.0f}cm, {anchor_y*100:.0f}cm): {len(badges)} badge(s)")
        
        conn = get_db()
        cur = conn.cursor()
        
        processed = 0
        
        for badge in badges:
            ssid = badge.get("ssid")
            mac = badge.get("mac")
            rssi = badge.get("rssi")
            
            if not ssid or not isinstance(ssid, str) or ssid.strip() == "":
                logger.warning(f"   ⚠️ SSID invalide")
                continue
            
            employee_name = ssid.strip()
            logger.info(f"   🔍 Recherche: '{employee_name}'")
            
            if DB_DRIVER == "sqlite":
                cur.execute(f"""
                    SELECT id, nom, prenom FROM employees 
                    WHERE LOWER(nom || ' ' || prenom) = LOWER({PLACEHOLDER})
                       OR LOWER(prenom || ' ' || nom) = LOWER({PLACEHOLDER})
                    LIMIT 1
                """, (employee_name, employee_name))
            else:
                cur.execute(f"""
                    SELECT id, nom, prenom FROM employees 
                    WHERE LOWER(CONCAT(nom, ' ', prenom)) = LOWER({PLACEHOLDER})
                       OR LOWER(CONCAT(prenom, ' ', nom)) = LOWER({PLACEHOLDER})
                    LIMIT 1
                """, (employee_name, employee_name))
            
            employee = cur.fetchone()
            
            if not employee:
                logger.error(f"   ❌ '{employee_name}' NON TROUVÉ")
                logger.error(f"      SSID badge = 'Nom Prénom' exact")
                continue
            
            employee_id = employee[0] if DB_DRIVER == "sqlite" else employee['id']
            emp_nom = employee[1] if DB_DRIVER == "sqlite" else employee['nom']
            emp_prenom = employee[2] if DB_DRIVER == "sqlite" else employee['prenom']
            
            logger.info(f"   ✅ Trouvé: {emp_prenom} {emp_nom}")
            
            cur.execute(f"""
                INSERT INTO rssi_measurements (employee_id, anchor_id, anchor_x, anchor_y, rssi, mac, timestamp)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
            """, [employee_id, anchor_id, anchor_x, anchor_y, rssi, mac, int(datetime.now().timestamp() * 1000)])
            
            distance_cm = rssi_to_distance(rssi) * 100
            processed += 1
            logger.info(f"   📶 RSSI: {rssi}dBm → {distance_cm:.1f}cm")
        
        conn.commit()
        
        if processed > 0:
            logger.info(f"🔄 Calcul positions...")
            calculate_and_broadcast_positions(cur)
            conn.commit()
        else:
            logger.warning(f"⚠️ 0/{len(badges)} mesures valides")
        
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True, 
            "message": f"{processed}/{len(badges)} mesures",
            "processed": processed,
            "anchor_id": anchor_id
        }), 200
        
    except Exception as e:
        logger.error(f"receive_rssi_data: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500

# ========== API POINTAGES ==========

@app.route("/api/pointages", methods=["POST"])
def add_pointage():
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({"success": False, "message": "Requête vide"}), 400
    
    emp_id = data.get("employeeId")
    pointage_type = data.get("type", "").lower().strip()
    timestamp = data.get("timestamp")
    date = data.get("date")
    
    if not emp_id or not pointage_type or not timestamp or not date:
        return jsonify({"success": False, "message": "Champs manquants"}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute(f"SELECT id, nom, prenom, type FROM employees WHERE id = {PLACEHOLDER}", (emp_id,))
        employee = cur.fetchone()
        
        if not employee:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Employé non trouvé"}), 404
        
        emp_nom = employee[1] if DB_DRIVER == "sqlite" else employee['nom']
        emp_prenom = employee[2] if DB_DRIVER == "sqlite" else employee['prenom']
        emp_type = employee[3] if DB_DRIVER == "sqlite" else employee['type']
        employee_name = f"{emp_nom} {emp_prenom}"
        
        if pointage_type in ['entree', 'entrée', 'entry', 'in']:
            pointage_type = 'arrivee'
        elif pointage_type in ['sortie', 'exit', 'out']:
            pointage_type = 'sortie'
        elif pointage_type not in ['arrivee', 'sortie']:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Type invalide"}), 400
        
        new_is_active = 1 if pointage_type == 'arrivee' else 0
        
        cur.execute(f"""
            UPDATE employees 
            SET is_active = {PLACEHOLDER}, last_seen = {PLACEHOLDER}
            WHERE id = {PLACEHOLDER}
        """, [new_is_active, int(timestamp), emp_id])
        
        pointage_id = str(uuid.uuid4())
        cur.execute(f"""
            INSERT INTO pointages (id, employee_id, employee_name, type, timestamp, date)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        """, [pointage_id, emp_id, employee_name, pointage_type, int(timestamp), date])
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Pointage: {employee_name} - {pointage_type}")
        
        return jsonify({
            "success": True,
            "message": f"Pointage {pointage_type} enregistré",
            "pointageId": pointage_id,
            "employeeName": employee_name,
            "employeeType": emp_type,
            "type": pointage_type,
            "is_active": new_is_active
        }), 201
        
    except Exception as e:
        logger.error(f"add_pointage: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/pointages/history", methods=["GET"])
def get_pointage_history():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(f"""
            SELECT p.id, p.employee_id, p.employee_name, p.type, p.timestamp, p.date,
                   e.email, e.telephone
            FROM pointages p
            LEFT JOIN employees e ON e.id = p.employee_id
            ORDER BY p.timestamp DESC
        """)
        rows = cur.fetchall()

        pointages = (
            [dict(row) for row in rows] if DB_DRIVER == "postgres"
            else [dict(zip([col[0] for col in cur.description], row)) for row in rows]
        )

        cur.close()
        conn.close()
        return jsonify({"success": True, "pointages": pointages}), 200
    except Exception as e:
        logger.error(f"get_pointage_history: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/pointages/recent", methods=["GET"])
def get_recent_pointages():
    try:
        threshold = int((datetime.now().timestamp() - 10) * 1000)
        
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute(f"""
            SELECT p.id, p.employee_name, p.type, p.timestamp,
                   e.nom, e.prenom
            FROM pointages p
            LEFT JOIN employees e ON e.id = p.employee_id
            WHERE p.timestamp > {PLACEHOLDER}
            ORDER BY p.timestamp DESC
            LIMIT 1
        """, (threshold,))
        
        row = cur.fetchone()
        pointages = []
        
        if row:
            if DB_DRIVER == "sqlite":
                pointage = {
                    "id": row[0],
                    "employee_name": row[1],
                    "type": row[2],
                    "timestamp": row[3],
                    "nom": row[4],
                    "prenom": row[5]
                }
            else:
                pointage = {
                    "id": row['id'],
                    "employee_name": row['employee_name'],
                    "type": row['type'],
                    "timestamp": row['timestamp'],
                    "nom": row['nom'],
                    "prenom": row['prenom']
                }
            pointages.append(pointage)
        
        cur.close()
        conn.close()
        
        return jsonify({"success": True, "pointages": pointages}), 200
        
    except Exception as e:
        logger.error(f"get_recent_pointages: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ========== DASHBOARD ==========

@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT s.id, s.employee_id, s.employee_name, s.amount, s.hours_worked, 
                   s.type AS payment_type, s.period, s.date,
                   e.nom, e.prenom, e.type, 
                   e.email, e.telephone, e.taux_horaire, e.frais_ecolage,
                   e.date_naissance, e.lieu_naissance
            FROM salaries s
            LEFT JOIN employees e ON e.id = s.employee_id
            ORDER BY s.date DESC
        """)
        rows = cursor.fetchall()

        payments = (
            [dict(row) for row in rows] if DB_DRIVER == "postgres"
            else [dict(zip([col[0] for col in cursor.description], row)) for row in rows]
        )

        conn.close()
        return render_template("dashboard.html", payments=payments)
    except Exception as e:
        logger.error(f"dashboard: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ========== DÉMARRAGE ==========

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🚀 Démarrage port {port}")
    logger.info(f"⚙️ DÉMO 1m²: fenêtre={config.MEASUREMENT_WINDOW}s, zone={config.ZONE_WIDTH}×{config.ZONE_HEIGHT}m")
    logger.info(f"⚙️ Seuils: excellent={config.THRESHOLD_EXCELLENT*100:.1f}cm, good={config.THRESHOLD_GOOD*100:.1f}cm")
    logger.info(f"⚙️ Alpha: excellent={config.ALPHA_EXCELLENT}, good={config.ALPHA_GOOD}")
    app.run(host="0.0.0.0", port=port, debug=False)
