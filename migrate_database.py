import sqlite3
import logging
import os
import glob
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

def find_database():
    """
    Trouve automatiquement la base de données SQLite dans le répertoire
    """
    possible_names = ['employees.db', 'database.db', 'app.db', '*.db']
    
    for pattern in possible_names:
        files = glob.glob(pattern)
        if files:
            db_file = files[0]
            if os.path.exists(db_file):
                logger.info(f"✅ Base de données trouvée: {db_file}")
                return db_file
    
    logger.error("❌ Aucune base de données trouvée!")
    logger.info("💡 Assurez-vous d'être dans le bon répertoire")
    return None

def backup_database(db_path):
    """
    Crée une sauvegarde de la base de données
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{db_path}.backup_{timestamp}"
        
        # Copier le fichier
        import shutil
        shutil.copy2(db_path, backup_path)
        
        logger.info(f"💾 Sauvegarde créée: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde: {e}")
        return None

def check_tables(conn):
    """
    Vérifie que les tables nécessaires existent
    """
    cursor = conn.cursor()
    
    required_tables = ['employees', 'pointages', 'salaries']
    existing_tables = []
    
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
    """)
    
    for row in cursor.fetchall():
        existing_tables.append(row[0])
    
    missing_tables = [t for t in required_tables if t not in existing_tables]
    
    if missing_tables:
        logger.warning(f"⚠️ Tables manquantes: {', '.join(missing_tables)}")
        logger.info("💡 Lancez d'abord 'python3 app.py' pour créer les tables")
        return False
    
    logger.info(f"✅ Toutes les tables sont présentes: {', '.join(existing_tables)}")
    return True

def migrate_pointages(conn):
    """
    Corrige tous les employee_name dans la table pointages
    """
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        logger.info("🔄 Début de la migration des pointages...")
        
        # Vérifier qu'il y a des données
        cursor.execute("SELECT COUNT(*) as total FROM pointages")
        total = cursor.fetchone()['total']
        
        if total == 0:
            logger.info("ℹ️ Aucun pointage à migrer")
            return
        
        # Récupérer tous les pointages
        cursor.execute("""
            SELECT p.id, p.employee_id, p.employee_name, e.nom, e.prenom
            FROM pointages p
            LEFT JOIN employees e ON e.id = p.employee_id
            WHERE p.employee_id IS NOT NULL
        """)
        
        pointages = cursor.fetchall()
        updated_count = 0
        
        for pointage in pointages:
            pointage_id = pointage['id']
            old_name = pointage['employee_name']
            nom = pointage['nom']
            prenom = pointage['prenom']
            
            if not nom or not prenom:
                logger.warning(f"⚠️ Employé incomplet pour pointage {pointage_id}")
                continue
            
            # ✅ Format correct: "Nom Prénom"
            correct_name = f"{nom} {prenom}"
            
            if old_name != correct_name:
                cursor.execute("""
                    UPDATE pointages
                    SET employee_name = ?
                    WHERE id = ?
                """, (correct_name, pointage_id))
                
                updated_count += 1
                logger.info(f"  ✅ Corrigé: '{old_name}' → '{correct_name}'")
        
        conn.commit()
        logger.info(f"✅ Migration pointages terminée: {updated_count}/{total} corrigés")
        
    except Exception as e:
        logger.error(f"❌ Erreur migration pointages: {e}", exc_info=True)
        conn.rollback()

