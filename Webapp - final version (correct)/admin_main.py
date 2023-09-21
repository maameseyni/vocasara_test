from flask import Flask, render_template, request, redirect, url_for,flash,Blueprint
import mysql.connector
from datetime import datetime
import os
from image_normal.Extractor_normal_image_copy import generate_report
import mysql.connector
import config
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
from base64 import b64encode

app3_blueprint = Blueprint('app3',__name__)
# Chemin du dossier du serveur
SERVER_FOLDER = config.SERVER_FOLDER
UPLOAD_FOLDER_PHOTO = config.UPLOAD_FOLDER_PHOTO

# Configuration de la base de données client
# Configuration de la base de données client
db_config_client = {
    'host': config.DB_HOST,
    'user': config.DB_USER,
    'password': config.DB_PASSWORD,
    'database': config.DB_DATABASE
}
# Fonction utilitaire pour la base de données client
def execute_query(query, values=None, fetchall=False):
    conn = mysql.connector.connect(**db_config_client)
    cursor = conn.cursor(buffered=True, dictionary=True)  # Ajoutez l'option dictionary=True
    cursor.execute(query, values)
    conn.commit()
    result = cursor.fetchall() if fetchall else None
    cursor.close()
    conn.close()
    return result


@app3_blueprint.route('/admin_dashboard')
def admin_dashboard():
    flash('Welcome to admin dashboard', 'success')

    # Récupérer les informations de la base de données
    users_query = "SELECT * FROM user"
    users = execute_query(users_query, fetchall=True)

    for user in users:
        email = user['email']
        fichiers_query = f"SELECT * FROM fichiers WHERE email_utilisateur='{email}'"
        fichiers = execute_query(fichiers_query, fetchall=True)

        user['nombre_images'] = len([f for f in fichiers if f['type_fichier'] == 'image/JPEG'])
        user['nombre_rapports'] = len([f for f in fichiers if f['type_fichier'] == 'excel/xlsx'])
        user['nombre_documents'] = len([f for f in fichiers if f['type_fichier'] == 'word/docx'])

        # Vérifiez si un chemin de photo de profil existe
        profile_photo = user.get('profile_photo')
        if profile_photo:
            profile_photo_path = os.path.join(UPLOAD_FOLDER_PHOTO, profile_photo)
            # Convertir la photo de profil en base64
            with open(profile_photo_path, "rb") as image_file:
                user['profile_photo'] = b64encode(image_file.read()).decode('utf-8')

    # Calculez les totaux

    total_images = sum(user['nombre_images'] for user in users)
    total_rapports = sum(user['nombre_rapports'] for user in users)
    total_documents = sum(user['nombre_documents'] for user in users)

    return render_template('admin_dashboard.html', users=users, total_images=total_images, total_rapports=total_rapports, total_documents=total_documents)


#super priviléges and there is issue cause u can't delete a row or modify a row cause there is a foreign key
'''''''''''''''
@app3_blueprint.route('/schemas')
def view_schemas():
    query = "SHOW SCHEMAS"
    schemas = execute_query(query, fetchall=True)
    return render_template('schemas.html', schemas=schemas)
'''''''''
@app3_blueprint.route('/tables/<schema_name>')
def view_tables(schema_name):
    query = f"SHOW TABLES IN {schema_name}"
    tables = execute_query(query, fetchall=True)
    return render_template('tables.html', schema_name=schema_name, tables=tables)

@app3_blueprint.route('/table_data/<schema_name>/<table_name>', methods=['GET', 'POST'])
def view_table_data(schema_name, table_name):
    query = f"SELECT * FROM {schema_name}.{table_name}"
    columns = execute_query(f"SHOW COLUMNS FROM {schema_name}.{table_name}", fetchall=True)
    data = execute_query(query, fetchall=True)
    
    if request.method == 'POST':
        if 'delete' in request.form:
            row_id = request.form['delete']
            delete_query = f"DELETE FROM {schema_name}.{table_name} WHERE id = {row_id}"
            execute_query(delete_query)
            return redirect(url_for('view_table_data', schema_name=schema_name, table_name=table_name))
        if 'edit' in request.form:
            row_id = request.form['edit']
            return redirect(url_for('app3.edit_row', schema_name=schema_name, table_name=table_name, row_id=row_id))
        if 'add' in request.form:
            return redirect(url_for('add_row', schema_name=schema_name, table_name=table_name))

    
    return render_template('table_data.html', schema_name=schema_name, table_name=table_name, columns=columns, data=data)

