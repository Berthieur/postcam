import os
import logging
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime
import uuid
import math
from collections import defaultdict

# === Import NumPy/SciPy pour calculs précis ===
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

# === Logger ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Vérification NumPy/SciPy ===
if NUMPY_AVAILABLE:
    logger.info("✅ NumPy et SciPy disponibles pour calculs précis")
else:
    logger.warning("⚠️ NumPy/SciPy non disponibles, utilisation de math standard")

# === DB imports ===
try:
    from database import init_db, get_db, verify_schema, DB_DRIVER
    logger.info("✅ database.py importé")
except Exception as e:
    logger.error(f"❌ Échec import database.py : {e}")
    raise

# === Placeholder SQL ===
PLACEHOLDER = "?" if DB_DRIVER == "sqlite" else "%s"

# --- Initialisation DB ---
try:
    init_db()
    verify_schema()
    logger.info("✅ Base initialisée et schéma vérifié")
except Exception as e:
    logger.error(f"❌ Échec init_db/verify_schema : {e}")
    raise

# === Filtres Jinja2 ===
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

# === Routes Web ===
@app.route("/")
@app.route("/login")
def login_page():
    logger.info("📄 Page de connexion")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    logger.info("✅ Déconnexion")
    return redirect(url_for("login_page"))

# === API Login ===
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