def migrate_salaries(conn):
    """
    Corrige tous les employee_name dans la table salaries
    """
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        logger.info("🔄 Début de la migration des salaires...")
        
        cursor.execute("SELECT COUNT(*) as total FROM salaries")
        total = cursor.fetchone()['total']
        
        if total == 0:
            logger.info("ℹ️ Aucun salaire à migrer")
            return
        
        cursor.execute("""
            SELECT s.id, s.employee_id, s.employee_name, e.nom, e.prenom
            FROM salaries s
            LEFT JOIN employees e ON e.id = s.employee_id
            WHERE s.employee_id IS NOT NULL
        """)
        
        salaries = cursor.fetchall()
        updated_count = 0
        
        for salary in salaries:
            salary_id = salary['id']
            old_name = salary['employee_name']
            nom = salary['nom']
            prenom = salary['prenom']
            
            if not nom or not prenom:
                logger.warning(f"⚠️ Employé incomplet pour salaire {salary_id}")
                continue
            
            correct_name = f"{nom} {prenom}"
            
            if old_name != correct_name:
                cursor.execute("""
                    UPDATE salaries
                    SET employee_name = ?
                    WHERE id = ?
                """, (correct_name, salary_id))
                
                updated_count += 1
                logger.info(f"  ✅ Corrigé: '{old_name}' → '{correct_name}'")
        
        conn.commit()
        logger.info(f"✅ Migration salaires terminée: {updated_count}/{total} corrigés")
        
    except Exception as e:
        logger.error(f"❌ Erreur migration salaires: {e}", exc_info=True)
        conn.rollback()

def verify_data(conn):
    """
    Vérifie que toutes les données sont cohérentes
    """
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        logger.info("🔍 Vérification finale...")
        
        # Vérifier pointages
        cursor.execute("""
            SELECT p.employee_name, e.nom, e.prenom
            FROM pointages p
            LEFT JOIN employees e ON e.id = p.employee_id
            WHERE p.employee_id IS NOT NULL
            LIMIT 10
        """)
        
        rows = cursor.fetchall()
        if rows:
            logger.info("📋 Échantillon de pointages:")
            errors = 0
            for row in rows:
                expected = f"{row['nom']} {row['prenom']}"
                status = "✅" if row['employee_name'] == expected else "❌"
                logger.info(f"  {status} {row['employee_name']}")
                if status == "❌":
                    errors += 1
            
            if errors == 0:
                logger.info("✅ Tous les pointages sont cohérents!")
            else:
                logger.warning(f"⚠️ {errors} pointages incohérents détectés")
        
        # Statistiques finales
        cursor.execute("SELECT COUNT(*) as total FROM pointages")
        total_pointages = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM employees")
        total_employees = cursor.fetchone()['total']
        
        logger.info(f"📊 Statistiques:")
        logger.info(f"  - {total_employees} employés")
        logger.info(f"  - {total_pointages} pointages")
        
    except Exception as e:
        logger.error(f"❌ Erreur vérification: {e}", exc_info=True)

def main():
    """
    Fonction principale
    """
    logger.info("=" * 70)
    logger.info("MIGRATION: Uniformisation des noms d'employés (Web ↔ Android)")
    logger.info("=" * 70)
    
    # Trouver la base de données
    db_path = find_database()
    if not db_path:
        return
    
    # Demander confirmation
    logger.info(f"\n⚠️  Base de données: {db_path}")
    response = input("Voulez-vous continuer? (oui/non): ").lower().strip()
    
    if response not in ['oui', 'o', 'yes', 'y']:
        logger.info("❌ Migration annulée")
        return
    
    # Créer une sauvegarde
    backup_path = backup_database(db_path)
    if not backup_path:
        logger.error("❌ Impossible de créer une sauvegarde, abandon")
        return
    
    # Ouvrir la connexion
    try:
        conn = sqlite3.connect(db_path)
        
        # Vérifier les tables
        if not check_tables(conn):
            conn.close()
            return
        
        # Exécuter les migrations
        migrate_pointages(conn)
        migrate_salaries(conn)
        verify_data(conn)
        
        conn.close()
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ Migration terminée avec succès!")
        logger.info("=" * 70)
        logger.info(f"💾 Sauvegarde disponible: {backup_path}")
        logger.info("🚀 Vous pouvez maintenant relancer le serveur: python3 app.py")
        
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}", exc_info=True)

if __name__ == "__main__":
    main()
