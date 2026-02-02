import os
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_key")

# =========================
# DADOS MOCK (temporários)
# =========================
tarefas_mock = []
contador_id = 1

# =========================
# ROTAS PRINCIPAIS
# =========================
@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))

    total = len(tarefas_mock)
    concluidas = len([t for t in tarefas_mock if t["feito"]])
    progresso = int((concluidas / total) * 100) if total > 0 else 0

    return render_template(
        "index.html",
        tela="app",
        nome=session["user"],
        tarefas=tarefas_mock,
        progresso=progresso,
        tarefa_edit=None
    )

# =========================
# CRUD DE TAREFAS (SIMULADO)
# =========================
@app.route("/adicionar", methods=["POST"])
def adicionar():
    global contador_id
    tarefas_mock.append({
        "id": contador_id,
        "texto": request.form.get("texto_tarefa"),
        "prioridade": int(request.form.get("prioridade")),
        "feito": False
    })
    contador_id += 1
    return redirect(url_for("index"))

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    tarefa = next((t for t in tarefas_mock if t["id"] == id), None)

    if request.method == "POST":
        tarefa["texto"] = request.form.get("texto_tarefa")
        tarefa["prioridade"] = int(request.form.get("prioridade"))
        return redirect(url_for("index"))

    total = len(tarefas_mock)
    concluidas = len([t for t in tarefas_mock if t["feito"]])
    progresso = int((concluidas / total) * 100) if total > 0 else 0

    return render_template(
        "index.html",
        tela="app",
        nome=session["user"],
        tarefas=tarefas_mock,
        progresso=progresso,
        tarefa_edit=tarefa
    )

@app.route("/deletar/<int:id>")
def deletar(id):
    global tarefas_mock
    tarefas_mock = [t for t in tarefas_mock if t["id"] != id]
    return redirect(url_for("index"))

@app.route("/completar/<int:id>")
def completar(id):
    tarefa = next((t for t in tarefas_mock if t["id"] == id), None)
    if tarefa:
        tarefa["feito"] = not tarefa["feito"]
    return redirect(url_for("index"))

# =========================
# LOGIN / CADASTRO (SIMPLES)
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["user"] = request.form.get("usuario")
        return redirect(url_for("index"))
    return render_template("index.html", tela="login")

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        session["user"] = request.form.get("usuario")
        return redirect(url_for("index"))
    return render_template("index.html", tela="cadastro")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# =========================
# START
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
