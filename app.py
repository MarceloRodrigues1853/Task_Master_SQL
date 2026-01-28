from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = 'seguranca_marcelo_rodrigues_2026'

# Configuração do Banco de Dados
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- MODELOS ---
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_usuario = db.Column(db.String(80), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    tarefas = db.relationship('Tarefa', backref='autor', lazy=True)

class Tarefa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.String(200), nullable=False)
    feito = db.Column(db.Boolean, default=False)
    data_vencimento = db.Column(db.String(10), nullable=True)
    prioridade = db.Column(db.Integer, default=2)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

with app.app_context():
    db.create_all()

# --- AUXILIARES ---
def obter_stats(user_id):
    tarefas_user = Tarefa.query.filter_by(usuario_id=user_id).all()
    total = len(tarefas_user)
    if total == 0: return 0, 0, 0
    concluidas = len([t for t in tarefas_user if t.feito])
    return total, concluidas, int((concluidas / total) * 100)

# --- ROTAS ---

@app.route('/')
@app.route('/editar/<int:edit_id>')
def index(edit_id=None):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    busca = request.args.get('q', '')
    query = Tarefa.query.filter_by(usuario_id=session['user_id'])
    if busca:
        query = query.filter(Tarefa.texto.contains(busca))
    
    minhas_tarefas = query.order_by(Tarefa.prioridade.desc(), Tarefa.data_vencimento).all()
    _, _, p = obter_stats(session['user_id'])
    return render_template('index.html', tarefas=minhas_tarefas, edit_id=edit_id, progresso=p, busca=busca, tela='app')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome = request.form.get('usuario')
        senha = request.form.get('senha')
        user = Usuario.query.filter_by(nome_usuario=nome).first()
        if user and check_password_hash(user.senha_hash, senha):
            session['user_id'] = user.id
            session['user_nome'] = user.nome_usuario
            return redirect(url_for('index'))
        flash('Acesso negado: Credenciais inválidas.')
    return render_template('index.html', tela='login', progresso=0)

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('usuario')
        senha = request.form.get('senha')
        if Usuario.query.filter_by(nome_usuario=nome).first():
            flash('Usuário já cadastrado.')
        else:
            db.session.add(Usuario(nome_usuario=nome, senha_hash=generate_password_hash(senha)))
            db.session.commit()
            flash('Conta criada! Faça login.')
            return redirect(url_for('login'))
    return render_template('index.html', tela='cadastro', progresso=0)

@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = db.session.get(Usuario, session['user_id'])
    if request.method == 'POST':
        if check_password_hash(user.senha_hash, request.form.get('senha_atual')):
            user.senha_hash = generate_password_hash(request.form.get('nova_senha'))
            db.session.commit()
            flash('Senha atualizada com sucesso.')
        else:
            flash('Senha atual incorreta.')
    t, c, p = obter_stats(session['user_id'])
    return render_template('index.html', tela='perfil', total=t, concluidas=c, progresso=p)

@app.route('/adicionar', methods=['POST'])
def adicionar():
    if 'user_id' in session:
        db.session.add(Tarefa(
            texto=request.form.get('texto_tarefa'),
            data_vencimento=request.form.get('data_vencimento'),
            prioridade=int(request.form.get('prioridade', 2)),
            usuario_id=session['user_id']
        ))
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/completar/<int:id_tarefa>')
def completar(id_tarefa):
    tarefa = db.session.get(Tarefa, id_tarefa)
    if tarefa and tarefa.usuario_id == session.get('user_id'):
        tarefa.feito = True
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/excluir/<int:id_tarefa>')
def excluir(id_tarefa):
    tarefa = db.session.get(Tarefa, id_tarefa)
    if tarefa and tarefa.usuario_id == session.get('user_id'):
        db.session.delete(tarefa)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/atualizar/<int:id_tarefa>', methods=['POST'])
def atualizar(id_tarefa):
    tarefa = db.session.get(Tarefa, id_tarefa)
    if tarefa and tarefa.usuario_id == session.get('user_id'):
        tarefa.texto = request.form.get('novo_texto')
        tarefa.data_vencimento = request.form.get('nova_data')
        tarefa.prioridade = int(request.form.get('nova_prio'))
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)