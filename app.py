import os
import pymysql
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Inicializa o driver MySQL
pymysql.install_as_MySQLdb()

app = Flask(__name__)
# Segurança: Se não houver chave no ambiente, usa um fallback (apenas para dev local)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-local-apenas')

# Configuração de Banco: O Docker passará a URL via ambiente
uri = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELOS SQL ---
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_usuario = db.Column(db.String(80), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    tarefas = db.relationship('Tarefa', backref='autor', lazy=True)

class Tarefa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.String(200), nullable=False)
    feito = db.Column(db.Boolean, default=False)
    prioridade = db.Column(db.Integer, default=2) 
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

with app.app_context():
    db.create_all()

# --- ROTAS ---
@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    busca = request.args.get('q', '')
    query = Tarefa.query.filter_by(usuario_id=session['user_id'])
    if busca: query = query.filter(Tarefa.texto.contains(busca))
    tarefas = query.order_by(Tarefa.prioridade.desc()).all()
    
    total = len(tarefas)
    concluidas = len([t for t in tarefas if t.feito])
    p = int((concluidas / total) * 100) if total > 0 else 0
    return render_template('index.html', tarefas=tarefas, progresso=p, busca=busca, tela='app', nome=session.get('user_nome'))

@app.route('/adicionar', methods=['POST'])
def adicionar():
    if 'user_id' in session:
        db.session.add(Tarefa(texto=request.form.get('texto_tarefa'), 
                             prioridade=int(request.form.get('prioridade', 2)), 
                             usuario_id=session['user_id']))
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    tarefa = db.session.get(Tarefa, id)
    if request.method == 'POST':
        tarefa.texto = request.form.get('texto_tarefa')
        tarefa.prioridade = int(request.form.get('prioridade'))
        db.session.commit()
        return redirect(url_for('index'))
    tarefas = Tarefa.query.filter_by(usuario_id=session['user_id']).all()
    return render_template('index.html', tarefas=tarefas, tarefa_edit=tarefa, tela='app', nome=session.get('user_nome'))

@app.route('/deletar/<int:id>')
def deletar(id):
    t = db.session.get(Tarefa, id)
    if t and t.usuario_id == session.get('user_id'):
        db.session.delete(t)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/completar/<int:id>')
def completar(id):
    t = db.session.get(Tarefa, id)
    if t and t.usuario_id == session.get('user_id'):
        t.feito = not t.feito
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Usuario.query.filter_by(nome_usuario=request.form.get('usuario')).first()
        if user and check_password_hash(user.senha_hash, request.form.get('senha')):
            session['user_id'], session['user_nome'] = user.id, user.nome_usuario
            return redirect(url_for('index'))
        flash('Credenciais inválidas.')
    return render_template('index.html', tela='login')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('usuario')
        if not Usuario.query.filter_by(nome_usuario=nome).first():
            db.session.add(Usuario(nome_usuario=nome, senha_hash=generate_password_hash(request.form.get('senha'))))
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('index.html', tela='cadastro')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)