@app3_blueprint.route('/edit_row/<schema_name>/<table_name>/<row_id>', methods=['GET', 'POST'])
def edit_row(schema_name, table_name, row_id):
    query = f"SELECT * FROM {schema_name}.{table_name} WHERE id = {row_id}"
    columns_data = execute_query(f"SHOW COLUMNS FROM {schema_name}.{table_name}", fetchall=True)
    data = execute_query(query, fetchall=True)
    
    if request.method == 'POST':
        update_values = []
        update_query = f"UPDATE {schema_name}.{table_name} SET "
        
        for column_data in columns_data:
            column_name = column_data['Field']
            
            if column_name != 'id':
                update_query += f"{column_name} = %s, "
                update_values.append(request.form.get(column_name))
        
        update_query = update_query[:-2]  # Supprimer la virgule finale et l'espace
        update_query += f" WHERE id = {row_id}"
        
        execute_query(update_query, values=update_values)
        flash("édition terminée")
        return redirect(url_for('app3.view_table_data', schema_name=schema_name, table_name=table_name))
    
    return render_template('edit_row.html', schema_name=schema_name, table_name=table_name, columns_data=columns_data, data=data)

@app3_blueprint.route('/delete_row/<schema_name>/<table_name>/<row_id>', methods=['GET', 'POST'])
def delete_row(schema_name, table_name, row_id):
    if request.method == 'POST':
        # Obtenir le nom de la colonne d'identifiant unique de la table
        query = f"SHOW COLUMNS FROM {schema_name}.{table_name}"
        columns_data = execute_query(query, fetchall=True)
        id_column = None
        for column_data in columns_data:
            if column_data['Key'] == 'PRI':
                id_column = column_data['Field']
                break
        if id_column is not None:
            # Utiliser le nom de la colonne d'identifiant unique dans la requête DELETE
            query = f"DELETE FROM {schema_name}.{table_name} WHERE {id_column} = %s"
            execute_query(query, values=(row_id,))
            return redirect(url_for('app3.view_table_data', schema_name=schema_name, table_name=table_name))
        else:
            flash("Erreur : Impossible de trouver la colonne d'identifiant unique dans la table.")
    else:
        flash('Colonnes supprimées')
        return render_template('delete_row.html', schema_name=schema_name, table_name=table_name, row_id=row_id)

@app3_blueprint.route('/add_row/<schema_name>/<table_name>', methods=['GET', 'POST'])
def add_row(schema_name, table_name):
    columns = execute_query(f"SHOW COLUMNS FROM {schema_name}.{table_name}", fetchall=True)
    if request.method == 'POST':
        insert_values = []
        insert_query = f"INSERT INTO {schema_name}.{table_name} ("
        for column in columns:
            if column['Field'] != 'id':
                insert_query += f"{column['Field']}, "
                if column['Field'] == 'last_login':
                    # Obtenir la date et l'heure actuelles
                    current_datetime = datetime.now()
                    # Formater la date et l'heure dans le format attendu par la base de données
                    formatted_datetime = current_datetime.strftime('%Y-%m-%d %H:%M:%S')
                    insert_values.append(formatted_datetime)
                else:
                    insert_values.append(request.form.get(column['Field']))
        
        insert_query = insert_query[:-2]  # Supprimer la virgule finale et l'espace
        insert_query += ") VALUES ("
        insert_query += "%s, " * (len(insert_values) - 1)
        insert_query += "%s)"
        
        execute_query(insert_query, values=insert_values)
        flash("utilisateur ajouté avec succès")
        return redirect(url_for('app3.view_table_data', schema_name=schema_name, table_name=table_name))
    return render_template('add_row.html', schema_name=schema_name, table_name=table_name, columns=columns)

class RegenerateReportForm(FlaskForm):
       user_email = StringField('E-mail de l\'utilisateur :', validators=[DataRequired()])
       session_id = StringField('ID de session :', validators=[DataRequired()])
       submit = SubmitField('Regénérer le rapport')
       
@app3_blueprint.route('/regenerate_report', methods=['GET', 'POST'])
def regenerate_report():
    
    form = RegenerateReportForm()
    if form.validate_on_submit():
        user_email = form.user_email.data
        session_id = form.session_id.data

        # Vérifiez que l'utilisateur et la session existent dans la base de données
        query = "SELECT * FROM client.user WHERE email = %s"
        user_result = execute_query(query, values=(user_email,), fetchall=True)

        if not user_result:
            flash("L'utilisateur spécifié n'existe pas.")
            return redirect(url_for('app3.admin_dashboard'))

        # Vérifiez si le dossier de l'utilisateur et de la session existe sur le serveur
        user_folder_path = os.path.join(SERVER_FOLDER, user_email)
        session_folder_path = os.path.join(user_folder_path, session_id)

        if not os.path.exists(session_folder_path):
            flash("Le dossier de l'utilisateur et de la session spécifiée n'existe pas.")
            return redirect(url_for('app3.admin_dashboard'))

        # Régénérez le rapp3_blueprintort pour l'utilisateur et la session spécifiés
        generate_report(session_folder_path)
        flash("Le rapport a été régénéré avec succès.")
        return redirect(url_for('app3.admin_dashboard'))
    return render_template('regenerate_report.html', form=form)

@app3_blueprint.errorhandler(404)
def page_not_found(e):
    return render_template('404_admin.html'), 404

@app3_blueprint.errorhandler(403)
def page_not_found(e):
    return render_template('403_admin.html'), 403


