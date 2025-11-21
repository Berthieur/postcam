import os
import sqlite3
import psycopg2
import logging
from psycopg2.extras import RealDictCursor

# --- Logger ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL fournie automatiquement par Render pour Postgres
DATABASE_URL = os.getenv("DATABASE_URL")

# Driver courant : "postgres" si DATABASE_URL défini, sinon "sqlite"
DB_DRIVER = "postgres" if DATABASE_URL else "sqlite"


def get_db():
    """Retourne une connexion DB (Postgres si DATABASE_URL, sinon SQLite)."""
    if DB_DRIVER == "postgres":
        try:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            return conn
        except Exception as e:
            logger.error(f"❌ Connexion PostgreSQL échouée : {e}")
            raise
    else:
        conn = sqlite3.connect("tracking.db")
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    """Crée les tables nécessaires si elles n'existent pas."""
    if DB_DRIVER == "postgres":
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()

            # Table employees
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    id TEXT PRIMARY KEY,
                    nom TEXT NOT NULL,
                    prenom TEXT NOT NULL,
                    type TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at BIGINT,
                    email TEXT,
                    telephone TEXT,
                    taux_horaire REAL,
                    frais_ecolage REAL,
                    profession TEXT,
                    date_naissance TEXT,
                    lieu_naissance TEXT,
                    last_position_x REAL,
                    last_position_y REAL,
                    last_seen BIGINT
                )
            """)

            # Table salaries avec CASCADE
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS salaries (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT REFERENCES employees(id) ON DELETE CASCADE,
                    employee_name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    hours_worked REAL,
                    period TEXT NOT NULL,
                    date BIGINT NOT NULL,
                    is_synced INTEGER DEFAULT 0
                )
            """)

            # Table pointages avec CASCADE
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pointages (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT REFERENCES employees(id) ON DELETE CASCADE,
                    employee_name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    timestamp BIGINT NOT NULL,
                    date TEXT NOT NULL,
                    is_synced INTEGER DEFAULT 0
                )
            """)

            # Table rssi_measurements avec CASCADE
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rssi_measurements (
                    id SERIAL PRIMARY KEY,
                    employee_id TEXT REFERENCES employees(id) ON DELETE CASCADE,
                    anchor_id INTEGER NOT NULL,
                    anchor_x REAL NOT NULL,
                    anchor_y REAL NOT NULL,
                    rssi INTEGER NOT NULL,
                    mac TEXT,
                    timestamp BIGINT NOT NULL
                )
            """)

            conn.commit()
            logger.info("✅ Tables PostgreSQL initialisées avec CASCADE")
        except Exception as e:
            logger.error(f"❌ init_db PostgreSQL : {e}")
            raise
        finally:
            if conn:
                conn.close()
    else:
        try:
            with sqlite3.connect("tracking.db") as conn:
                cursor = conn.cursor()

                # Table employees
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS employees (
                        id TEXT PRIMARY KEY,
                        nom TEXT NOT NULL,
                        prenom TEXT NOT NULL,
                        type TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at BIGINT,
                        email TEXT,
                        telephone TEXT,
                        taux_horaire REAL,
                        frais_ecolage REAL,
                        profession TEXT,
                        date_naissance TEXT,
                        lieu_naissance TEXT,
                        last_position_x REAL,
                        last_position_y REAL,
                        last_seen BIGINT
                    )
                """)

                # Table salaries avec CASCADE
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS salaries (
                        id TEXT PRIMARY KEY,
                        employee_id TEXT NOT NULL,
                        employee_name TEXT NOT NULL,
                        type TEXT NOT NULL,
                        amount REAL NOT NULL,
                        hours_worked REAL,
                        period TEXT NOT NULL,
                        date BIGINT NOT NULL,
                        is_synced INTEGER DEFAULT 0,
                        FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
                    )
                """)

                # Table pointages avec CASCADE
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pointages (
                        id TEXT PRIMARY KEY,
                        employee_id TEXT NOT NULL,
                        employee_name TEXT NOT NULL,
                        type TEXT NOT NULL,
                        timestamp BIGINT NOT NULL,
                        date TEXT NOT NULL,
                        is_synced INTEGER DEFAULT 0,
                        FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
                    )
                """)

                # Table rssi_measurements avec CASCADE
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS rssi_measurements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        employee_id TEXT NOT NULL,
                        anchor_id INTEGER NOT NULL,
                        anchor_x REAL NOT NULL,
                        anchor_y REAL NOT NULL,
                        rssi INTEGER NOT NULL,
                        mac TEXT,
                        timestamp BIGINT NOT NULL,
                        FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
                    )
                """)

                conn.commit()
                logger.info("✅ Tables SQLite initialisées avec CASCADE")
        except Exception as e:
            logger.error(f"❌ init_db SQLite : {e}")
            raise


