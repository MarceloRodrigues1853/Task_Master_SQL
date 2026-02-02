import os
import sqlite3
import pymysql
import pymysql.cursors
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
# Usa a SECRET_KEY do Render ou uma padrão para desenvolvimento local
app.secret_key = os.environ.get("SECRET_KEY", "chave_mestra_local_123")

# ---------- CONEXÃO HÍBRIDA (LOCAL / NUVEM) ----------
def get_db():
    db_url = os.environ.get("DATABASE_URL")
    
    if db_url:
        # Configuração para o Render (TiDB / MySQL)
        # Exemplo de URL: mysql+pymysql://user:pass@host:port/dbname
        try:
            # Remove o prefixo do SQLAlchemy para o PyMySQL
            limpo = db_url.replace("mysql+pymysql://", "")
            user_pass, resto = limpo.split("@")
            usuario, senha = user_pass.split(":")
            host_porto, db_nome_com_query = resto.split("/")
            host, porto = host_porto.split(":")
            db_nome = db_nome_com_query.split("?")[0]
            
            return pymysql.connect(
                host=host,
                port=int(porto),
                user=usuario,
                password=senha,
                database=db_nome,
                cursorclass=pymysql.cursors.DictCursor,
                ssl={'ca': '/etc/ssl/certs/ca-certificates.crt'} # Caminho padrão no Render
            )
        except Exception as e:
            print(f"Erro na conexão remota: {e}")

    # Configuração para Local (SQLite)
    basedir = os.path.abspath(os.path.dirname(__file__))
    conn = sqlite3.connect(os.path.join(basedir, "database.db"))
    conn.row_factory = sqlite3.Row
    return conn

# ---------- INICIALIZAÇÃO DO BANCO ----------
def init_db():
    db = get_db()
    cursor = db.cursor()
    
    # Diferenciação de sintaxe para evitar o erro OperationalError no SQLite
    is_mysql = os.environ.get("DATABASE_URL") is not None
    pk_style = "INTEGER PRIMARY KEY AUTO_INCREMENT" if is_mysql else "INTEGER PRIMARY KEY AUTOINCREMENT"

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS usuarios (
        id {pk_style},
        usuario VARCHAR(100) NOT NULL,
        senha VARCHAR(100) NOT NULL
    )""")
    
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS tarefas (
        id {pk_style},
        texto TEXT NOT NULL,
        prioridade INTEGER,
        feito INTEGER DEFAULT 0,
        usuario VARCHAR(100)
    )""")
    
    if hasattr(db, 'commit'):
        db.commit()
    db.close()

# Inicializa o banco ao abrir o app
with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f"Aviso ao iniciar banco: {e}")

# ---------- ROTAS ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario, senha = request.form["usuario"], request.form["senha"]
        db = get_db()
        cursor = db.cursor()
        
        # Ajuste de placeholders (%s para MySQL, ? para SQLite)
        sql = "SELECT * FROM usuarios WHERE usuario = %s AND senha = %s" if os.environ.get("DATABASE_URL") else \
              "SELECT * FROM usuarios WHERE usuario = ? AND senha = ?"
        
        cursor.execute(sql, (usuario, senha))
        user = cursor.fetchone()
        db.close()

        if user:
            session["usuario"] = usuario
            return redirect(url_for("index"))
    return render_template("index.html", tela="login")

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        usuario, senha = request.form["usuario"], request.form["senha"]
        db = get_db()
        cursor = db.cursor()
        sql = "INSERT INTO usuarios (usuario, senha) VALUES (%s, %s)" if os.environ.get("DATABASE_URL") else \
              "INSERT INTO usuarios (usuario, senha) VALUES (?, ?)"
        cursor.execute(sql, (usuario, senha))
        if hasattr(db, 'commit'): db.commit()
        db.close()
        session["usuario"] = usuario
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
    sql = "SELECT * FROM tarefas WHERE usuario = %s ORDER BY feito ASC, prioridade DESC" if os.environ.get("DATABASE_URL") else \
          "SELECT * FROM tarefas WHERE usuario = ? ORDER BY feito ASC, prioridade DESC"
    cursor.execute(sql, (session["usuario"],))
    tarefas = cursor.fetchall()
    
    total = len(tarefas)
    feitas = len([t for t in tarefas if t["feito"] == 1 or t["feito"] is True])
    progresso = int((feitas / total) * 100) if total > 0 else 0
    db.close()
    return render_template("index.html", tela="app", nome=session["usuario"], tarefas=tarefas, progresso=progresso, tarefa_edit=None)

@app.route("/adicionar", methods=["POST"])
def adicionar():
    if "usuario" not in session: return redirect(url_for("login"))
    db = get_db()
    cursor = db.cursor()
    sql = "INSERT INTO tarefas (texto, prioridade, feito, usuario) VALUES (%s, %s, 0, %s)" if os.environ.get("DATABASE_URL") else \
          "INSERT INTO tarefas (texto, prioridade, feito, usuario) VALUES (?, ?, 0, ?)"
    cursor.execute(sql, (request.form["texto_tarefa"], request.form["prioridade"], session["usuario"]))
    if hasattr(db, 'commit'): db.commit()
    db.close()
    return redirect(url_for("index"))

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    if "usuario" not in session: return redirect(url_for("login"))
    db = get_db()
    cursor = db.cursor()
    placeholder = "%s" if os.environ.get("DATABASE_URL") else "?"

    if request.method == "POST":
        sql = f"UPDATE tarefas SET texto = {placeholder}, prioridade = {placeholder} WHERE id = {placeholder} AND usuario = {placeholder}"
        cursor.execute(sql, (request.form["texto_tarefa"], request.form["prioridade"], id, session["usuario"]))
        if hasattr(db, 'commit'): db.commit()
        db.close()
        return redirect(url_for("index"))

    sql_select = f"SELECT * FROM tarefas WHERE id = {placeholder} AND usuario = {placeholder}"
    cursor.execute(sql_select, (id, session["usuario"]))
    tarefa = cursor.fetchone()
    
    # Busca a lista para manter o fundo da página preenchido
    sql_list = f"SELECT * FROM tarefas WHERE usuario = {placeholder} ORDER BY feito ASC, prioridade DESC"
    cursor.execute(sql_list, (session["usuario"],))
    tarefas = cursor.fetchall()
    
    total = len(tarefas)
    feitas = len([t for t in tarefas if t["feito"] == 1 or t["feito"] is True])
    progresso = int((feitas / total) * 100) if total > 0 else 0
    
    db.close()
    return render_template("index.html", tela="app", nome=session["usuario"], tarefas=tarefas, progresso=progresso, tarefa_edit=tarefa)

@app.route("/completar/<int:id>")
def completar(id):
    if "usuario" not in session: return redirect(url_for("login"))
    db = get_db()
    cursor = db.cursor()
    placeholder = "%s" if os.environ.get("DATABASE_URL") else "?"
    cursor.execute(f"UPDATE tarefas SET feito = 1 WHERE id = {placeholder} AND usuario = {placeholder}", (id, session["usuario"]))
    if hasattr(db, 'commit'): db.commit()
    db.close()
    return redirect(url_for("index"))

@app.route("/deletar/<int:id>")
def deletar(id):
    if "usuario" not in session: return redirect(url_for("login"))
    db = get_db()
    cursor = db.cursor()
    placeholder = "%s" if os.environ.get("DATABASE_URL") else "?"
    cursor.execute(f"DELETE FROM tarefas WHERE id = {placeholder} AND usuario = {placeholder}", (id, session["usuario"]))
    if hasattr(db, 'commit'): db.commit()
    db.close()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)