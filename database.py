import os
import sqlite3
import pymysql
import pymysql.cursors
from urllib.parse import urlparse
from werkzeug.security import generate_password_hash, check_password_hash

def get_db():
    host = os.environ.get("DB_HOST")
    if host:
        return pymysql.connect(
            host=host, port=int(os.environ.get("DB_PORT", 4000)),
            user=os.environ.get("DB_USER"), password=os.environ.get("DB_PASSWORD"),
            database=os.environ.get("DB_NAME"), cursorclass=pymysql.cursors.DictCursor,
            ssl={'ca': os.environ.get("DB_SSL_CA")}
        )
    
    db_url = os.environ.get("DATABASE_URL")
    if db_url and "mysql" in db_url:
        url = urlparse(db_url)
        return pymysql.connect(
            host=url.hostname, port=url.port or 3306, user=url.username,
            password=url.password, database=url.path.lstrip('/'),
            cursorclass=pymysql.cursors.DictCursor
        )

    basedir = os.path.abspath(os.path.dirname(__file__))
    conn = sqlite3.connect(os.path.join(basedir, "database.db"))
    conn.row_factory = sqlite3.Row
    return conn

def get_ph():
    is_mysql = (os.environ.get("DB_HOST") is not None) or (os.environ.get("DATABASE_URL") is not None and "mysql" in os.environ.get("DATABASE_URL"))
    return "%s" if is_mysql else "?"

# Funções de Autenticação Segura
def criar_usuario(usuario, senha):
    db = get_db()
    cursor = db.cursor()
    ph = get_ph()
    senha_hash = generate_password_hash(senha)
    cursor.execute(f"INSERT INTO usuarios (usuario, senha) VALUES ({ph}, {ph})", (usuario, senha_hash))
    if hasattr(db, 'commit'): db.commit()
    db.close()

def validar_login(usuario, senha):
    db = get_db()
    cursor = db.cursor()
    ph = get_ph()
    cursor.execute(f"SELECT * FROM usuarios WHERE usuario = {ph}", (usuario,))
    user = cursor.fetchone()
    db.close()
    if user and check_password_hash(user["senha"], senha):
        return user
    return None