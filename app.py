import os
import zipfile
import smtplib
from email.message import EmailMessage
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# --- CONFIGURAÇÕES DE SEGURANÇA E AMBIENTE ---
# Busca as chaves configuradas no painel do Render
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-fallback-123')

base_dir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(base_dir, 'database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- MODELOS DO BANCO DE DADOS ---
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
    prioridade = db.Column(db.Integer, default=2) # 3:Urgente, 2:Normal, 1:Baixa
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

# --- CORREÇÃO PARA O RENDER: GARANTIR CRIAÇÃO DO BANCO ---
# Essencial para evitar o Erro 500 no primeiro deploy
with app.app_context():
    db.create_all()

# --- SISTEMA DE BACKUP AUTOMÁTICO ---
def enviar_backup():
    user = os.environ.get('EMAIL_USER')
    password = os.environ.get('EMAIL_PASS')
    destino = os.environ.get('EMAIL_DESTINO')

    if all([user, password, destino]):
        try:
            zip_name = "backup_database.zip"
            with zipfile.ZipFile(zip_name, 'w') as z:
                if os.path.exists(db_path):
                    z.write(db_path, arcname="database.db")
            
            msg = EmailMessage()
            msg['Subject'] = f"📦 Backup Task Master SQL - Produção"
            msg['From'] = user
            msg['To'] = destino
            msg.set_content("Backup automatizado do banco de dados SQLite.")

            with open(zip_name, 'rb') as f:
                msg.add_attachment(f.read(), maintype='application', subtype='zip', filename=zip_name)

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(user, password)
                smtp.send_message(msg)
            
            os.remove(zip_name)
            print("✅ Backup enviado com sucesso.")
        except Exception as e:
            print(f"❌ Erro no backup: {e}")

# Agendador: executa toda segunda-feira às 03:00h
scheduler = BackgroundScheduler()
scheduler.add_job(func=enviar_backup, trigger="cron", day_of_week="mon", hour=3)
scheduler.start()

# --- ROTAS PRINCIPAIS ---

@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    # Sistema de Busca
    busca = request.args.get('q', '')
    query = Tarefa.query.filter_by(usuario_id=session['user_id'])
    if busca:
        query = query.filter(Tarefa.texto.contains(busca))
    
    minhas_tarefas = query.order_by(Tarefa.prioridade.desc(), Tarefa.data_vencimento).all()
    
    # Estatísticas e Progresso
    total = len(minhas_tarefas)
    concluidas = len([t for t in minhas_tarefas if t.feito])
    p = int((concluidas / total) * 100) if total > 0 else 0
    
    return render_template('index.html', tarefas=minhas_tarefas, progresso=p, busca=busca, tela='app')

@app.route('/admin-dashboard')
def admin():
    # Rota visualizada com sucesso localmente
    if 'user_id' not in session: return redirect(url_for('login'))
    
    total_u = Usuario.query.count()
    total_t = Tarefa.query.count()
    concluidas = Tarefa.query.filter_by(feito=True).count()
    
    return render_template('index.html', tela='admin', u_count=total_u, t_count=total_t, c_count=concluidas)

@app.route('/backup-manual')
def backup_manual():
    # Rota secreta para testar se as variáveis de e-mail estão certas
    enviar_backup()
    return "Processo de backup disparado! Verifique seu e-mail."

# --- AUTENTICAÇÃO E CRUD ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Usuario.query.filter_by(nome_usuario=request.form.get('usuario')).first()
        if user and check_password_hash(user.senha_hash, request.form.get('senha')):
            session['user_id'] = user.id
            session['user_nome'] = user.nome_usuario
            return redirect(url_for('index'))
        flash('Usuário ou senha inválidos.')
    return render_template('index.html', tela='login')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('usuario')
        if Usuario.query.filter_by(nome_usuario=nome).first():
            flash('Usuário já existe.')
        else:
            db.session.add(Usuario(nome_usuario=nome, senha_hash=generate_password_hash(request.form.get('senha'))))
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('index.html', tela='cadastro')

@app.route('/adicionar', methods=['POST'])
def adicionar():
    if 'user_id' in session:
        nova = Tarefa(
            texto=request.form.get('texto_tarefa'),
            data_vencimento=request.form.get('data_vencimento'),
            prioridade=int(request.form.get('prioridade', 2)),
            usuario_id=session['user_id']
        )
        db.session.add(nova)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/completar/<int:id>')
def completar(id):
    # Uso do db.session.get para evitar LegacyAPIWarning
    t = db.session.get(Tarefa, id)
    if t and t.usuario_id == session.get('user_id'):
        t.feito = True
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)