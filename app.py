import os
import pymysql
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

# =========================
# Configurações iniciais
# =========================
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave-padrao")

# =========================
# Conexão com o TiDB Cloud
# =========================
def get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        ssl={"ca": os.getenv("DB_SSL_CA")},
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

# =========================
# Inicialização do banco
# =========================
def init_db():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome_usuario VARCHAR(80) UNIQUE NOT NULL,
                senha_hash VARCHAR(200) NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tarefas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                texto VARCHAR(200) NOT NULL,
                feito BOOLEAN DEFAULT FALSE,
                prioridade INT DEFAULT 2,
                usuario_id INT,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        """)
    conn.close()

init_db()

# =========================
# ROTAS WEB
# =========================
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM tarefas WHERE usuario_id=%s ORDER BY prioridade DESC",
            (session["user_id"],)
        )
        tarefas = cursor.fetchall()
    conn.close()

    total = len(tarefas)
    concluidas = len([t for t in tarefas if t["feito"]])
    progresso = int((concluidas / total) * 100) if total else 0

    return render_template(
        "index.html",
        tarefas=tarefas,
        progresso=progresso,
        tela="app",
        nome=session.get("user_nome")
    )

# =========================
# TAREFAS
# =========================
@app.route("/adicionar", methods=["POST"])
def adicionar():
    if "user_id" not in session:
        return redirect(url_for("login"))

    texto = request.form.get("texto_tarefa")
    prioridade = int(request.form.get("prioridade", 2))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO tarefas (texto, prioridade, usuario_id) VALUES (%s, %s, %s)",
            (texto, prioridade, session["user_id"])
        )
    conn.close()
    return redirect(url_for("index"))

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        if request.method == "POST":
            cursor.execute(
                "UPDATE tarefas SET texto=%s, prioridade=%s WHERE id=%s AND usuario_id=%s",
                (
                    request.form.get("texto_tarefa"),
                    int(request.form.get("prioridade")),
                    id,
                    session["user_id"]
                )
            )
            conn.close()
            return redirect(url_for("index"))

        cursor.execute(
            "SELECT * FROM tarefas WHERE id=%s AND usuario_id=%s",
            (id, session["user_id"])
        )
        tarefa_edit = cursor.fetchone()

        cursor.execute(
            "SELECT * FROM tarefas WHERE usuario_id=%s ORDER BY prioridade DESC",
            (session["user_id"],)
        )
        tarefas = cursor.fetchall()

    conn.close()

    return render_template(
        "index.html",
        tarefas=tarefas,
        tarefa_edit=tarefa_edit,
        tela="app",
        nome=session.get("user_nome"),
        progresso=0
    )

@app.route("/completar/<int:id>")
def completar(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE tarefas SET feito = NOT feito WHERE id=%s AND usuario_id=%s",
            (id, session["user_id"])
        )
    conn.close()
    return redirect(url_for("index"))

@app.route("/deletar/<int:id>")
def deletar(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM tarefas WHERE id=%s AND usuario_id=%s",
            (id, session["user_id"])
        )
    conn.close()
    return redirect(url_for("index"))

# =========================
# LOGIN / CADASTRO
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        senha = request.form.get("senha")

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM usuarios WHERE nome_usuario=%s",
                (usuario,)
            )
            user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["senha_hash"], senha):
            session["user_id"] = user["id"]
            session["user_nome"] = user["nome_usuario"]
            return redirect(url_for("index"))

        flash("Usuário ou senha inválidos")

    return render_template("index.html", tela="login")

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        senha = generate_password_hash(request.form.get("senha"))

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO usuarios (nome_usuario, senha_hash) VALUES (%s, %s)",
                    (usuario, senha)
                )
        except Exception:
            flash("Usuário já existe")
            conn.close()
            return redirect(url_for("cadastro"))

        conn.close()
        return redirect(url_for("login"))

    return render_template("index.html", tela="cadastro")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# =========================
# ROTA TÉCNICA (API)
# =========================
@app.route("/db-test")
def db_test():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS db, VERSION() AS version")
            r = cursor.fetchone()
        conn.close()
        return jsonify({"conectado": True, **r})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# =========================
# RUN
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
