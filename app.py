import os
import logging
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from datetime import datetime
import uuid
import math
from collections import defaultdict

# === Configuration Flask ===
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "3fb5222037e2be9d7d09019e1b46e268ec470fa2974a3981")
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)  # Activer les journaux SocketIO

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

# === POST ajouter salaire ===
@app.route("/api/salary", methods=["POST"])
def add_salary():
    data = request.get_json(silent=True)
    logger.info(f"📥 Données reçues: {data}")

    if not data:
        logger.error("❌ Requête vide")
        return jsonify({"success": False, "message": "Requête vide"}), 400

    # ✅ CORRECTION : Accepter les deux formats (camelCase ET snake_case)
    employee_id = data.get("employeeId") or data.get("employee_id")
    employee_name = data.get("employeeName") or data.get("employee_name")
    amount = data.get("amount")
    record_type = data.get("type")
    hours_worked = data.get("hoursWorked") or data.get("hours_worked", 0.0)

    # Validation des champs requis
    if not employee_name or not isinstance(employee_name, str) or not employee_name.strip():
        logger.error(f"❌ employeeName manquant ou vide: {repr(employee_name)}")
        return jsonify({"success": False, "message": "Champ manquant ou vide: employeeName"}), 400

    if not amount:
        logger.error(f"❌ amount manquant")
        return jsonify({"success": False, "message": "Champ manquant ou vide: amount"}), 400

    if not record_type:
        logger.error(f"❌ type manquant")
        return jsonify({"success": False, "message": "Champ manquant ou vide: type"}), 400

    # Validation du montant
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

        # Nettoyer le nom
        employee_name = employee_name.strip()

        # Si employee_id fourni, vérifier qu'il existe
        if employee_id:
            cur.execute(f"SELECT id, nom, prenom FROM employees WHERE id = {PLACEHOLDER}", (employee_id,))
            employee = cur.fetchone()

            if not employee:
                logger.warning(f"⚠️ Employé {employee_id} non trouvé")
        else:
            # Chercher l'employé par nom
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
                # Créer un nouvel employé si introuvable
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

        # Préparer les données
        salary_date = int(data.get("date", datetime.now().timestamp() * 1000))
        period = data.get("period") or datetime.now().strftime("%Y-%m")
        salary_id = data.get("id") or str(uuid.uuid4())

        # ✅ CORRECTION : Vérifier si l'enregistrement existe déjà
        cur.execute(f"SELECT id FROM salaries WHERE id = {PLACEHOLDER}", (salary_id,))
        existing = cur.fetchone()

        if existing:
            logger.warning(f"⚠️ Salaire {salary_id} existe déjà, mise à jour au lieu d'insertion")
            
            # UPDATE au lieu de INSERT
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
            # INSERT normal
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

        cur.execute(f"DELETE FROM salaries WHERE employee_id = {PLACEHOLDER}", [id])
        cur.execute(f"DELETE FROM employees WHERE id = {PLACEHOLDER}", [id])

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Employé supprimé"}), 200
    except Exception as e:
        logger.error(f"❌ delete_employee: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

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

# 2️⃣ Dans la fonction add_pointage(), après l'enregistrement:

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
        cur.execute(f"SELECT id, nom, prenom FROM employees WHERE id = {PLACEHOLDER}", (emp_id,))
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
        
        # ✅ AJOUTER CES LIGNES ICI ✅
        # Extraire nom et prénom
        if DB_DRIVER == "sqlite":
            nom = employee[1]
            prenom = employee[2]
        else:
            nom = employee['nom']
            prenom = employee['prenom']
        
        # Formater la date et l'heure
        timestamp = int(data.get("timestamp"))
        dt = datetime.fromtimestamp(timestamp / 1000)
        date_formatted = dt.strftime("%d/%m/%y")
        time_formatted = dt.strftime("%H:%M:%S")
        
        # Émettre vers ESP32
        socketio.emit('pointage_event', {
            'nom': nom,
            'prenom': prenom,
            'type': data.get("type"),
            'date': date_formatted,
            'time': time_formatted,
            'timestamp': timestamp
        }, namespace='/api/rssi-data', broadcast=True)
        
        logger.info(f"📡 Événement pointage émis: {prenom} {nom}")
        # ✅ FIN DES LIGNES À AJOUTER ✅
        
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
# === GET historique pointages ===
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
        return jsonify({"success": True, "pointages": pointages}), 200
    except Exception as e:
        logger.error(f"❌ get_pointage_history: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/scan", methods=["POST"])
def scan_qr_code():
    data = request.get_json(silent=True)
    logger.info(f"📸 Scan reçu : {data}")

    if not data or "qr_code" not in data:
        return jsonify({"success": False, "message": "QR code manquant"}), 400

    qr_code = data["qr_code"].strip()
    if not qr_code:
        return jsonify({"success": False, "message": "QR code vide"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(f"SELECT id, nom, prenom, is_active FROM employees WHERE id = {PLACEHOLDER}", (qr_code,))
        employee = cur.fetchone()

        if not employee:
            logger.warning(f"❌ Aucun employé trouvé pour le QR {qr_code}")
            return jsonify({"success": False, "message": "Employé non trouvé"}), 404

        emp_id, nom, prenom, is_active = employee
        now = int(datetime.now().timestamp() * 1000)
        today = datetime.now().strftime("%Y-%m-%d")

        if is_active == 0:
            pointage_type = "ENTREE"
            cur.execute(f"UPDATE employees SET is_active = 1 WHERE id = {PLACEHOLDER}", (emp_id,))
            message = f"{prenom} {nom} est entré."
        else:
            pointage_type = "SORTIE"
            cur.execute(f"UPDATE employees SET is_active = 0 WHERE id = {PLACEHOLDER}", (emp_id,))
            message = f"{prenom} {nom} est sorti."

        pointage_id = str(uuid.uuid4())
        cur.execute(f"""
            INSERT INTO pointages (id, employee_id, employee_name, type, timestamp, date)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        """, [
            pointage_id,
            emp_id,
            f"{prenom} {nom}",
            pointage_type,
            now,
            today
        ])

        conn.commit()
        cur.close()
        conn.close()

        # ✅ AJOUTER CES LIGNES ICI ✅
        # Formater la date et l'heure pour l'affichage LCD
        dt = datetime.fromtimestamp(now / 1000)
        date_formatted = dt.strftime("%d/%m/%y")  # Format: 02/11/25
        time_formatted = dt.strftime("%H:%M:%S")  # Format: 14:30:45
        
        # Émettre l'événement vers tous les ESP32 connectés
        socketio.emit('pointage_event', {
            'nom': nom,
            'prenom': prenom,
            'type': pointage_type,
            'date': date_formatted,
            'time': time_formatted,
            'timestamp': now
        }, namespace='/api/rssi-data', broadcast=True)
        
        logger.info(f"📡 Événement pointage émis vers ESP32: {prenom} {nom} - {pointage_type}")
        # ✅ FIN DES LIGNES À AJOUTER ✅

        logger.info(f"✅ {pointage_type} enregistré pour {prenom} {nom}")
        return jsonify({
            "success": True,
            "action": pointage_type,
            "message": message,
            "employeeId": emp_id,
            "timestamp": now,
            "date": today
        }), 200

    except Exception as e:
        logger.error(f"❌ scan_qr_code: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# === WebSocket pour RSSI ===
@socketio.on('connect', namespace='/api/rssi-data')
def handle_rssi_connect():
    logger.info("📡 Client WebSocket connecté à /api/rssi-data")

@socketio.on('disconnect', namespace='/api/rssi-data')
def handle_rssi_disconnect():
    logger.info("📡 Client WebSocket déconnecté de /api/rssi-data")

# 👇 Correction ici : on écoute 'rssi_data' (et non 'message')
@socketio.on('rssi_data', namespace='/api/rssi-data')
def handle_rssi_data(data):
    logger.info(f"📡 RSSI reçu via WebSocket: {data}")

    try:
        anchor_id = data.get("anchor_id")
        anchor_x = data.get("anchor_x")
        anchor_y = data.get("anchor_y")
        badges = data.get("badges", [])

        logger.info(f"📡 Ancre #{anchor_id} à ({anchor_x}, {anchor_y}) : {len(badges)} badges")

        conn = get_db()
        cur = conn.cursor()

        for badge in badges:
            ssid = badge.get("ssid")
            mac = badge.get("mac")
            rssi = badge.get("rssi")

            if not ssid or ssid == "None" or not isinstance(ssid, str) or ssid.strip() == "":
                logger.warning(f"❌ SSID invalide: {repr(ssid)}")
                continue

            employee_name = ssid.strip()

            cur.execute(f"""
                SELECT id, nom, prenom FROM employees 
                WHERE CONCAT(nom, ' ', prenom) = {PLACEHOLDER}
                LIMIT 1
            """, (employee_name,))

            employee = cur.fetchone()
            if not employee:
                logger.warning(f"⚠️ Employé '{employee_name}' non trouvé")
                continue

            employee_id = employee[0] if DB_DRIVER == "sqlite" else employee['id']
            logger.info(f"✅ Employé trouvé: {employee_id}")

            cur.execute(f"""
                INSERT INTO rssi_measurements (employee_id, anchor_id, anchor_x, anchor_y, rssi, mac, timestamp)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
            """, [
                employee_id, anchor_id, anchor_x, anchor_y, rssi, mac,
                int(datetime.now().timestamp() * 1000)
            ])

        conn.commit()
        calculate_and_broadcast_positions(cur)
        conn.commit()

        cur.close()
        conn.close()

        # ✅ Réponse positive à l’ESP32
        emit('ack', {'success': True, 'message': f'{len(badges)} mesures traitées'}, namespace='/api/rssi-data')

    except Exception as e:
        logger.error(f"❌ Erreur WebSocket RSSI: {e}", exc_info=True)
        emit('error', {'success': False, 'message': str(e)}, namespace='/api/rssi-data')

# === Calcul et diffusion des positions ===
def calculate_and_broadcast_positions(cursor):
    threshold = int((datetime.now().timestamp() - 5) * 1000)

    cursor.execute(f"""
        SELECT employee_id, anchor_id, anchor_x, anchor_y, rssi
        FROM rssi_measurements
        WHERE timestamp > {PLACEHOLDER}
    """, (threshold,))

    measurements = cursor.fetchall()

    if not measurements:
        logger.info("Aucune mesure récente pour triangulation")
        return

    employee_data = defaultdict(list)
    for row in measurements:
        emp_id = row[0] if DB_DRIVER == "sqlite" else row['employee_id']
        anchor_id = row[1] if DB_DRIVER == "sqlite" else row['anchor_id']
        anchor_x = row[2] if DB_DRIVER == "sqlite" else row['anchor_x']
        anchor_y = row[3] if DB_DRIVER == "sqlite" else row['anchor_y']
        rssi = row[4] if DB_DRIVER == "sqlite" else row['rssi']

        distance = rssi_to_distance(rssi)
        employee_data[emp_id].append({
            'anchor_id': anchor_id,
            'x': anchor_x,
            'y': anchor_y,
            'distance': distance
        })

    for emp_id, anchors in employee_data.items():
        if len(anchors) >= 3:
            pos_x, pos_y = trilateration(anchors)

            cursor.execute(f"""
                UPDATE employees
                SET last_position_x = {PLACEHOLDER}, last_position_y = {PLACEHOLDER}, last_seen = {PLACEHOLDER}
                WHERE id = {PLACEHOLDER}
            """, [pos_x, pos_y, int(datetime.now().timestamp() * 1000), emp_id])

            logger.info(f"Position calculée pour {emp_id}: ({pos_x:.2f}, {pos_y:.2f})")

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

    logger.info(f"📤 Diffusion positions à {len(employees)} employés actifs")
    for emp in employees:
        if emp.get('last_position_x') is not None:
            logger.info(f"  {emp['prenom']} {emp['nom']}: ({emp['last_position_x']:.2f}, {emp['last_position_y']:.2f})")

    socketio.emit('positions', {'success': True, 'employees': employees}, namespace='/api/employees/active')

def rssi_to_distance(rssi, tx_power=-59, n=2.0):
    """Convertit un RSSI en distance estimée (mètres)."""
    if rssi == 0:
        return -1.0
    ratio = (tx_power - rssi) / (10 * n)
    return round(math.pow(10, ratio), 2)


def trilateration(anchors):
    """Calcule la position (x, y) à partir de 3 ancres RSSI."""
    anchors = sorted(anchors, key=lambda x: x['distance'])[:3]
    logger.info("📡 Ancres utilisées pour la triangulation :")
    for i, a in enumerate(anchors):
        logger.info(f"  {i+1}. Ancre #{a['anchor_id']} ({a['x']}, {a['y']}) d={a['distance']:.2f}m")

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
    if denom == 0:
        logger.warning("⚠️ Triangulation impossible (points alignés)")
        return (x1, y1)

    x = (C*E - B*F) / denom
    y = (A*F - C*D) / denom
    return round(x, 2), round(y, 2)
# === GET employés actifs ===
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
        logger.info(f"📤 {len(employees)} employés actifs renvoyés")
        for emp in employees:
            if emp.get('last_position_x') is not None:
                logger.info(f"  {emp['prenom']} {emp['nom']}: ({emp['last_position_x']:.2f}, {emp['last_position_y']:.2f})")
        
        return jsonify({"success": True, "employees": employees}), 200
    except Exception as e:
        logger.error(f"❌ get_active_employees: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# === POST activer via QR ===
@app.route("/api/activate-qr", methods=["POST"])
def activate_via_qr():
    data = request.get_json(silent=True) or request.form
    if not data:
        return jsonify({"success": False, "message": "Données manquantes"}), 400

    emp_id = data.get("employee_id")
    badge_id = data.get("badge_id")
    identifier = emp_id or badge_id
    if not identifier:
        return jsonify({"success": False, "message": "employee_id ou badge_id requis"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute(f"UPDATE employees SET is_active = {PLACEHOLDER}, last_seen = {PLACEHOLDER} WHERE id = {PLACEHOLDER}",
                        [1, int(datetime.now().timestamp() * 1000), identifier])
        except Exception as e:
            logger.warning(f"🔁 update is_active failed: {e}, trying 'active' column")
            cur.execute(f"UPDATE employees SET active = {PLACEHOLDER}, last_seen = {PLACEHOLDER} WHERE id = {PLACEHOLDER}",
                        [1, int(datetime.now().timestamp() * 1000), identifier])

        if cur.rowcount == 0:
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

# === Route temporaire pour déboguer les requêtes HTTP erronées ===
@app.route("/api/rssi-data", methods=["GET", "POST"])
def receive_rssi_data_http():
    logger.warning("⚠️ Requête HTTP reçue sur /api/rssi-data (WebSocket attendu)")
    return jsonify({"success": False, "message": "Utilisez WebSocket (wss://) pour /api/rssi-data"}), 400

# --- Démarrage ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))  # Port 8000 pour Koyeb
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)  # allow_unsafe pour SocketIO
