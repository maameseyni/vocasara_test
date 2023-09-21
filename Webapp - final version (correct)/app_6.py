import os
import uuid
import torch
import base64
import torch.nn as nn
import torchvision.transforms as transforms
from torchvision.models import mobilenet_v2
from PIL import Image as IMG 
from flask import Flask, render_template, request, flash, redirect, session, url_for, send_from_directory,make_response
from werkzeug.utils import secure_filename  
import shutil
import mysql.connector
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from image_normal.Extractor_normal_image_copy import generate_report,app2_blueprint
from image_normal.regenerate_rapport_final_resume import app4_blueprint
from image_normal.merge_quantification_rapport_visible import app5_blueprint
import piexif
import logging
from admin_main import app3_blueprint
from flask import jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
import config
import openpyxl
from collections import Counter
import pandas as pd
import math
#from flask_wtf.csrf import CSRFProtect

# Configuration du logging pour les erreurs
log_folder = os.path.join(os.path.dirname(__file__), 'log')
if not os.path.exists(log_folder):
    os.makedirs(log_folder)

crash_log_path = os.path.join(log_folder, 'crash.log')
access_log_path = os.path.join(log_folder, 'access.log')

logging.basicConfig(filename=crash_log_path, level=logging.ERROR)

# Configuration du logging d'accès
access_logger = logging.getLogger('access')
access_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(access_log_path)
access_logger.addHandler(file_handler)

# Logguer les activités suspectes
suspicious_activity_logger = logging.getLogger('suspicious_activity')
suspicious_activity_logger.setLevel(logging.INFO)
suspicious_activity_handler = logging.FileHandler(os.path.join(log_folder, 'suspicious_activity.log'))
suspicious_activity_logger.addHandler(suspicious_activity_handler)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = config.SERVER_FOLDER
app.config['UPLOAD_FOLDER_photo'] = config.UPLOAD_FOLDER_PHOTO
app.config['ALLOWED_EXTENSIONS'] = {'jpg', 'jpeg', 'png'}
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']
ALLOWED_EXTENSIONS_doc = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx','kml', 'kmz','jpg', 'jpeg', 'png'}
#csrf = CSRFProtect(app)

app.register_blueprint(app2_blueprint)
app.register_blueprint(app3_blueprint)
app.register_blueprint(app4_blueprint)
app.register_blueprint(app5_blueprint)
# Fonction pour établir une connexion à la base de données
def get_db_connection():
    try:
        return mysql.connector.connect(
            host=config.DB_HOST,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_DATABASE
        )
    except mysql.connector.Error as error:
        print("Failed to connect to database: {}".format(error))
        return None
    