# === GET employés ===
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
        logger.error(f"❌ get_all_employees: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# === POST ajouter employé ===
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
            "message": "Employé ajouté avec succès",
            "id": new_id
        }), 201

    except Exception as e:
        logger.error(f"❌ add_employee: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# === POST ajouter salaire ===
@app.route("/api/salary", methods=["POST"])
def add_salary():
    data = request.get_json(silent=True)
    logger.info(f"📥 Données reçues: {data}")

    if not data:
        logger.error("❌ Requête vide")
        return jsonify({"success": False, "message": "Requête vide"}), 400

    employee_id = data.get("employeeId") or data.get("employee_id")
    employee_name = data.get("employeeName") or data.get("employee_name")
    amount = data.get("amount")
    record_type = data.get("type")
    hours_worked = data.get("hoursWorked") or data.get("hours_worked", 0.0)

    if not employee_name or not isinstance(employee_name, str) or not employee_name.strip():
        logger.error(f"❌ employeeName manquant ou vide: {repr(employee_name)}")
        return jsonify({"success": False, "message": "Champ manquant ou vide: employeeName"}), 400

    if not amount:
        logger.error(f"❌ amount manquant")
        return jsonify({"success": False, "message": "Champ manquant ou vide: amount"}), 400

    if not record_type:
        logger.error(f"❌ type manquant")
        return jsonify({"success": False, "message": "Champ manquant ou vide: type"}), 400

    try:
        amount = float(amount)
        if amount <= 0:
            logger.error(f"❌ Montant invalide: {amount}")
            return jsonify({"success": False, "message": "Le montant doit être supérieur à 0"}), 400
    except (ValueError, TypeError):
        logger.error(f"❌ Montant non numérique: {data.get('amount')}")
        return jsonify({"success": False, "message": "Le montant doit être un nombre valide"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        employee_name = employee_name.strip()

        if employee_id:
            cur.execute(f"SELECT id, nom, prenom FROM employees WHERE id = {PLACEHOLDER}", (employee_id,))
            employee = cur.fetchone()

            if not employee:
                logger.warning(f"⚠️ Employé {employee_id} non trouvé")
        else:
            cur.execute(f"""
                SELECT id FROM employees 
                WHERE CONCAT(nom, ' ', prenom) = {PLACEHOLDER} 
                   OR CONCAT(prenom, ' ', nom) = {PLACEHOLDER}
                LIMIT 1
            """, (employee_name, employee_name))
            
            employee = cur.fetchone()
            
            if employee:
                employee_id = employee[0] if DB_DRIVER == "sqlite" else employee['id']
                logger.info(f"✅ Employé trouvé par nom: {employee_id}")
            else:
                logger.warning(f"⚠️ Employé '{employee_name}' non trouvé, création automatique")
                emp_name_parts = employee_name.split(" ", 1)
                prenom = emp_name_parts[0] if len(emp_name_parts) > 0 else "Inconnu"
                nom = emp_name_parts[1] if len(emp_name_parts) > 1 else employee_name
                
                employee_id = str(uuid.uuid4())
                
                cur.execute(f"""
                    INSERT INTO employees (id, nom, prenom, type, is_active, created_at)
                    VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
                """, [employee_id, nom, prenom, "employe", 1, int(datetime.now().timestamp() * 1000)])
                
                logger.info(f"✅ Nouvel employé créé: {employee_id}")

        salary_date = int(data.get("date", datetime.now().timestamp() * 1000))
        period = data.get("period") or datetime.now().strftime("%Y-%m")
        salary_id = data.get("id") or str(uuid.uuid4())

        cur.execute(f"SELECT id FROM salaries WHERE id = {PLACEHOLDER}", (salary_id,))
        existing = cur.fetchone()

        if existing:
            logger.warning(f"⚠️ Salaire {salary_id} existe déjà, mise à jour au lieu d'insertion")
            
            cur.execute(f"""
                UPDATE salaries 
                SET employee_id = {PLACEHOLDER}, employee_name = {PLACEHOLDER}, 
                    amount = {PLACEHOLDER}, hours_worked = {PLACEHOLDER}, 
                    type = {PLACEHOLDER}, period = {PLACEHOLDER}, date = {PLACEHOLDER}
                WHERE id = {PLACEHOLDER}
            """, [
                employee_id, employee_name, amount, hours_worked,
                record_type, period, salary_date, salary_id
            ])
            
            action = "mis à jour"
        else:
            cur.execute(f"""
                INSERT INTO salaries (id, employee_id, employee_name, amount, hours_worked, type, period, date)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
            """, [
                salary_id, employee_id, employee_name, amount, hours_worked,
                record_type, period, salary_date
            ])
            
            action = "créé"

        conn.commit()
        logger.info(f"✅ Salaire {action}: ID={salary_id}, employee_id={employee_id}, amount={amount}, type={record_type}")

        cur.close()
        conn.close()
        
        return jsonify({
            "success": True, 
            "message": f"Salaire {action} avec succès", 
            "id": salary_id,
            "employeeId": employee_id,
            "action": action
        }), 201 if action == "créé" else 200

    except Exception as e:
        logger.error(f"❌ add_salary: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500

# === PUT modifier employé ===
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
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Employé modifié"}), 200
    except Exception as e:
        logger.error(f"❌ update_employee: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# === DELETE supprimer employé ===
@app.route("/api/employees/<id>", methods=["DELETE"])
def delete_employee(id):
    try:
        conn = get_db()
        cur = conn.cursor()

        # ✅ Supprimer d'abord toutes les dépendances dans l'ordre
        cur.execute(f"DELETE FROM pointages WHERE employee_id = {PLACEHOLDER}", [id])
        cur.execute(f"DELETE FROM rssi_measurements WHERE employee_id = {PLACEHOLDER}", [id])
        cur.execute(f"DELETE FROM salaries WHERE employee_id = {PLACEHOLDER}", [id])
        
        # ✅ Enfin, supprimer l'employé
        cur.execute(f"DELETE FROM employees WHERE id = {PLACEHOLDER}", [id])

        conn.commit()
        
        # Vérifier combien de lignes ont été supprimées
        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Employé non trouvé"}), 404
        
        cur.close()
        conn.close()
        
        logger.info(f"✅ Employé {id} et toutes ses données supprimés")
        return jsonify({"success": True, "message": "Employé supprimé avec succès"}), 200
        
    except Exception as e:
        logger.error(f"❌ delete_employee: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Erreur lors de la suppression: {str(e)}"}), 500

# === GET historique salaires ===
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
        logger.info(f"📤 Historique salaires renvoyé: {len(salaries)} enregistrements")
        return jsonify({"success": True, "salaries": salaries}), 200

    except Exception as e:
        logger.error(f"❌ get_salary_history: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# === Dashboard ===
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
        logger.error(f"❌ dashboard: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ========== ROUTE HTTP POUR RSSI ==========
@app.route("/api/rssi-data", methods=["POST"])
def receive_rssi_data_http():
    """
    Reçoit les données RSSI via HTTP POST depuis ESP32
    """
    data = request.get_json(silent=True)
    
    if not data:
        logger.error("❌ Requête vide")
        return jsonify({"success": False, "message": "Données vides"}), 400
    
    logger.info(f"📡 RSSI reçu via HTTP de l'Ancre #{data.get('anchor_id')}")
    
    try:
        anchor_id = data.get("anchor_id")
        anchor_x = data.get("anchor_x")
        anchor_y = data.get("anchor_y")
        badges = data.get("badges", [])
        
        if anchor_id is None or anchor_x is None or anchor_y is None:
            return jsonify({
                "success": False, 
                "message": "Champs manquants: anchor_id, anchor_x, anchor_y"
            }), 400
        
        logger.info(f"   Position: ({anchor_x}, {anchor_y})")
        logger.info(f"   Badges détectés: {len(badges)}")
        
        conn = get_db()
        cur = conn.cursor()
        
        processed = 0
        
        for badge in badges:
            ssid = badge.get("ssid")
            mac = badge.get("mac")
            rssi = badge.get("rssi")
            
            if not ssid or not isinstance(ssid, str) or ssid.strip() == "":
                logger.warning(f"   ⚠️ SSID invalide: {repr(ssid)}")
                continue
            
            employee_name = ssid.strip()
            
            cur.execute(f"""
                SELECT id, nom, prenom FROM employees 
                WHERE CONCAT(nom, ' ', prenom) = {PLACEHOLDER}
                   OR CONCAT(prenom, ' ', nom) = {PLACEHOLDER}
                LIMIT 1
            """, (employee_name, employee_name))
            
            employee = cur.fetchone()
            
            if not employee:
                logger.warning(f"   ⚠️ Employé '{employee_name}' non trouvé en BDD")
                continue
            
            employee_id = employee[0] if DB_DRIVER == "sqlite" else employee['id']
            
            cur.execute(f"""
                INSERT INTO rssi_measurements (employee_id, anchor_id, anchor_x, anchor_y, rssi, mac, timestamp)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
            """, [
                employee_id, anchor_id, anchor_x, anchor_y, rssi, mac,
                int(datetime.now().timestamp() * 1000)
            ])
            
            processed += 1
            logger.info(f"   ✅ {employee_name} → {rssi} dBm")
        
        conn.commit()
        
        if processed > 0:
            calculate_and_broadcast_positions(cur)
            conn.commit()
            logger.info(f"   📍 Positions recalculées")
        
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True, 
            "message": f"{processed}/{len(badges)} mesures enregistrées",
            "processed": processed,
            "anchor_id": anchor_id
        }), 200
        
    except Exception as e:
        logger.error(f"❌ receive_rssi_data_http: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500

# ========== FONCTIONS DE CALCUL OPTIMISÉES ==========

def rssi_to_distance(rssi, tx_power=-59, n=2.5):
    """
    Convertit un RSSI en distance estimée (mètres).
    Modèle de propagation: d = 10^((TxPower - RSSI) / (10 * n))
    
    Args:
        rssi: Signal reçu en dBm
        tx_power: Puissance d'émission de référence à 1m (calibré)
        n: Exposant de perte de trajet (2.0 = espace libre, 2.5-3.5 = intérieur)
    """
    if rssi == 0:
        return -1.0
    
    # Filtrage des valeurs aberrantes
    if rssi > -30 or rssi < -100:
        logger.warning(f"⚠️ RSSI hors limites: {rssi} dBm")
        rssi = max(-100, min(-30, rssi))
    
    ratio = (tx_power - rssi) / (10 * n)
    distance = math.pow(10, ratio)
    
    # Limite la distance max à 15m pour éviter les valeurs aberrantes
    return round(min(distance, 15.0), 2)

def trilateration_numpy(anchors):
    """
    Trilatération optimisée avec NumPy/SciPy (moindres carrés non linéaires).
    Résout le système: min Σ((x - xi)² + (y - yi)² - ri²)²
    """
    if len(anchors) < 3:
        return (anchors[0]['x'], anchors[0]['y'])
    
    # Préparer les données
    positions = np.array([[a['x'], a['y']] for a in anchors])
    distances = np.array([a['distance'] for a in anchors])
    
    # Fonction objectif pour least_squares
    def equations(p, positions, distances):
        x, y = p
        return np.sqrt((positions[:, 0] - x)**2 + (positions[:, 1] - y)**2) - distances
    
    # Point initial = centroïde pondéré par inverse des distances
    weights = 1.0 / (distances + 0.1)  # Éviter division par zéro
    x_init = np.sum(positions[:, 0] * weights) / np.sum(weights)
    y_init = np.sum(positions[:, 1] * weights) / np.sum(weights)
    
    # Résolution par moindres carrés
    result = least_squares(
        equations, 
        [x_init, y_init], 
        args=(positions, distances),
        method='lm',  # Levenberg-Marquardt
        max_nfev=100
    )
    
    x, y = result.x
    
    # Limiter aux dimensions de la zone (0-6m × 0-5m)
    x = max(0.0, min(6.0, x))
    y = max(0.0, min(5.0, y))
    
    # ✅ IMPORTANT: Convertir np.float64 en float Python pour PostgreSQL
    return round(float(x), 2), round(float(y), 2)

def trilateration_basic(anchors):
    """
    Trilatération géométrique classique (fallback si NumPy indisponible).
    """
    anchors = sorted(anchors, key=lambda x: x['distance'])[:3]

    (x1, y1, r1), (x2, y2, r2), (x3, y3, r3) = \
        (anchors[0]['x'], anchors[0]['y'], anchors[0]['distance']), \
        (anchors[1]['x'], anchors[1]['y'], anchors[1]['distance']), \
        (anchors[2]['x'], anchors[2]['y'], anchors[2]['distance'])

    A = 2*(x2 - x1)
    B = 2*(y2 - y1)
    C = r1**2 - r2**2 - x1**2 + x2**2 - y1**2 + y2**2
    D = 2*(x3 - x2)
    E = 2*(y3 - y2)
    F = r2**2 - r3**2 - x2**2 + x3**2 - y2**2 + y3**2

    denom = (A*E - B*D)
    if abs(denom) < 1e-6:  # Éviter division par zéro
        return (x1, y1)

    x = (C*E - B*F) / denom
    y = (A*F - C*D) / denom
    
    # Limiter aux dimensions de la zone
    x = max(0.0, min(6.0, x))
    y = max(0.0, min(5.0, y))
    
    return round(x, 2), round(y, 2)

def trilateration(anchors):
    """
    Point d'entrée principal pour la trilatération.
    Utilise NumPy si disponible, sinon méthode géométrique.
    """
    if NUMPY_AVAILABLE:
        try:
            return trilateration_numpy(anchors)
        except Exception as e:
            logger.warning(f"⚠️ Échec trilatération NumPy: {e}, utilisation méthode basique")
            return trilateration_basic(anchors)
    else:
        return trilateration_basic(anchors)

def calculate_and_broadcast_positions(cursor):
    """
    Calcule la position de chaque employé actif via trilatération optimisée.
    Applique un filtre de lissage exponentiel pour stabiliser les positions.
    NOUVEAU: Seuil adaptatif selon qualité du signal RSSI.
    """
    # ✅ Fenêtre élargie à 8 secondes pour plus de stabilité
    threshold = int((datetime.now().timestamp() - 8) * 1000)

    cursor.execute(f"""
        SELECT employee_id, anchor_id, anchor_x, anchor_y, rssi
        FROM rssi_measurements
        WHERE timestamp > {PLACEHOLDER}
    """, (threshold,))

    measurements = cursor.fetchall()

    if not measurements:
        logger.info("   ℹ️ Aucune mesure récente pour triangulation")
        return

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

    for emp_id, anchors in employee_data.items():
        if len(anchors) >= 3:
            # ✅ Moyenner les mesures par ancre pour réduire le bruit
            anchor_averages = defaultdict(lambda: {'x': 0, 'y': 0, 'distances': [], 'rssis': [], 'count': 0})
            
            for anchor in anchors:
                aid = anchor['anchor_id']
                anchor_averages[aid]['x'] = anchor['x']
                anchor_averages[aid]['y'] = anchor['y']
                anchor_averages[aid]['distances'].append(anchor['distance'])
                anchor_averages[aid]['rssis'].append(anchor['rssi'])
                anchor_averages[aid]['count'] += 1
            
            # Calculer distance moyenne par ancre
            averaged_anchors = []
            all_rssis = []
            
            for aid, data in anchor_averages.items():
                avg_distance = sum(data['distances']) / len(data['distances'])
                avg_rssi = sum(data['rssis']) / len(data['rssis'])
                
                averaged_anchors.append({
                    'anchor_id': aid,
                    'x': data['x'],
                    'y': data['y'],
                    'distance': avg_distance,
                    'rssi': avg_rssi
                })
                all_rssis.append(avg_rssi)
            
            if len(averaged_anchors) < 3:
                logger.info(f"   ⚠️ Employé {emp_id}: seulement {len(averaged_anchors)} ancres après moyennage")
                continue
            
            # ✅ NOUVEAU: Calculer qualité moyenne des signaux
            avg_rssi = sum(all_rssis) / len(all_rssis)
            
            # Classifier la qualité du signal
            if avg_rssi > -60:
                signal_quality = "excellent"
                movement_threshold = 0.05  # 5cm - très précis
                alpha = 0.20  # Plus réactif
            elif avg_rssi > -70:
                signal_quality = "good"
                movement_threshold = 0.10  # 10cm - bon équilibre
                alpha = 0.15  # Équilibré
            else:
                signal_quality = "weak"
                movement_threshold = 0.20  # 20cm - plus stable
                alpha = 0.10  # Très stable
            
            # Calculer nouvelle position
            new_x, new_y = trilateration(averaged_anchors)
            
            # Récupérer ancienne position pour lissage
            cursor.execute(f"""
                SELECT last_position_x, last_position_y 
                FROM employees 
                WHERE id = {PLACEHOLDER}
            """, (emp_id,))
            
            old_pos = cursor.fetchone()
            
            if old_pos:
                if DB_DRIVER == "sqlite":
                    old_x = old_pos[0]
                    old_y = old_pos[1]
                else:
                    old_x = old_pos['last_position_x']
                    old_y = old_pos['last_position_y']
                
                if old_x is not None and old_y is not None:
                    # ✅ Filtre adaptatif selon qualité signal
                    pos_x = round(alpha * new_x + (1 - alpha) * old_x, 2)
                    pos_y = round(alpha * new_y + (1 - alpha) * old_y, 2)
                    
                    # ✅ Seuil de mise à jour adaptatif
                    distance_moved = ((pos_x - old_x)**2 + (pos_y - old_y)**2)**0.5
                    
                    if distance_moved < movement_threshold:
                        logger.info(
                            f"   🔒 Employé {emp_id}: mouvement négligeable "
                            f"({distance_moved:.2f}m < {movement_threshold}m), "
                            f"signal={signal_quality} ({avg_rssi:.0f}dBm), position maintenue"
                        )
                        continue  # Ne pas mettre à jour
                    
                    # Conversion pour PostgreSQL
                    pos_x = float(pos_x)
                    pos_y = float(pos_y)
                    
                    logger.info(
                        f"   📍 Position employé {emp_id}: ({pos_x:.2f}, {pos_y:.2f}) "
                        f"[mouvement={distance_moved:.2f}m, signal={signal_quality}, "
                        f"RSSI={avg_rssi:.0f}dBm, alpha={alpha}]"
                    )
                else:
                    pos_x, pos_y = float(new_x), float(new_y)
                    logger.info(f"   📍 Position initiale employé {emp_id}: ({pos_x:.2f}, {pos_y:.2f})")
            else:
                pos_x, pos_y = float(new_x), float(new_y)
                logger.info(f"   📍 Première position employé {emp_id}: ({pos_x:.2f}, {pos_y:.2f})")

            cursor.execute(f"""
                UPDATE employees
                SET last_position_x = {PLACEHOLDER}, last_position_y = {PLACEHOLDER}, last_seen = {PLACEHOLDER}
                WHERE id = {PLACEHOLDER}
            """, [pos_x, pos_y, int(datetime.now().timestamp() * 1000), emp_id])

        else:
            logger.info(f"   ⚠️ Employé {emp_id}: seulement {len(anchors)} ancres (min 3 requis)")
# ========== AUTRES ROUTES ==========

@app.route("/api/pointages/recent", methods=["GET"])
def get_recent_pointages():
    """
    Retourne le dernier pointage des 10 dernières secondes
    pour affichage temps réel sur LCD
    """
    try:
        anchor_id = request.args.get("anchor_id")
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
        
        if pointages:
            logger.info(f"📺 Pointage récent trouvé: {pointages[0]['prenom']} {pointages[0]['nom']} - {pointages[0]['type']}")
        else:
            logger.info(f"📺 Aucun pointage récent (< 10s)")
        
        return jsonify({"success": True, "pointages": pointages}), 200
        
    except Exception as e:
        logger.error(f"❌ get_recent_pointages: {e}", exc_info=True)
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
        logger.error(f"❌ get_active_employees: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
# === POST ajouter pointage (✅ CORRIGÉ POUR ANDROID) ===
@app.route("/api/pointages", methods=["POST"])
def add_pointage():
    data = request.get_json(silent=True)
    logger.info(f"📥 Pointage reçu: {data}")
    
    if not data:
        return jsonify({"success": False, "message": "Requête vide"}), 400
    
    # ✅ VALIDATION FLEXIBLE DES CHAMPS
    emp_id = data.get("employeeId")
    pointage_type = data.get("type", "").lower().strip()
    timestamp = data.get("timestamp")
    date = data.get("date")
    
    # ✅ Vérifier les champs requis
    if not emp_id:
        return jsonify({"success": False, "message": "Champ manquant: employeeId"}), 400
    
    if not pointage_type:
        return jsonify({"success": False, "message": "Champ manquant: type"}), 400
    
    if not timestamp or not date:
        return jsonify({"success": False, "message": "Champs manquants: timestamp ou date"}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # ✅ RÉCUPÉRER L'EMPLOYÉ DEPUIS LA BDD
        cur.execute(f"SELECT id, nom, prenom, type FROM employees WHERE id = {PLACEHOLDER}", (emp_id,))
        employee = cur.fetchone()
        
        if not employee:
            cur.close()
            conn.close()
            logger.error(f"❌ Employé {emp_id} non trouvé en base")
            return jsonify({
                "success": False, 
                "message": f"Employé {emp_id} non trouvé. Veuillez synchroniser les employés."
            }), 404
        
        # ✅ CONSTRUIRE LE NOM EXACT : "Nom Prénom"
        emp_nom = employee[1] if DB_DRIVER == "sqlite" else employee['nom']
        emp_prenom = employee[2] if DB_DRIVER == "sqlite" else employee['prenom']
        emp_type = employee[3] if DB_DRIVER == "sqlite" else employee['type']
        employee_name = f"{emp_nom} {emp_prenom}"
        
        # ✅ NORMALISER LE TYPE DE POINTAGE (accepter plusieurs formats)
        pointage_type_normalized = pointage_type.lower()
        
        if pointage_type_normalized in ['entree', 'entrée', 'entry', 'in']:
            pointage_type_normalized = 'arrivee'
        elif pointage_type_normalized in ['sortie', 'exit', 'out']:
            pointage_type_normalized = 'sortie'
        elif pointage_type_normalized not in ['arrivee', 'sortie']:
            cur.close()
            conn.close()
            return jsonify({
                "success": False, 
                "message": f"Type de pointage invalide: '{pointage_type}'. Utilisez 'arrivee' ou 'sortie'."
            }), 400
        
        logger.info(f"✅ Type normalisé: '{pointage_type}' → '{pointage_type_normalized}'")
        
        # ✅ METTRE À JOUR is_active SELON LE TYPE
        new_is_active = 1 if pointage_type_normalized == 'arrivee' else 0
        
        cur.execute(f"""
            UPDATE employees 
            SET is_active = {PLACEHOLDER}, last_seen = {PLACEHOLDER}
            WHERE id = {PLACEHOLDER}
        """, [new_is_active, int(timestamp), emp_id])
        
        # ✅ INSÉRER LE POINTAGE AVEC LE NOM CORRECT
        pointage_id = str(uuid.uuid4())
        cur.execute(f"""
            INSERT INTO pointages (id, employee_id, employee_name, type, timestamp, date)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        """, [
            pointage_id, 
            emp_id, 
            employee_name,           # ✅ Format: "Razafiarinirina Angela"
            pointage_type_normalized, # ✅ Format: "arrivee" ou "sortie"
            int(timestamp), 
            date
        ])
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Pointage enregistré: {employee_name} ({emp_type}) - {pointage_type_normalized} (is_active={new_is_active})")
        
        return jsonify({
            "success": True,
            "message": f"Pointage {pointage_type_normalized} enregistré avec succès",
            "pointageId": pointage_id,
            "employeeName": employee_name,
            "employeeType": emp_type,
            "type": pointage_type_normalized,
            "is_active": new_is_active
        }), 201
        
    except Exception as e:
        logger.error(f"❌ add_pointage: {e}", exc_info=True)
        return jsonify({
            "success": False, 
            "message": f"Erreur serveur: {str(e)}"
        }), 500
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
        logger.error(f"❌ get_pointage_history: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# --- Démarrage ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
