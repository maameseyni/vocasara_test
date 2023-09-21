import mysql.connector
import config

def create_table():
    try :
        # Configuration de la connexion MySQL
        db_config = {
            'host': config.DB_HOST,
            'user': config.DB_USER,
            'password': config.DB_PASSWORD,
            'database': config.DB_DATABASE
        }
        # Établir une connexion à la base de données
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Définir la requête de création de table
        create_table_query = '''
            CREATE TABLE IF NOT EXISTS user (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL,
                registration_date VARCHAR(255) NOT NULL,
                service VARCHAR(255),
                last_login DATETIME,
                profile_photo VARCHAR(255),
                role ENUM('admin', 'guest', 'client') NOT NULL DEFAULT 'client'
            )
        '''

        # Exécuter la requête de création de table
        cursor.execute(create_table_query)

        # Définir la requête de création de table login_attempts
        create_login_attempts_table_query = '''
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                attempts INT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''

        # Exécuter la requête de création de table login_attempts
        cursor.execute(create_login_attempts_table_query)

        # Définir la requête de création de table blocked_users
        create_blocked_users_table_query = '''
            CREATE TABLE IF NOT EXISTS blocked_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                block_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''

        # Exécuter la requête de création de table blocked_users
        cursor.execute(create_blocked_users_table_query)

#if u encoured encore with notification juste change by using notification VARCHAR(255) NOT NULL DEFAULT '' instance notification TEXT NOT NULL
        # Modify the create_session_table_query to include the 'approved' column
        create_session_table_query = '''
        CREATE TABLE IF NOT EXISTS session (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            session_id VARCHAR(255) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            notification VARCHAR(255) NOT NULL DEFAULT '',
            is_read BOOLEAN DEFAULT FALSE,
            is_read_admin BOOLEAN DEFAULT FALSE,
            approved BOOLEAN DEFAULT FALSE, -- New column for approval status
            UNIQUE (session_id)
        )
        '''
        # Execute the ALTER statement to add the new 'approved' column
        add_approved_column_query = '''
        ALTER TABLE session
        ADD UNIQUE (session_id)
        '''
        # Execute the ALTER statement to add the 'approved' column
        #cursor.execute(add_approved_column_query)
        # Execute the CREATE TABLE query to create the 'session' table
        cursor.execute(create_session_table_query)
        # Fermer la connexion à la base de données
        # Définir la requête de création de table fichiers
        create_fichiers_table_query = '''
            CREATE TABLE IF NOT EXISTS fichiers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email_utilisateur VARCHAR(255) NOT NULL,
                nom_fichier VARCHAR(255) NOT NULL,
                chemin_fichier VARCHAR(255) NOT NULL,
                type_fichier VARCHAR(255),
                date_creation DATETIME,
                poids_fichier VARCHAR(255),
                UNIQUE (nom_fichier, chemin_fichier)
            )
        '''

        # Exécuter la requête de création de table fichiers
        cursor.execute(create_fichiers_table_query)

        conn.close()
    except mysql.connector.Error as error:
        print('Erreur lors de la création de la table : ' + str(error), 'error')
create_table()
