import os
import sqlite3
import pymysql
import pymysql.cursors
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave_mestra_local_123")

def get_db():
    db_url = os.environ.get("DATABASE_URL")
    
    if db_url and "mysql" in db_url:
        try:
            # Forma robusta de extrair dados da URL do Render
            url = urlparse(db_url)
            return pymysql.connect(
                host=url.hostname,
                port=url.port or 3306,
                user=url.username,
                password=url.password,
                database=url.path.lstrip('/'),
                cursorclass=pymysql.cursors.DictCursor,
                ssl={'ca': '/etc/ssl/certs/ca-certificates.crt'}
            )
        except Exception as e:
            print(f"Erro na conexão remota: {e}")

    # Fallback para Local (SQLite)
    basedir = os.path.abspath(os.path.dirname(__file__))
    conn = sqlite3.connect(os.path.join(basedir, "database.db"))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    cursor = db.cursor()
    
    is_mysql = os.environ.get("DATABASE_URL") and "mysql" in os.environ.get("DATABASE_URL")
    pk_style = "INTEGER PRIMARY KEY AUTO_INCREMENT" if is_mysql else "INTEGER PRIMARY KEY AUTOINCREMENT"
    text_type = "VARCHAR(255)" if is_mysql else "TEXT"

    # Criar tabelas se não existirem
    cursor.execute(f"CREATE TABLE IF NOT EXISTS usuarios (id {pk_style})")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS tarefas (id {pk_style})")
    
    # Se estiver no MySQL/TiDB, garantir que as colunas existam (Add Column if not exists)
    if is_mysql:
        # Colunas para usuarios
        for col, spec in [("usuario", "VARCHAR(100)"), ("senha", "VARCHAR(100)")]:
            try:
                cursor.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {spec}")
            except: pass # Ignora se a coluna já existir
            
        # Colunas para tarefas
        for col, spec in [("texto", "TEXT"), ("prioridade", "INTEGER"), 
                          ("feito", "INTEGER DEFAULT 0"), ("usuario", "VARCHAR(100)")]:
            try:
                cursor.execute(f"ALTER TABLE tarefas ADD COLUMN {col} {spec}")
            except: pass # Ignora se a coluna já existir
    else:
        # No SQLite local, é mais fácil recriar ou apenas garantir a criação inicial
        cursor.execute(f"""CREATE TABLE IF NOT EXISTS usuarios (
            id {pk_style}, usuario VARCHAR(100), senha VARCHAR(100)
        )""")
        cursor.execute(f"""CREATE TABLE IF NOT EXISTS tarefas (
            id {pk_style}, texto TEXT, prioridade INTEGER, feito INTEGER DEFAULT 0, usuario VARCHAR(100)
        )""")
    
    if hasattr(db, 'commit'): db.commit()
    db.close()

with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f"Aviso ao iniciar banco: {e}")

# Helper para placeholders de SQL
def get_ph():
    return "%s" if os.environ.get("DATABASE_URL") and "mysql" in os.environ.get("DATABASE_URL") else "?"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()
        ph = get_ph()
        cursor.execute(f"SELECT * FROM usuarios WHERE usuario = {ph} AND senha = {ph}", 
                       (request.form["usuario"], request.form["senha"]))
        user = cursor.fetchone()
        db.close()
        if user:
            session["usuario"] = request.form["usuario"]
            return redirect(url_for("index"))
    return render_template("index.html", tela="login")

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()
        ph = get_ph()
        cursor.execute(f"INSERT INTO usuarios (usuario, senha) VALUES ({ph}, {ph})", 
                       (request.form["usuario"], request.form["senha"]))
        if hasattr(db, 'commit'): db.commit()
        db.close()
        session["usuario"] = request.form["usuario"]
        return redirect(url_for("index"))
    return render_template("index.html", tela="cadastro")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def index():
    if "usuario" not in session: return redirect(url_for("login"))
    db = get_db()
    cursor = db.cursor()
    ph = get_ph()
    cursor.execute(f"SELECT * FROM tarefas WHERE usuario = {ph} ORDER BY feito ASC, prioridade DESC", (session["usuario"],))
    tarefas = cursor.fetchall()
    total = len(tarefas)
    feitas = len([t for t in tarefas if t["feito"] in [1, True]])
    progresso = int((feitas / total) * 100) if total > 0 else 0
    db.close()
    return render_template("index.html", tela="app", nome=session["usuario"], tarefas=tarefas, progresso=progresso, tarefa_edit=None)

@app.route("/adicionar", methods=["POST"])
def adicionar():
    db = get_db()
    cursor = db.cursor()
    ph = get_ph()
    cursor.execute(f"INSERT INTO tarefas (texto, prioridade, feito, usuario) VALUES ({ph}, {ph}, 0, {ph})", 
                   (request.form["texto_tarefa"], request.form["prioridade"], session["usuario"]))
    if hasattr(db, 'commit'): db.commit()
    db.close()
    return redirect(url_for("index"))

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    db = get_db()
    cursor = db.cursor()
    ph = get_ph()
    if request.method == "POST":
        cursor.execute(f"UPDATE tarefas SET texto = {ph}, prioridade = {ph} WHERE id = {ph} AND usuario = {ph}",
                       (request.form["texto_tarefa"], request.form["prioridade"], id, session["usuario"]))
        if hasattr(db, 'commit'): db.commit()
        db.close()
        return redirect(url_for("index"))
    cursor.execute(f"SELECT * FROM tarefas WHERE id = {ph} AND usuario = {ph}", (id, session["usuario"]))
    tarefa = cursor.fetchone()
    db.close()
    return render_template("index.html", tela="app", nome=session["usuario"], tarefas=[], progresso=0, tarefa_edit=tarefa)

@app.route("/completar/<int:id>")
def completar(id):
    db = get_db()
    cursor = db.cursor()
    ph = get_ph()
    cursor.execute(f"UPDATE tarefas SET feito = 1 WHERE id = {ph} AND usuario = {ph}", (id, session["usuario"]))
    if hasattr(db, 'commit'): db.commit()
    db.close()
    return redirect(url_for("index"))

@app.route("/deletar/<int:id>")
def deletar(id):
    db = get_db()
    cursor = db.cursor()
    ph = get_ph()
    cursor.execute(f"DELETE FROM tarefas WHERE id = {ph} AND usuario = {ph}", (id, session["usuario"]))
    if hasattr(db, 'commit'): db.commit()
    db.close()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)