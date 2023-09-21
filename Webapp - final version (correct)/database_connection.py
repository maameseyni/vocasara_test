from flask import Flask, flash
import mysql.connector
import config

db_config_client = {
    'host': config.DB_HOST,
    'user': config.DB_USER,
    'password': config.DB_PASSWORD,
    'database': config.DB_DATABASE
}

# Fonction utilitaire pour la base de données client
def execute_query(query, values=None, fetchall=False):
    try:
        conn = mysql.connector.connect(**db_config_client)
        cursor = conn.cursor(buffered=True)
        cursor.execute(query, values)
        conn.commit()
        result = cursor.fetchall() if fetchall else None
        cursor.close()
        conn.close()
        return result
    except mysql.connector.Error as error:
        flash('Erreur lors de l\'exécution de la requête : ' + str(error), 'error')
        return None