class LoginForm(FlaskForm):
    user = StringField('Utilisateur', validators=[DataRequired()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
    submit = SubmitField('Connexion')
        
@app.route('/formulaire_rapport')
def formulaire_rapport():
    # Redirige vers la route '/generate_report' dans 'app2_.py'
    return render_template('formulaire_rapport.html')

@app.route('/acceuil')
def acceuil(): 
    return render_template('acceuil.html' )

@app.route('/traitement')
def traitement():
    return render_template('traitement.html')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
           
def allowed_file_doc(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS_doc
 # Route Flask pour afficher la galerie

@app.route('/localisation_defauts', methods=['GET'])
def localisation_defauts():
    user_role = session.get('role')
    user_email = session.get('email')
    if 'email' not in session:
        return redirect(url_for('login'))
    if user_role != 'admin':
        user_folder = os.path.join(UPLOAD_FOLDER, user_email)
    else:
        user_folder = UPLOAD_FOLDER
    # Connexion à la base de données et récupération des chemins des fichiers
    conn = get_db_connection()  # Créez votre propre fonction pour établir une connexion à la base de données
    cursor = conn.cursor()
        # Si l'utilisateur n'est pas administrateur, ajoutez une condition pour filtrer par email
    if user_role != 'admin':
        cursor.execute("SELECT chemin_fichier, type_fichier, nom_fichier FROM fichiers WHERE nom_fichier LIKE %s AND type_fichier = %s AND email_utilisateur = %s", ("%Rapport_defaut%.xlsx", "excel/xlsx", user_email))
    else:
        cursor.execute("SELECT chemin_fichier, type_fichier, nom_fichier FROM fichiers WHERE nom_fichier LIKE %s AND type_fichier = %s", ("%Rapport_defaut%.xlsx", "excel/xlsx"))
    rows = cursor.fetchall()
    sql_query = "SELECT chemin_fichier, nom_fichier FROM fichiers WHERE type_fichier = 'image/JPEG'"
    cursor.execute(sql_query)
    result = cursor.fetchall()
        # Créez une liste de paires (nom de fichier, données base64) pour la galerie HTML
    image_data_list = []
    for row in result:
        image_path = row[0]
        image_name = row[1]
        try:
            with open(image_path, 'rb') as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
                image_data_list.append((image_name, image_data))
        except FileNotFoundError:
            # Si le fichier n'existe pas, ignorez-le et continuez avec les autres fichiers
            pass
    # Construisez la liste des chemins de fichiers à partir des résultats de la requête SQL
    files_list = [os.path.join(user_folder, row[0]) for row in rows]
    # Fermez la connexion à la base de données
    cursor.close()
    conn.close()
    return render_template('localisation_defauts.html', files_list=files_list,image_data_list=image_data_list)

@app.route('/get-file-data', methods=['GET'])
def get_file_data():
    file_name = request.args.get('file')
    df = pd.read_excel(file_name)  # Lire le fichier Excel avec pandas
    image_data = []
    data = df.values.tolist()  # Convertir les données en une liste de listes
    # Ajoutez les informations sur les images à la liste de données
    for i in range(len(data)):
        data[i].extend([image_data[i]])
    return jsonify(data)

@app.route('/get-selected-files-data', methods=['POST'])
def get_selected_files_data():
    selected_files = request.json
    data = []
    total_lines = 0  # Initialise le compteur total de lignes
    for file_name in selected_files:
        df = pd.read_excel(file_name)  # Lire le fichier Excel avec pandas
        data.extend(df.values.tolist())  # Ajouter les données à la liste
        total_lines += df.shape[0]  # Ajouter le nombre de lignes du fichier au compteur total
    # Enregistrer le nombre total de lignes dans le local storage du navigateur
    session['total_selected_lines'] = total_lines
    return jsonify(data)

# Define a route to serve image files
@app.route('/image_preview/<path:filename>')
def image_preview(filename):
    if 'email' not in session:
        return redirect(url_for('login'))
    user_role = session.get('role')
    if user_role == 'admin':
        user_folder = os.path.join(UPLOAD_FOLDER)
        file_path = os.path.join(user_folder, filename)
    else:
        user_folder = os.path.join(UPLOAD_FOLDER, session['email'])
        file_path = os.path.join(user_folder, filename)
    # Check if the requested file exists and is an image
    if os.path.exists(file_path) and allowed_file(filename):
        return send_from_directory(user_folder, filename)
    # If the file doesn't exist or is not an image, return a default image or an error image
    return send_from_directory('./logo', 'logo.png')

def extract_data(file_path):
    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active
    data = [cell.value for cell in sheet['D'][1:] if cell.value]
    return data

def process_data(data):
    counter = Counter()
    for entry in data:
        defects = entry.split('/')
        defects = [defect.strip() for defect in defects if defect.strip() != '']
        for defect in defects:
            counter[defect] += 1
    total = sum(counter.values())
    labels = list(counter.keys())
    values = list(counter.values())
    percentages = [(value / total) * 100 for value in values]  # Calculer les pourcentages
    return labels, values, percentages


@app.route('/statistics', methods=['GET', 'POST'])
def statistics():
    user_role = session.get('role')
    user_email = session.get('email')
    if 'email' not in session:
        return redirect(url_for('login'))
    # Si l'utilisateur n'est pas administrateur, définissez son dossier utilisateur
    if user_role != 'admin':
        user_folder = os.path.join(UPLOAD_FOLDER, user_email)
    else:
        user_folder = UPLOAD_FOLDER
    # Connexion à la base de données et récupération des chemins des fichiers
    conn = get_db_connection()  # Créez votre propre fonction pour établir une connexion à la base de données
    cursor = conn.cursor()
    # Si l'utilisateur n'est pas administrateur, ajoutez une condition pour filtrer par email
    if user_role != 'admin':
        cursor.execute("SELECT chemin_fichier FROM fichiers WHERE nom_fichier LIKE %s AND type_fichier = %s AND email_utilisateur = %s", ("%Rapport_defaut%.xlsx", "excel/xlsx", user_email))
    else:
        cursor.execute("SELECT chemin_fichier FROM fichiers WHERE nom_fichier LIKE %s AND type_fichier = %s", ("%Rapport_defaut%.xlsx", "excel/xlsx"))
    rows = cursor.fetchall()
    # Construisez la liste des chemins de fichiers à partir des résultats de la requête SQL
    files_list = [os.path.join(user_folder, row[0]) for row in rows]
    # Fermez la connexion à la base de données
    cursor.close()
    conn.close()
    if request.method == 'POST':
        selected_files = request.form.getlist('file[]')
        chart_type = request.form.get('chart-type')
        all_data = []
        # Process selected files
        for file_path in files_list:
            if file_path in selected_files:
                extracted_data = extract_data(file_path)
                all_data.extend(extracted_data)
        if chart_type == 'pie':
            labels, values, percentages = process_data(all_data)
            chart_data = {'labels': labels, 'values': values, 'percentages': percentages, 'chartType': 'pie'}
        elif chart_type == 'bar':
            labels, values, percentages = process_data(all_data)
            numbers = [values[labels.index(label)] for label in labels]
            chart_data = {'labels': labels, 'values': values, 'numbers': numbers, 'percentages': percentages, 'chartType': 'bar'}
        return jsonify(chart_data)
    return render_template('statistics.html', files_list=files_list)


def check_file_approval_in_database(file_path):
    connection = get_db_connection()
    cursor = connection.cursor()
    query = "SELECT approved FROM session WHERE file_path = %s"
    values = (file_path,)
    cursor.execute(query, values)
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    if result and result[0]:  # Si le fichier est approuvé (result[0] == True)
        return True
    return False


@app.route('/files', defaults={'path': ''})
@app.route('/files/<path:path>')
def files(path):
    if 'email' not in session:
        return redirect(url_for('login'))
    
    user_role = session.get('role')
    user_folder = os.path.join(UPLOAD_FOLDER, session['email']) if user_role != "admin" else os.path.join(UPLOAD_FOLDER)

    if not os.path.exists(user_folder):
        os.makedirs(user_folder)

    target_folder = os.path.join(user_folder, path)
    if not os.path.exists(target_folder) or not os.path.isdir(target_folder):
        return redirect(url_for('files'))

    connection = get_db_connection()
    cursor = connection.cursor()

    if user_role != 'admin':
        session_id = os.path.basename(path)
        query = "SELECT approved FROM session WHERE session_id = %s"
        values = (session_id,)
        cursor.execute(query, values)
        result = cursor.fetchone()
        if result and not result[0]:
            flash('Vous n\'êtes pas autorisé à accéder à cette session.', 'error')
            cursor.close()
            connection.close()
            return redirect(url_for('files'))

    query = "SELECT session_id, approved FROM session"
    cursor.execute(query)
    sessions = cursor.fetchall()
    approved_sessions = [session[0] for session in sessions if session[1]]
    not_approved_sessions = [session[0] for session in sessions if not session[1]]
    cursor.close()
    connection.close()
    files_list = []
    folders_list = []
 
    for file in os.listdir(target_folder):
        file_path = os.path.join(target_folder, file)
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")  # Ajoutez cette ligne pour le débogage
            continue  # Ignorer ce fichier s'il n'existe pas
        modified_date = datetime.fromtimestamp(os.path.getmtime(file_path))
        if os.path.isfile(file_path) and allowed_file_doc(file):
            files_list.append((file, modified_date))
        elif os.path.isdir(file_path):
            folders_list.append((file, modified_date))

    return render_template('file.html', path=path, folders=folders_list, files=files_list,
                           approved_sessions=approved_sessions, not_approved_sessions=not_approved_sessions)

@app.route('/disapprove_session', methods=['POST'])
def disapprove_session():
    if 'email' not in session:
        return redirect(url_for('login'))
    user_role = session.get('role')
    if user_role != 'admin':
        flash("Vous n\'êtes pas autorisé à effectuer cette action. La session n'a pas été désapprouvée", 'error')
        return redirect(url_for('files'))
    session_id = request.form.get('session_id')
    connection = get_db_connection()
    cursor = connection.cursor()
    query = "UPDATE session SET approved = FALSE WHERE session_id = %s"
    values = (session_id,)
    cursor.execute(query, values)
    connection.commit()
    cursor.close()
    connection.close()
    flash('La session a été désapprouvée avec succès.', 'success')
    return redirect(url_for('files'))


@app.route('/approve_session', methods=['POST'])
def approve_session():
    if 'email' not in session:
        return redirect(url_for('login'))
    user_role = session.get('role')
    if user_role != 'admin':
        flash("Vous n\'êtes pas autorisé à effectuer cette action.La session n'a pas été approuvée", 'error')
        return redirect(url_for('files'))
    session_id = request.form.get('session_id')
    connection = get_db_connection()
    cursor = connection.cursor()
    query = "UPDATE session SET approved = TRUE WHERE session_id = %s"
    values = (session_id,)
    cursor.execute(query, values)
    connection.commit()
    cursor.close()
    connection.close()
    flash('La session a été approuvée avec succès.', 'success')
    return redirect(url_for('files'))

@app.route('/download/<path:filename>')
def download(filename):
    if 'email' not in session:
        return redirect(url_for('login'))
    
    user_role = session.get('role')
    if user_role == "admin":
        user_folder = os.path.join(UPLOAD_FOLDER)
    else :
        user_folder = os.path.join(UPLOAD_FOLDER, session['email'])
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    file_path = os.path.join(user_folder, filename)
    if os.path.isfile(file_path) and allowed_file_doc(filename):
        return send_from_directory(user_folder, filename, as_attachment=True)

    return redirect(url_for('files'))

# Route pour la page de connexion
@app.route('/')
def login():
    form = LoginForm(request.form)
    return render_template('index_login.html',form=form)


@app.route('/get_notifications', methods=['GET'])
def get_notifications():
    email = session.get('email')
    if not email:
        return jsonify({'error': 'Utilisateur non connecté.'}), 401

    role = request.args.get('role')  # Récupérer le rôle de l'utilisateur depuis la requête GET

    connection = get_db_connection()
    cursor = connection.cursor()
    
    if role == 'admin':
        # Si l'utilisateur est un admin, récupérer toutes les notifications
        cursor.execute('SELECT id, notification, is_read_admin AS is_read FROM session ORDER BY created_at DESC')
    else:
        # Sinon, récupérer les notifications de l'utilisateur spécifique
        cursor.execute('SELECT id, notification, is_read FROM session WHERE email = %s ORDER BY created_at DESC', (email,))

    notifications = [
        {
            'id': id,
            'notification': notification,
            'is_read': is_read,
        }
        for id, notification, is_read in cursor.fetchall()
    ]
    cursor.close()
    connection.close()
    return jsonify(notifications)

@app.route('/mark_notification_as_read', methods=['POST'])
def mark_notification_as_read():
    if request.method == 'POST':
        notification_id = request.form.get('notificationId')
        if notification_id:
            connection = get_db_connection()
            cursor = connection.cursor()

            user_role = request.headers.get('role')  # Récupérer le rôle de l'utilisateur à partir de l'en-tête

            if user_role == 'admin':
                cursor.execute('UPDATE session SET is_read_admin = TRUE WHERE id = %s', (notification_id,))
            else:
                cursor.execute('UPDATE session SET is_read = TRUE WHERE id = %s', (notification_id,))

            connection.commit()
            cursor.close()
            connection.close()
            return jsonify({'message': 'Notification marquée comme lue.'})
        else:
            return jsonify({'error': 'ID de notification manquant.'}), 400
    return jsonify({'error': 'Méthode non autorisée.'}), 405

@app.route('/profile')
def profil():
    # Vérifier si l'utilisateur est connecté
    if 'email' not in session:
        return redirect(url_for('login'))

    # Récupérer les informations du profil depuis la base de données
    connection = get_db_connection()
    if connection is None:
        return "Erreur de connexion à la base de données"

    cursor = connection.cursor()
    email = session['email']
    cursor.execute("SELECT id, email, password, registration_date, service, last_login, profile_photo FROM user WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user is None:
        cursor.close()
        connection.close()
        return "Utilisateur non trouvé dans la base de données"

    profile_photo_path = os.path.normpath(os.path.join(app.config['UPLOAD_FOLDER_photo'], user[6])) if user[6] else None
    # Convertir le chemin de la photo de profil en base64
    profile_photo = None
    if profile_photo_path:
        with open(profile_photo_path, 'rb') as file:
            profile_photo = base64.b64encode(file.read()).decode('utf-8')

    cursor.close()
    connection.close()

    # Renvoyer les informations du profil à la page HTML
    return render_template('profile.html', email=user[1], registration_date=user[3], service=user[4], last_login=user[5], profile_photo=profile_photo)
@app.route('/change_photo', methods=['POST'])
def change_photo():
    # Vérifier si l'utilisateur est connecté
    if 'email' not in session:
        return redirect(url_for('login'))

    # Vérifier si le fichier a été envoyé dans la requête
    if 'file' not in request.files:
        return "Aucun fichier n'a été envoyé"

    file = request.files['file']
    # Vérifier si le fichier a un nom de fichier valide et une extension autorisée
    if file.filename == '':
        return "Le fichier n'a pas de nom"
    if not allowed_file(file.filename):
        return "Extension de fichier non autorisée"

    email = session['email']
    destination_folder = os.path.join(app.config['UPLOAD_FOLDER_photo'], email)

    # Créer le dossier de destination s'il n'existe pas déjà
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    # Obtenir le chemin de la photo de profil actuelle depuis la base de données
    connection = get_db_connection()
    if connection is None:
        return "Erreur de connexion à la base de données"

    cursor = connection.cursor()
    cursor.execute("SELECT profile_photo FROM user WHERE email = %s", (email,))
    old_profile_photo = cursor.fetchone()[0]

    # Supprimer l'ancienne photo de profil si elle existe
    if old_profile_photo:
        old_profile_photo_path = os.path.join(app.config['UPLOAD_FOLDER_photo'], old_profile_photo)
        if os.path.exists(old_profile_photo_path):
            os.remove(old_profile_photo_path)

    # Enregistrer le fichier avec un nom sécurisé dans le dossier de destination
    filename = secure_filename(file.filename)
    file.save(os.path.join(destination_folder, filename))

    # Mettre à jour la photo de profil dans la base de données avec le chemin complet du fichier
    photo_path = os.path.join(destination_folder, filename)
    cursor.execute("UPDATE user SET profile_photo = %s, profile_photo = %s WHERE email = %s", (filename, photo_path, email))
    connection.commit()
    cursor.close()
    connection.close()
    flash('Votre photo de profil a été mise à jour avec succès.', 'success')
    return redirect(url_for('profil'))


@app.route('/delete_photo', methods=['POST'])
def delete_photo():
    # Vérifier si l'utilisateur est connecté
    if 'email' not in session:
        return redirect(url_for('login'))

    connection = get_db_connection()
    if connection is None:
        return "Erreur de connexion à la base de données"

    cursor = connection.cursor()
    email = session['email']
    # Mettre à jour la base de données pour supprimer la photo de profil
    cursor.execute("UPDATE user SET profile_photo = NULL WHERE email = %s", (email,))
    connection.commit()
    cursor.close()
    connection.close()
    flash('Votre photo de profil a été supprimée avec succès.', 'success')
    return redirect(url_for('profil'))

@app.route('/change_password', methods=['POST'])
def change_password():
    # Vérifier si l'utilisateur est connecté
    if 'email' not in session:
        return redirect(url_for('login'))

    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    # Vérifier si les champs de mot de passe sont vides
    if not current_password or not new_password or not confirm_password:
        flash("Veuillez remplir tous les champs", "error")
        return redirect(url_for('profil'))
    # Vérifier si le nouveau mot de passe correspond à la confirmation
    if new_password != confirm_password:
        flash("Le nouveau mot de passe ne correspond pas à la confirmation", "error")
        return redirect(url_for('profil'))
    # Vérifier si l'utilisateur existe dans la base de données
    connection = get_db_connection()
    if connection is None:
        flash("Erreur de connexion à la base de données", "error")
        return redirect(url_for('profil'))
    cursor = connection.cursor()
    email = session['email']
    cursor.execute("SELECT password FROM user WHERE email = %s", (email,))
    result = cursor.fetchone()
    # Vérifier si le mot de passe actuel est correct
    if not result or result[0] != current_password:
        flash("Mot de passe actuel incorrect", "error")
        return redirect(url_for('profil'))

    # Mettre à jour le nouveau mot de passe dans la base de données
    cursor.execute("UPDATE user SET password = %s WHERE email = %s", (new_password, email))
    connection.commit()

    cursor.close()
    connection.close()

    flash("Mot de passe modifié avec succès", "success")
    return redirect(url_for('profil'))

# Route pour se déconnecter
@app.route('/logout')
def logout():
    # Enregistrement des informations de déconnexion dans le log d'accès
    access_logger.info('Utilisateur {} déconnecté à {}'.format(session.get('email'), datetime.now()))
    session.pop('email', None)
    return redirect(url_for('login'))

@app.route('/validate', methods=['POST'])
def validate():
    form = LoginForm(request.form)
    
    if form.validate_on_submit():
        email = form.user.data
        password = form.password.data
    
    if not email or not password:
        flash('Veuillez entrer un email et un mot de passe', 'error')
        return redirect('/')
    
    connection = get_db_connection()
    if connection is None:
        flash('Erreur de connexion à la base de données', 'error')
        return redirect('/')

    cursor = connection.cursor()

    # Vérification du nombre de tentatives de connexion
    cursor.execute('SELECT * FROM login_attempts WHERE email=%s', (email,))
    login_attempts = cursor.fetchone()
    if login_attempts and login_attempts[2] >= 5:
        # Vérification du délai de blocage
        if login_attempts[3] > datetime.now():
            time_left = login_attempts[3] - datetime.now()
            flash('Trop de tentatives de connexion. Veuillez réessayer dans {} minutes.'.format(time_left.seconds // 60), 'error')
            return redirect('/')
        else:
            # Réinitialisation des tentatives de connexion
            cursor.execute('DELETE FROM login_attempts WHERE email=%s', (email,))
            connection.commit()
    # Vérification du blocage de l'utilisateur
    cursor.execute('SELECT * FROM blocked_users WHERE email=%s', (email,))
    blocked_user = cursor.fetchone()
    if blocked_user:
        # Vérification du délai de blocage
        if blocked_user[2] > datetime.now():
            time_left = blocked_user[2] - datetime.now()
            flash('Votre compte est temporairement bloqué. Veuillez réessayer dans {} minutes.'.format(time_left.seconds // 60), 'error')
            suspicious_activity_logger.warning('Tentative de connexion échouée (compte temporairement bloqué) : email={}, time_left={}'.format(email, time_left.seconds // 60))
            return redirect('/')
        else:
            # Suppression de l'utilisateur bloqué
            cursor.execute('DELETE FROM blocked_users WHERE email=%s', (email,))
            connection.commit()
    # Récupération du mot de l'utilisateur depuis la base de données
    cursor.execute('SELECT password,role FROM user WHERE email=%s', (email,))
    stored_password = cursor.fetchone()
    if stored_password is None or stored_password[0] != password:
        # Mise à jour du nombre de tentatives de connexion
        if login_attempts:
            attempts = login_attempts[2] + 1
            if attempts >= 5:
                # Bloquer l'utilisateur après 5 tentatives
                block_time = datetime.now() + timedelta(hours=1)
                cursor.execute('INSERT INTO blocked_users (email, block_time) VALUES (%s, %s)', (email, block_time))
                connection.commit()
                flash('Trop de tentatives de connexion. Votre compte a été bloqué.', 'error')
                # Enregistrer l'activité suspecte
                suspicious_activity_logger.warning('Tentative de connexion échouée (compte bloqué) : email={}, time_left={}'.format(email, time_left.seconds // 60))
                return render_template('403_admin.html')
            else:
                cursor.execute('UPDATE login_attempts SET attempts=%s WHERE email=%s', (attempts, email))
        else:
            cursor.execute('INSERT INTO login_attempts (email, attempts) VALUES (%s, %s)', (email, 1))
        connection.commit()
        
        flash('Email ou mot de passe incorrect', 'error')
        suspicious_activity_logger.warning('Tentative de connexion échouée (mot de passe incorrect) : email={}'.format(email))
        return redirect('/')
    else:
        # Réinitialisation du nombre de tentatives de connexion
        if login_attempts:
            cursor.execute('DELETE FROM login_attempts WHERE email=%s', (email,))
            connection.commit()
        # Mise à jour de la dernière heure et date de connexion
        current_time = datetime.now()
        cursor.execute('UPDATE user SET last_login=%s WHERE email=%s', (current_time, email))
        connection.commit()
        session['email'] = email
        # Enregistrement des informations de connexion dans le log d'accès
        access_logger.info('Utilisateur {} connecté à {}'.format(email, datetime.now()))
            # Récupération du rôle de l'utilisateur depuis la base de données
        user_role = stored_password[1]
        if user_role:
            role = user_role
            session['role'] = role
            flash(role)
            if user_role != 'admin':
                # Logic for admin user
                return redirect(url_for('acceuil'))
            else:
                # Logic for regular client user
                return redirect(url_for('acceuil'))
        else:
            flash('Rôle de l\'utilisateur non trouvé', 'error')
            return redirect('/')
        
def create_user_folder(email):
    user_folder_path = os.path.join(app.config['UPLOAD_FOLDER'], email.replace('@', '_').replace('.', '_'))
    os.makedirs(user_folder_path, exist_ok=True)
    return user_folder_path

def create_defect_folder(user_folder_path, defect_name):
    defect_folder_path = os.path.join(user_folder_path, defect_name)
    os.makedirs(defect_folder_path, exist_ok=True)
    return defect_folder_path

def create_session_folder(user_folder_path, session_id):
    session_folder_path = os.path.join(user_folder_path, session_id)
    if not os.path.exists(session_folder_path):
        os.makedirs(session_folder_path)
    return session_folder_path

def get_last_session_folder(user_folder_path):
    subfolders = [f for f in os.listdir(user_folder_path) if os.path.isdir(os.path.join(user_folder_path, f))]
    if subfolders:
        last_folder = max(subfolders, key=os.path.getctime)
        return os.path.join(user_folder_path, last_folder)
    else:
        return None


def get_unique_session_id(email):
    session_id = str(uuid.uuid4())
    create_session(email, session_id)
    return session_id

#classification d'images chargement du model
def load_model(num_classes):
    model = mobilenet_v2(pretrained=True)
    for param in model.parameters():
        param.requires_grad = False
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, num_classes)
    model.dropout = nn.Dropout(0.3)
    try:
        model.load_state_dict(torch.load('./model/model.pt'))
    except:
        model.load_state_dict(torch.load('./model/model.pt', map_location=torch.device('cpu')))
    return model.to(device)

#classification d'images
def get_transform():
    return transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

def remove_unsorted_images(user_folder_path):
    file_list = os.listdir(user_folder_path)
    for file_name in file_list:
        file_path = os.path.join(user_folder_path, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)

#classification d'images
def inference_image(model, image_path, class_names, user_folder_path):
    email = session.get('email')
    transform = get_transform()
    image = IMG.open(image_path).convert('RGB')
    transformed_image = transform(image).unsqueeze(0).to(device)
    model.eval()
    with torch.no_grad():
        outputs = model(transformed_image)
        probabilities = torch.softmax(outputs, dim=1)[0]
        _, predicted = torch.max(outputs.data, 1)
        detected_defects = []
        for i, prob in enumerate(probabilities):
            if prob.item() > 0.2:
                defect_name = class_names[i]
                defect_prob = prob.item() * 100
                detected_defects.append((defect_name, defect_prob))
                defect_folder_path = create_defect_folder(user_folder_path, defect_name)
                shutil.copy(image_path, defect_folder_path)  # Copie de l'image sans la convertir
                # Après avoir copié l'image dans le dossier approprié, insérez les informations dans la base de données
        for defect_name, defect_prob in detected_defects:
            # Obtenez les informations du fichier
            file_name = os.path.basename(image_path)
            file_path = os.path.join(user_folder_path, defect_name, file_name)
            file_type = "image/JPEG"  # Vous pouvez obtenir le type de fichier à partir de l'extension du fichier
            creation_date = datetime.now()  # Utilisez la date actuelle
            file_size = convert_size(os.path.getsize(image_path))
            # Insérez les informations du fichier dans la base de données
            insert_file_info_to_db(email, file_name, file_path, file_type, creation_date, file_size)
    
        # Supprimer les images non rangées
        remove_unsorted_images(user_folder_path)
        if len(detected_defects) > 0:
            detected_defects = sorted(detected_defects, key=lambda x: x[1], reverse=True)
            return detected_defects
        else:
            return None

#classification d'images
def load_class_names():
    class_names = []
    with open('./label/class_label.txt', 'r') as f:
        for line in f:
            class_names.append(line.strip())
    return class_names

#creation de sesssion d'utlisateur
def create_session(user_email, session_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    query = "INSERT INTO session (session_id, email, approved) " \
            "VALUES (%s, %s, %s) " \
            "ON DUPLICATE KEY UPDATE email=VALUES(email), approved=VALUES(approved)"
    values = (session_id, user_email, False)  # Setting approved to False for new sessions
    cursor.execute(query, values)
    # Commit the transaction to make the changes persistent
    connection.commit()

#récupération de la session
def get_user_session(email):
    connection = get_db_connection()
    cursor = connection.cursor()
    query = "SELECT session_id FROM user WHERE email = %s"
    values = (email,)
    cursor.execute(query, values)
    user = [session[0] for session in cursor.fetchall()]
    cursor.close()
    connection.close()
    return user

#récupération de l'email
def get_email(session_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    query = "SELECT email FROM session WHERE session_id = %s"
    values = (session_id,)
    cursor.execute(query, values)
    email = cursor.fetchone()
    cursor.close()
    connection.close()
    if email:
        return email[0]
    else:
        return None

#création d'un nom de fichier unique
def get_unique_filename(folder_path, filename):
    base_name = filename.rsplit('.', 1)[0]
    extension = filename.rsplit('.', 1)[1]
    counter = 1
    unique_filename = filename
    while os.path.exists(os.path.join(folder_path, unique_filename)):
        unique_filename = f"{base_name}_{counter}.{extension}"
        counter += 1
    return unique_filename

#compression des images
def compress_image(image_path, output_path, quality=60):
    with IMG.open(image_path) as img:
        # Sauvegarder les données EXIF
        exif_data = img.info.get('exif')
        # Compresser l'image
        compressed_img = img.copy()
        compressed_img.save(output_path, format='JPEG', optimize=True, quality=quality)
        # Restaurer les données EXIF dans l'image compressée
        if exif_data:
            exif_dict = piexif.load(image_path)
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, output_path)
  
#page de traitement focntion pour charger les photos et les classer              
@app.route('/upload_and_predict', methods=['GET', 'POST'])
def upload_and_predict():
    if request.method == 'POST':
        email = session.get('email')
        if email is None:
            flash("Veuillez vous connecter pour accéder à cette page.")
            return redirect('/')
        session_id = str(uuid.uuid4())
        user_folder_path = os.path.join(UPLOAD_FOLDER, email)
        session_folder_path = os.path.join(user_folder_path, session_id)
        if not os.path.exists(user_folder_path):
            os.makedirs(user_folder_path)
        if not os.path.exists(session_folder_path):
            os.makedirs(session_folder_path)
        uploaded_files = request.files.getlist('files')
        class_names = load_class_names()
        num_classes = len(class_names)
        model = load_model(num_classes)
        detected_defects = []
        ignored_images = []
        image_count = 0
        # Dans la fonction upload_and_predict, après avoir enregistré le fichier :
        for file in uploaded_files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                existing_file_path = os.path.join(session_folder_path, filename)

                if os.path.exists(existing_file_path):
                    unique_filename = get_unique_filename(session_folder_path, filename)
                    file_path = os.path.join(session_folder_path, unique_filename)
                    flash("Le fichier {} a été renommé en {} pour éviter les conflits.".format(filename, unique_filename))
                else:
                    file_path = os.path.join(session_folder_path, filename)
                file.save(file_path)
                # Compress the image and save it with a new filename
                compressed_file_path = os.path.join(session_folder_path, "VC_" + filename)
                compress_image(file_path, compressed_file_path)
                image_count += 1
                defects = inference_image(model, compressed_file_path, class_names, session_folder_path)
                if defects:
                    detected_defects.extend(defects)
                else:
                    ignored_images.append(filename)
            else:
                ignored_images.append(file.filename)
        if ignored_images:
            flash("Les fichiers suivants n'ont pas pu être chargés car ils ne sont pas pris en compte: " + ', '.join(ignored_images))
        if detected_defects:
            defect_counts = {}
            for defect_name, _ in detected_defects:
                defect_counts[defect_name] = defect_counts.get(defect_name, 0) + 1
            create_session(email, session_id)
            flash("Nombre d'images chargées : {}".format(image_count))
            generate_report(session_folder_path)
            flash ('rapport généré avec succès. veuillez regardez danss mes ficher /profil')
            notification_exists_query = 'SELECT id FROM session WHERE session_id = %s'
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute(notification_exists_query, (session_id,))
            existing_notification_id = cursor.fetchone()
            # Mettre à jour la notification existante
            update_notification_query = 'UPDATE session SET notification = %s, created_at = %s WHERE id = %s'
            notification = "Nouveau rapport généré le {} pour l'utilisateur {} pour la session {}".format(
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session.get('email'), session_id
            )
            data = (notification, datetime.now(), existing_notification_id[0])
            cursor.execute(update_notification_query, data)
            connection.commit()
            cursor.close()
            connection.close()

            return render_template('traitement.html', detected_defects=detected_defects, defect_counts=defect_counts)
        else:
            flash("Aucune image n'a été chargée? assurez vous de sélectionner des images correctes.")
    return render_template('traitement.html')

# Fonction pour insérer les informations du fichier dans la base de données
def insert_file_info_to_db(email, file_name, file_path, file_type, creation_date, file_size):
    connection = get_db_connection()
    cursor = connection.cursor()
    query = "INSERT INTO fichiers (email_utilisateur, nom_fichier, chemin_fichier, type_fichier, date_creation, poids_fichier) " \
            "VALUES (%s, %s, %s, %s, %s, %s)"
    values = (email, file_name, file_path, file_type, creation_date, file_size)
    cursor.execute(query, values)
    connection.commit()

def convert_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404_admin.html'), 404

@app.errorhandler(403)
def page_not_found(e):
    return render_template('403_admin.html'), 403

if __name__ == '__main__':
    app.run(debug=True)

