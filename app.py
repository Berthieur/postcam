import os
import logging
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime
import uuid

# === Configuration Flask ===
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "3fb5222037e2be9d7d09019e1b46e268ec470fa2974a3981")
CORS(app, resources={r"/api/*": {"origins": "*"}})

# === Logger ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === DB imports ===
try:
    from database import init_db, get_db, verify_schema, DB_DRIVER
    logger.info("✅ database.py importé")
except Exception as e:
    logger.error(f"❌ Échec import database.py : {e}")
    raise

# === Placeholder SQL (Postgres = %s, SQLite = ?) ===
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

# === POST ajouter salaire (CORRIGÉ) ===
@app.route("/api/salary", methods=["POST"])
def add_salary():
    data = request.get_json(silent=True)
    logger.info(f"📥 Données reçues: {data}")

    if not data:
        logger.error("❌ Requête vide")
        return jsonify({"success": False, "message": "Requête vide"}), 400

    # Validation des champs requis
    required_fields = ["employeeId", "employeeName", "amount", "type"]
    for field in required_fields:
        if field not in data or data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
            logger.error(f"❌ Champ manquant ou vide: {field}")
            return jsonify({"success": False, "message": f"Champ manquant ou vide: {field}"}), 400

    # Validation spécifique pour amount
    try:
        amount = float(data["amount"])
        if amount <= 0:
            logger.error(f"❌ Montant invalide: {amount}")
            return jsonify({"success": False, "message": "Le montant doit être supérieur à 0"}), 400
    except (ValueError, TypeError):
        logger.error(f"❌ Montant non numérique: {data.get('amount')}")
        return jsonify({"success": False, "message": "Le montant doit être un nombre valide"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        emp_id = data["employeeId"]
        emp_name = data["employeeName"].strip()

        # Vérifier si l’employé existe
        cur.execute(f"SELECT id, nom, prenom FROM employees WHERE id = {PLACEHOLDER}", (emp_id,))
        employee = cur.fetchone()

        if not employee:
            logger.warning(f"⚠️ Employé {emp_id} non trouvé, création automatique")
            emp_name_parts = emp_name.split(" ")
            nom = emp_name_parts[-1] if len(emp_name_parts) > 1 else emp_name
            prenom = emp_name_parts[0] if len(emp_name_parts) > 1 else "Inconnu"
            new_id = emp_id or str(uuid.uuid4())

            cur.execute(f"""
                INSERT INTO employees (id, nom, prenom, type, is_active, created_at)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
            """, [new_id, nom, prenom, data.get("type", "inconnu"), 1, int(datetime.now().timestamp() * 1000)])

            emp_id = new_id
        else:
            logger.info(f"✅ Employé trouvé: {employee['nom']} {employee['prenom']}")

        salary_date = int(data.get("date", datetime.now().timestamp() * 1000))
        period = data.get("period") or datetime.now().strftime("%Y-%m")

        cur.execute(f"""
            INSERT INTO salaries (id, employee_id, employee_name, amount, hours_worked, type, period, date)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        """, [
            str(uuid.uuid4()), emp_id, emp_name, amount, data.get("hoursWorked", 0.0),
            data["type"], period, salary_date
        ])

        conn.commit()
        logger.info(f"✅ Salaire enregistré: employee_id={emp_id}, amount={amount}, type={data['type']}")

        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Salaire enregistré", "employeeId": emp_id}), 201

    except Exception as e:
        logger.error(f"❌ add_salary: {e}")
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

        # Supprimer d'abord les salaires liés (clé étrangère)
        cur.execute(f"DELETE FROM salaries WHERE employee_id = {PLACEHOLDER}", [id])

        # Supprimer l’employé
        cur.execute(f"DELETE FROM employees WHERE id = {PLACEHOLDER}", [id])

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Employé supprimé"}), 200
    except Exception as e:
        logger.error(f"❌ delete_employee: {e}")
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

        # Assurer que les valeurs nulles sont converties correctement
        for record in salaries:
            if record.get("hours_worked") is None:
                record["hours_worked"] = 0.0
            if record.get("period") is None:
                record["period"] = ""

        cur.close()
        conn.close()
        logger.info(f"📤 Historique salaires renvoyé: {len(salaries)} enregistrements valides")
        return jsonify({"success": True, "salaries": salaries}), 200

    except Exception as e:
        logger.error(f"❌ get_salary_history: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

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

@app.route("/api/pointages", methods=["POST"])
def add_pointage():
    data = request.get_json(silent=True)
    logger.info(f"📥 Données pointage reçues: {data}")

    if not data:
        return jsonify({"success": False, "message": "Requête vide"}), 400

    required = ["employeeId", "employeeName", "type", "timestamp", "date"]
    for field in required:
        if field not in data or not data[field]:
            return jsonify({"success": False, "message": f"Champ manquant ou vide: {field}"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        emp_id = data.get("employeeId")
        cur.execute(f"SELECT id FROM employees WHERE id = {PLACEHOLDER}", (emp_id,))
        employee = cur.fetchone()

        if not employee:
            return jsonify({"success": False, "message": f"Employé avec ID {emp_id} non trouvé"}), 404

        pointage_id = str(uuid.uuid4())
        cur.execute(f"""
            INSERT INTO pointages (id, employee_id, employee_name, type, timestamp, date)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        """, [
            pointage_id,
            data.get("employeeId"),
            data.get("employeeName"),
            data.get("type"),
            int(data.get("timestamp")),
            data.get("date")
        ])

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Pointage enregistré",
            "pointageId": pointage_id
        }), 201
    except Exception as e:
        logger.error(f"❌ add_pointage: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/pointages/history", methods=["GET"])
def get_pointage_history():
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(f"""
            SELECT p.id, p.employee_id, p.employee_name, p.type, p.timestamp, p.date,
                   e.email, e.telephone, e.taux_horaire, e.frais_ecolage,
                   e.date_naissance, e.lieu_naissance
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
        # ✅ cohérent avec Android → renvoyer "pointages"
        return jsonify({"success": True, "pointages": pointages}), 200
    except Exception as e:
        logger.error(f"❌ get_pointage_history: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
@app.route("/api/rssi-data", methods=["POST"])
def receive_rssi_data():
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({"success": False, "message": "Données manquantes"}), 400
    
    anchor_id = data.get("anchor_id")
    anchor_x = data.get("anchor_x")
    anchor_y = data.get("anchor_y")
    badges = data.get("badges", [])
    
    logger.info(f"📡 RSSI ancre #{anchor_id} à ({anchor_x}, {anchor_y}) : {len(badges)} badges")
    logger.info(f"   JSON reçu: {data}")  # DEBUG: voir le JSON complet
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        for badge in badges:
            ssid = badge.get("ssid")
            mac = badge.get("mac")
            rssi = badge.get("rssi")
            
            logger.info(f"   Badge: ssid='{ssid}', mac={mac}, rssi={rssi}")  # DEBUG
            
            if not ssid or ssid == "None" or not isinstance(ssid, str) or ssid.strip() == "":
                logger.warning(f"❌ SSID invalide: {repr(ssid)}")
                continue

            employee_name = ssid.replace("BADGE_", "").strip()
            
            # Recherche par nom complet
            cur.execute(f"""
                SELECT id, nom, prenom FROM employees 
                WHERE CONCAT(nom, ' ', prenom) = {PLACEHOLDER}
                   OR nom = {PLACEHOLDER}
                   OR prenom = {PLACEHOLDER}
                LIMIT 1
            """, (employee_name, employee_name, employee_name))
            
            employee = cur.fetchone()
            if not employee:
                logger.warning(f"⚠️ Employé '{employee_name}' non trouvé dans la BD")
                continue
            
            employee_id = employee[0] if DB_DRIVER == "sqlite" else employee['id']
            logger.info(f"✅ Employé trouvé: {employee_id}")
            
            # Enregistrer RSSI
            cur.execute(f"""
                INSERT INTO rssi_measurements (employee_id, anchor_id, anchor_x, anchor_y, rssi, mac, timestamp)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
            """, [
                employee_id, anchor_id, anchor_x, anchor_y, rssi, mac,
                int(datetime.now().timestamp() * 1000)
            ])
        
        conn.commit()
        calculate_positions(cur)
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({"success": True, "message": f"{len(badges)} mesures traitées"}), 201
        
    except Exception as e:
        logger.error(f"❌ Erreur RSSI: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500
def calculate_positions(cursor):
    """Calcule la position des employés par triangulation"""
    import math
    
    # Récupérer les mesures récentes (moins de 5 secondes)
    threshold = int((datetime.now().timestamp() - 5) * 1000)
    
    cursor.execute(f"""
        SELECT employee_id, anchor_id, anchor_x, anchor_y, rssi
        FROM rssi_measurements
        WHERE timestamp > {PLACEHOLDER}
    """, (threshold,))
    
    measurements = cursor.fetchall()
    
    if not measurements:
        return
    
    # Grouper par employee_id
    from collections import defaultdict
    employee_data = defaultdict(list)
    
    for row in measurements:
        emp_id = row[0] if DB_DRIVER == "sqlite" else row['employee_id']
        anchor_id = row[1] if DB_DRIVER == "sqlite" else row['anchor_id']
        anchor_x = row[2] if DB_DRIVER == "sqlite" else row['anchor_x']
        anchor_y = row[3] if DB_DRIVER == "sqlite" else row['anchor_y']
        rssi = row[4] if DB_DRIVER == "sqlite" else row['rssi']
        
        # Convertir RSSI en distance (formule simplifiée)
        distance = rssi_to_distance(rssi)
        
        employee_data[emp_id].append({
            'anchor_id': anchor_id,
            'x': anchor_x,
            'y': anchor_y,
            'distance': distance
        })
    
    # Triangulation pour chaque employé
    for emp_id, anchors in employee_data.items():
        if len(anchors) >= 3:
            pos_x, pos_y = trilateration(anchors)
            
            # Mettre à jour la position dans la BD
            cursor.execute(f"""
                UPDATE employees
                SET last_position_x = {PLACEHOLDER}, last_position_y = {PLACEHOLDER}, last_seen = {PLACEHOLDER}
                WHERE id = {PLACEHOLDER}
            """, [pos_x, pos_y, int(datetime.now().timestamp() * 1000), emp_id])
            
            logger.info(f"Position calculée pour {emp_id}: ({pos_x:.2f}, {pos_y:.2f})")


def rssi_to_distance(rssi, tx_power=-59, n=2.0):
    """Convertit RSSI en distance (mètres)
    tx_power: puissance à 1m (calibration requise)
    n: facteur d'atténuation (2.0 pour espace libre, 3-4 pour intérieur)
    """
    import math
    if rssi == 0:
        return -1.0
    
    ratio = (tx_power - rssi) / (10 * n)
    return math.pow(10, ratio)


def trilateration(anchors):
    """Triangulation basique à 3 points SANS NumPy"""
    import math
    
    # Prendre les 3 meilleures ancres
    anchors = sorted(anchors, key=lambda x: x['distance'])[:3]
    
    logger.info(f"  Ancres utilisées pour triangulation :")
    for i, a in enumerate(anchors):
        logger.info(f"    {i+1}. Ancre #{a['anchor_id']} à ({a['x']}, {a['y']}) distance={a['distance']:.2f}m")
    
    x1, y1, r1 = anchors[0]['x'], anchors[0]['y'], anchors[0]['distance']
    x2, y2, r2 = anchors[1]['x'], anchors[1]['y'], anchors[1]['distance']
    x3, y3, r3 = anchors[2]['x'], anchors[2]['y'], anchors[2]['distance']
    
    # Système d'équations linéaires
    A = 2*x2 - 2*x1
    B = 2*y2 - 2*y1
    C = r1**2 - r2**2 - x1**2 + x2**2 - y1**2 + y2**2
    D = 2*x3 - 2*x2
    E = 2*y3 - 2*y2
    F = r2**2 - r3**2 - x2**2 + x3**2 - y2**2 + y3**2
    
    try:
        denom1 = (E*A - B*D)
        denom2 = (B*D - A*E)
        
        if abs(denom1) < 0.0001 or abs(denom2) < 0.0001:
            raise ZeroDivisionError("Dénominateur proche de zéro")
        
        x = (C*E - F*B) / denom1
        y = (C*D - A*F) / denom2
        
        logger.info(f"  ✅ Triangulation réussie : x={x:.2f}, y={y:.2f}")
        return (x, y)
    except Exception as e:
        logger.warning(f"  ⚠️ Erreur triangulation : {e}. Utilisation du centroïde")
        # Fallback: centroïde pondéré (plus proche = plus de poids)
        total_weight = sum(1.0 / max(a['distance'], 0.1) for a in anchors)
        x = sum(a['x'] / max(a['distance'], 0.1) for a in anchors) / total_weight
        y = sum(a['y'] / max(a['distance'], 0.1) for a in anchors) / total_weight
        logger.info(f"  Centroïde pondéré : x={x:.2f}, y={y:.2f}")
        return (x, y)
@app.route("/api/employees/active", methods=["GET"])
def get_active_employees():
    """Récupère les employés actifs avec leurs positions en temps réel"""
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
        logger.info(f"📤 {len(employees)} employés actifs renvoyés (avec positions)")
        
        # Log des positions pour debug
        for emp in employees:
            if emp.get('last_position_x') is not None:
                logger.info(f"  {emp['prenom']} {emp['nom']}: ({emp['last_position_x']:.2f}, {emp['last_position_y']:.2f})")
        
        return jsonify({"success": True, "employees": employees}), 200
    except Exception as e:
        logger.error(f"❌ get_active_employees: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/activate-qr", methods=["POST"])
def activate_via_qr():
    data = request.get_json(silent=True) or request.form
    if not data:
        return jsonify({"success": False, "message": "Données manquantes"}), 400

    emp_id = data.get("employee_id")    # préférable : l'uuid
    badge_id = data.get("badge_id")     # optionnel : id du badge / numéro
    identifier = emp_id or badge_id
    if not identifier:
        return jsonify({"success": False, "message": "employee_id ou badge_id requis"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        # Première tentative : mettre is_active = 1 (utilisé dans ton code)
        try:
            cur.execute(f"UPDATE employees SET is_active = {PLACEHOLDER}, last_seen = {PLACEHOLDER} WHERE id = {PLACEHOLDER}",
                        [1, int(datetime.now().timestamp() * 1000), identifier])
            if cur.rowcount == 0:
                # peut-être la table utilise 'active' ou le QR contient un badge_id au lieu de id
                cur.execute(f"UPDATE employees SET active = {PLACEHOLDER}, last_seen = {PLACEHOLDER} WHERE id = {PLACEHOLDER}",
                            [1, int(datetime.now().timestamp() * 1000), identifier])
        except Exception as e:
            # si erreur (colonne inconnue), essayer la colonne 'active'
            logger.warning(f"🔁 update is_active failed: {e}, trying 'active' column")
            cur.execute(f"UPDATE employees SET active = {PLACEHOLDER}, last_seen = {PLACEHOLDER} WHERE id = {PLACEHOLDER}",
                        [1, int(datetime.now().timestamp() * 1000), identifier])

        # Si aucune ligne modifiée, peut-être le QR est un badge_id (badge_code). Chercher employee par badge.
        if cur.rowcount == 0:
            # adapter le nom de la table/colonne badge selon ton schéma : ici j'essaie rssi_data / badges
            cur.execute(f"SELECT employee_id FROM rssi_data WHERE badge_id = {PLACEHOLDER} LIMIT 1", [identifier])
            row = cur.fetchone()
            if row:
                emp_id_from_badge = row[0] if DB_DRIVER == "sqlite" else row['employee_id']
                cur.execute(f"UPDATE employees SET is_active = {PLACEHOLDER}, last_seen = {PLACEHOLDER} WHERE id = {PLACEHOLDER}",
                            [1, int(datetime.now().timestamp() * 1000), emp_id_from_badge])

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Employé activé"}), 200

    except Exception as e:
        logger.error(f"❌ activate_via_qr: {e}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500

# --- Démarrage ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)