def verify_schema():
    """Vérifie la structure de la table employees."""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()

        if DB_DRIVER == "postgres":
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'employees';
            """)
            rows = cursor.fetchall()
            columns = [row["column_name"] for row in rows]
        else:
            cursor.execute("PRAGMA table_info(employees);")
            rows = cursor.fetchall()
            columns = [row[1] for row in rows]

        logger.info(f"📋 Colonnes trouvées dans employees : {columns}")

        expected = ["id", "nom", "prenom", "type", "is_active", "created_at"]
        missing = [col for col in expected if col not in columns]

        if missing:
            logger.error(f"❌ Colonnes manquantes : {missing}")
        else:
            logger.info("✅ Schéma employees correct")

        cursor.close()
    except Exception as e:
        logger.error(f"❌ Erreur verify_schema : {e}")
        raise
    finally:
        if conn:
            conn.close()


def upgrade_foreign_keys():
    """
    Met à jour les contraintes de clés étrangères existantes pour CASCADE
    (uniquement si les tables existent déjà sans CASCADE)
    """
    if DB_DRIVER != "postgres":
        logger.info("ℹ️ Upgrade CASCADE non nécessaire pour SQLite")
        return
    
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Vérifier si les contraintes existent déjà
        cur.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name IN ('pointages', 'rssi_measurements', 'salaries')
            AND constraint_type = 'FOREIGN KEY'
        """)
        
        constraints = cur.fetchall()
        
        if not constraints:
            logger.info("ℹ️ Aucune contrainte à modifier (probablement nouvelle installation)")
            return
        
        logger.info("🔧 Mise à jour des contraintes de clés étrangères...")
        
        # Supprimer anciennes contraintes (si elles existent)
        try:
            cur.execute("ALTER TABLE pointages DROP CONSTRAINT IF EXISTS pointages_employee_id_fkey")
            cur.execute("ALTER TABLE rssi_measurements DROP CONSTRAINT IF EXISTS rssi_measurements_employee_id_fkey")
            cur.execute("ALTER TABLE salaries DROP CONSTRAINT IF EXISTS salaries_employee_id_fkey")
        except Exception as e:
            logger.warning(f"⚠️ Impossible de supprimer les contraintes: {e}")
        
        # Recréer avec CASCADE
        try:
            cur.execute("""
                ALTER TABLE pointages 
                ADD CONSTRAINT pointages_employee_id_fkey 
                FOREIGN KEY (employee_id) 
                REFERENCES employees(id) 
                ON DELETE CASCADE
            """)
            
            cur.execute("""
                ALTER TABLE rssi_measurements 
                ADD CONSTRAINT rssi_measurements_employee_id_fkey 
                FOREIGN KEY (employee_id) 
                REFERENCES employees(id) 
                ON DELETE CASCADE
            """)
            
            cur.execute("""
                ALTER TABLE salaries 
                ADD CONSTRAINT salaries_employee_id_fkey 
                FOREIGN KEY (employee_id) 
                REFERENCES employees(id) 
                ON DELETE CASCADE
            """)
            
            conn.commit()
            logger.info("✅ Contraintes de clés étrangères mises à jour avec CASCADE")
        except Exception as e:
            logger.warning(f"⚠️ Contraintes probablement déjà OK: {e}")
        
        cur.close()
        
    except Exception as e:
        logger.error(f"❌ upgrade_foreign_keys: {e}")
    finally:
        if conn:
            conn.close()
