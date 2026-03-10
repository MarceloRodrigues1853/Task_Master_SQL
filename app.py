import os
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from database import get_db, get_ph, criar_usuario, validar_login

# Carrega configurações do arquivo .env
load_dotenv()

app = Flask(__name__)
# Dica: Coloque uma chave secreta real no seu arquivo .env
app.secret_key = os.environ.get("SECRET_KEY", "uma_chave_bem_secreta_aqui")

# ---------- ROTAS DE AUTENTICAÇÃO ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = validar_login(request.form["usuario"], request.form["senha"])
        if user:
            session["usuario"] = user["usuario"]
            return redirect(url_for("index"))
    return render_template("index.html", tela="login")

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        criar_usuario(request.form["usuario"], request.form["senha"])
        session["usuario"] = request.form["usuario"]
        return redirect(url_for("index"))
    return render_template("index.html", tela="cadastro")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------- ROTAS PRINCIPAIS ----------

@app.route("/")
def index():
    if "usuario" not in session: 
        return redirect(url_for("login"))
    
    db = get_db(); cursor = db.cursor(); ph = get_ph()
    busca = request.args.get('busca', '')
    
    sql = f"SELECT * FROM tarefas WHERE usuario = {ph}"
    params = [session["usuario"]]
    if busca:
        sql += " AND texto LIKE %s" if ph == "%s" else " AND texto LIKE ?"
        params.append(f"%{busca}%")
    
    sql += " ORDER BY feito ASC, data_vencimento ASC, prioridade DESC"
    cursor.execute(sql, tuple(params))
    tarefas = cursor.fetchall()
    
    # Cálculo de progresso
    total = len(tarefas)
    feitas = len([t for t in tarefas if t["feito"] in [1, True]])
    progresso = int((feitas / total) * 100) if total > 0 else 0
    
    db.close()
    return render_template("index.html", tela="app", nome=session["usuario"], 
                           tarefas=tarefas, progresso=progresso, 
                           tarefa_edit=None, busca=busca)

@app.route("/adicionar", methods=["POST"])
def adicionar():
    if "usuario" not in session: return redirect(url_for("login"))
    db = get_db(); cursor = db.cursor(); ph = get_ph()
    data_v = request.form.get("data_vencimento") or None
    
    cursor.execute(f"INSERT INTO tarefas (texto, prioridade, feito, usuario, data_vencimento) VALUES ({ph}, {ph}, 0, {ph}, {ph})", 
                   (request.form["texto_tarefa"], request.form["prioridade"], session["usuario"], data_v))
    
    if hasattr(db, 'commit'): db.commit()
    db.close(); return redirect(url_for("index"))

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    if "usuario" not in session: return redirect(url_for("login"))
    db = get_db(); cursor = db.cursor(); ph = get_ph()
    
    if request.method == "POST":
        data_v = request.form.get("data_vencimento") or None
        cursor.execute(f"UPDATE tarefas SET texto = {ph}, prioridade = {ph}, data_vencimento = {ph} WHERE id = {ph} AND usuario = {ph}",
                       (request.form["texto_tarefa"], request.form["prioridade"], data_v, id, session["usuario"]))
        if hasattr(db, 'commit'): db.commit()
        db.close(); return redirect(url_for("index"))
    
    cursor.execute(f"SELECT * FROM tarefas WHERE id = {ph} AND usuario = {ph}", (id, session["usuario"]))
    tarefa = cursor.fetchone(); db.close()
    return render_template("index.html", tela="app", nome=session["usuario"], tarefas=[], progresso=0, tarefa_edit=tarefa)

@app.route("/completar/<int:id>")
def completar(id):
    if "usuario" not in session: return redirect(url_for("login"))
    db = get_db(); cursor = db.cursor(); ph = get_ph()
    cursor.execute(f"UPDATE tarefas SET feito = 1 WHERE id = {ph} AND usuario = {ph}", (id, session["usuario"]))
    if hasattr(db, 'commit'): db.commit()
    db.close(); return redirect(url_for("index"))

@app.route("/deletar/<int:id>")
def deletar(id):
    if "usuario" not in session: return redirect(url_for("login"))
    db = get_db(); cursor = db.cursor(); ph = get_ph()
    cursor.execute(f"DELETE FROM tarefas WHERE id = {ph} AND usuario = {ph}", (id, session["usuario"]))
    if hasattr(db, 'commit'): db.commit()
    db.close(); return redirect(url_for("index"))

if __name__ == "__main__":
    # IMPORTANTE: Em produção, mude para debug=False
    app.run(debug=True)