import os
import logging
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime
import uuid
from flask_socketio import SocketIO, emit
import psycopg2  # For explicit Neon PostgreSQL error handling

# === Configuration Flask ===
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "3fb5222037e2be9d7d09019e1b46e268ec470fa2974a3981")
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=True,
    engineio_logger=True,
    ping_timeout=120,
    ping_interval=30
)

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

# === Placeholder SQL (Postgres = %s) ===
PLACEHOLDER = "%s"  # Neon uses PostgreSQL, so always %s

# --- Initialisation DB ---
try:
    init_db()
    verify_schema()
    logger.info("✅ Base initialisée et schéma vérifié")
except Exception as e:
    logger.error(f"❌ Échec init_db/verify_schema : {e}")
    raise

# === WebSocket Events ===
@socketio.on('connect')
def handle_connect():
    logger.info(f"✅ Client connecté: {request.sid}")
    emit('connection_response', {'status': 'connected', 'sid': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"❌ Client déconnecté: {request.sid}")

@socketio.on('pointageUpdate')
def handle_pointage_update(data):
    logger.info(f"📥 Événement pointageUpdate reçu: {data}")
    try:
        required_fields = ["id", "employeeId", "employeeName", "type", "timestamp", "date"]
        for field in required_fields:
            if field not in data or not data[field]:
                logger.error(f"❌ Champ manquant ou vide dans pointageUpdate: {field}")
                return

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(f"""
                INSERT INTO pointages (id, employee_id, employee_name, type, timestamp, date)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
            """, [
                data["id"],
                data["employeeId"],
                data["employeeName"],
                data["type"],
                int(data["timestamp"]),
                data["date"]
            ])
            conn.commit()
            logger.info(f"✅ Pointage inséré: ID={data['id']}")
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Erreur insertion pointage: {e}")
            raise
        finally:
            cur.close()
            conn.close()

        socketio.emit('pointageUpdate', data, broadcast=True)
        logger.info(f"📡 Événement pointageUpdate émis: {data}")
    except Exception as e:
        logger.error(f"❌ Erreur traitement pointageUpdate: {e}")

@socketio.on('salaryUpdate')
def handle_salary_update(data):
    logger.info(f"📥 Événement salaryUpdate reçu: {data}")
    try:
        if "salaries" not in data or not isinstance(data["salaries"], list):
            logger.error("❌ Données salaryUpdate invalides: 'salaries' doit être une liste")
            return

        conn = get_db()
        cur = conn.cursor()
        try:
            for salary in data["salaries"]:
                required_fields = ["id", "employee_id", "employee_name", "amount", "type", "period", "date"]
                for field in required_fields:
                    if field not in salary or salary[field] is None:
                        logger.error(f"❌ Champ manquant ou vide dans salaryUpdate: {field}")
                        continue

                cur.execute(f"""
                    INSERT INTO salaries (id, employee_id, employee_name, amount, hours_worked, type, period, date)
                    VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
                """, [
                    salary["id"],
                    salary["employee_id"],
                    salary["employee_name"],
                    float(salary["amount"]),
                    salary.get("hours_worked", 0.0),
                    salary["type"],
                    salary["period"],
                    int(salary["date"])
                ])
            conn.commit()
            logger.info(f"✅ {len(data['salaries'])} salaires insérés")
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Erreur insertion salaire: {e}")
            raise
        finally:
            cur.close()
            conn.close()

        socketio.emit('salaryUpdate', data, broadcast=True)
        logger.info(f"📡 Événement salaryUpdate émis: {data}")
    except Exception as e:
        logger.error(f"❌ Erreur traitement salaryUpdate: {e}")

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

        employees = [dict(row) for row in rows]  # Simplified for PostgreSQL
        conn.close()
        logger.info(f"📤 {len(employees)} employés renvoyés")
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
        logger.info(f"✅ Employé ajouté: ID={new_id}")
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
    logger.info(f"📥 Données salaire reçues: {data}")

    if not data:
        logger.error("❌ Requête vide")
        return jsonify({"success": False, "message": "Requête vide"}), 400

    required_fields = ["employeeId", "employeeName", "amount", "type"]
    for field in required_fields:
        if field not in data or data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
            logger.error(f"❌ Champ manquant ou vide: {field}")
            return jsonify({"success": False, "message": f"Champ manquant ou vide: {field}"}), 400

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

        cur.execute(f"SELECT id, nom, prenom FROM employees WHERE id = {PLACEHOLDER}", (emp_id,))
        employee = cur.fetchone()

        if not employee:
            logger.warning(f"⚠️ Employé {emp_id} non trouvé, création automatique")
            emp_name_parts = emp_name.split(" ")
            nom = emp_name_parts[-1] if len(emp_name_parts) > 1 else emp_name
            prenom = emp_name_parts[0] if len(emp_name_parts) > 1 else "Inconnu"
            new_id = emp_id

            cur.execute(f"""
                INSERT INTO employees (id, nom, prenom, type, is_active, created_at)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
            """, [new_id, nom, prenom, data.get("type", "inconnu"), 1, int(datetime.now().timestamp() * 1000)])
            conn.commit()
            final_emp_id = new_id
            logger.info(f"✅ Employé créé avec ID: {final_emp_id}")
        else:
            final_emp_id = employee["id"]
            logger.info(f"✅ Employé trouvé: {employee['nom']} {employee['prenom']}, ID: {final_emp_id}")

        salary_date = int(data.get("date", datetime.now().timestamp() * 1000))
        period = data.get("period") or datetime.now().strftime("%Y-%m")
        salary_id = str(uuid.uuid4())

        cur.execute(f"""
            INSERT INTO salaries (id, employee_id, employee_name, amount, hours_worked, type, period, date)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        """, [
            salary_id,
            final_emp_id,
            emp_name,
            amount,
            data.get("hoursWorked", 0.0),
            data["type"],
            period,
            salary_date
        ])

        conn.commit()
        logger.info(f"✅ Salaire inséré: ID={salary_id}, employee_id={final_emp_id}, amount={amount}")

        salary_data = {
            "salaries": [{
                "id": salary_id,
                "employee_id": final_emp_id,
                "employee_name": emp_name,
                "amount": amount,
                "hours_worked": data.get("hoursWorked", 0.0),
                "type": data["type"],
                "period": period,
                "date": salary_date
            }]
        }
        socketio.emit("salaryUpdate", salary_data, broadcast=True)
        logger.info(f"📡 Événement salaryUpdate émis pour salaire ID={salary_id}: {salary_data}")

        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Salaire enregistré", "employeeId": final_emp_id}), 201
    except Exception as e:
        logger.error(f"❌ add_salary: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
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
        logger.info(f"✅ Employé modifié: ID={id}")
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
        logger.info(f"✅ Employé supprimé: ID={id}")
        return jsonify({"success": True, "message": "Employé supprimé"}), 200
    except Exception as e:
        logger.error(f"❌ delete_employee: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# === GET historique des salaires ===
@app.route("/api/salary/history", methods=["GET"])
def get_salary_history():
    try:
        conn = get_db()
        cur = conn.cursor()

        # Relaxed filtering for debugging
        cur.execute(f"""
            SELECT s.id, s.employee_id, s.employee_name, s.amount, s.hours_worked, 
                   s.type, s.period, s.date,
                   e.email, e.telephone, e.taux_horaire, e.frais_ecolage,
                   e.date_naissance, e.lieu_naissance
            FROM salaries s
            LEFT JOIN employees e ON e.id = s.employee_id
            ORDER BY s.date DESC
        """)
        rows = cur.fetchall()

        salaries = [dict(row) for row in rows]  # Simplified for PostgreSQL
        logger.info(f"=== RÉCUPÉRATION HISTORIQUE SALAIRES ===")
        logger.info(f"Nombre total de records: {len(salaries)}")

        valid_count = 0
        invalid_count = 0

        for record in salaries:
            if (record.get("employee_id") and 
                record.get("employee_name") and 
                record.get("employee_name").strip() and
                record.get("amount", 0) > 0):
                valid_count += 1
                logger.info(f"✅ Record valide: ID={record['id']}, " +
                           f"employee_id={record['employee_id']}, " +
                           f"employee_name={record['employee_name']}, " +
                           f"type={record['type']}, " +
                           f"amount={record['amount']}")
            else:
                invalid_count += 1
                logger.warning(f"⚠️ Record invalide: {record}")

        logger.info(f"Résumé: {valid_count} valides, {invalid_count} invalides")

        cur.close()
        conn.close()
        return jsonify({"success": True, "salaries": salaries}), 200
    except Exception as e:
        logger.error(f"❌ get_salary_history: {e}", exc_info=True)
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

        payments = [dict(row) for row in rows]  # Simplified for PostgreSQL
        logger.info(f"📤 {len(payments)} paiements renvoyés au dashboard")
        conn.close()
        return render_template("dashboard.html", payments=payments)
    except Exception as e:
        logger.error(f"❌ dashboard: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# === POST pointages ===
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
        logger.info(f"✅ Pointage inséré: ID={pointage_id}")

        pointage_data = {
            "id": pointage_id,
            "employeeId": data.get("employeeId"),
            "employeeName": data.get("employeeName"),
            "type": data.get("type"),
            "timestamp": int(data.get("timestamp")),
            "date": data.get("date")
        }
        socketio.emit("pointageUpdate", pointage_data, broadcast=True)
        logger.info(f"📡 Événement pointageUpdate émis pour pointage ID={pointage_id}: {pointage_data}")

        cur.close()
        conn.close()
        return jsonify({
            "success": True,
            "message": "Pointage enregistré",
            "pointageId": pointage_id
        }), 201
    except Exception as e:
        logger.error(f"❌ add_pointage: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({"success": False, "message": str(e)}), 500

# === GET historique des pointages ===
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

        pointages = [dict(row) for row in rows]  # Simplified for PostgreSQL
        logger.info(f"📤 {len(pointages)} pointages renvoyés")
        cur.close()
        conn.close()
        return jsonify({"success": True, "pointages": pointages}), 200
    except Exception as e:
        logger.error(f"❌ get_pointage_history: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# === Route PIR ===
@app.route("/api/motion", methods=["GET"])
def motion_detected():
    logger.info("⚡ Mouvement détecté par ESP32 (PIR)")
    try:
        socketio.emit("motionDetected", {"motion": True, "timestamp": int(datetime.now().timestamp() * 1000)}, broadcast=True)
        logger.info("📡 Événement motionDetected émis")
        return jsonify({"success": True, "message": "Motion detected"}), 200
    except Exception as e:
        logger.error(f"❌ Erreur motion_detected: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# === GET employés actifs ===
@app.route("/api/employees/active", methods=["GET"])
def get_active_employees():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM employees WHERE is_active = 1 ORDER BY nom, prenom")
        rows = cursor.fetchall()

        employees = [dict(row) for row in rows]  # Simplified for PostgreSQL
        logger.info(f"📤 {len(employees)} employés actifs renvoyés")
        conn.close()
        return jsonify({"success": True, "employees": employees})
    except Exception as e:
        logger.error(f"❌ get_active_employees: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# --- Démarrage ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
