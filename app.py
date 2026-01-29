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

# --- CIBERSEGURANÇA E AMBIENTE ---
# Busca as variáveis configuradas no painel do Render
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-padrao-123')

base_dir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(base_dir, 'database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- MODELOS (Estrutura de Dados SQL) ---
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

# --- INICIALIZAÇÃO DO BANCO (Crucial para o Render) ---
# Garante que as tabelas existam sem depender do 'if __name__'
with app.app_context():
    db.create_all()

# --- MOTOR DE BACKUP AUTOMÁTICO ---
def enviar_backup():
    user = os.environ.get('EMAIL_USER')
    password = os.environ.get('EMAIL_PASS')
    destino = os.environ.get('EMAIL_DESTINO')

    if not all([user, password, destino]):
        return "❌ Erro: Variáveis de ambiente de e-mail ausentes."

    try:
        # Usamos /tmp/ para evitar erros de permissão de escrita no Render
        zip_path = "/tmp/backup_database.zip"
        
        with zipfile.ZipFile(zip_path, 'w') as z:
            if os.path.exists(db_path):
                z.write(db_path, arcname="database.db")
        
        msg = EmailMessage()
        msg['Subject'] = "📦 Backup Automatizado - Task Master SQL"
        msg['From'] = user
        msg['To'] = destino
        msg.set_content(f"Segue anexo o backup do banco de dados SQLite.")

        with open(zip_path, 'rb') as f:
            msg.add_attachment(f.read(), maintype='application', subtype='zip', filename="backup.zip")

        # Conexão via TLS (Porta 587) para maior compatibilidade com a nuvem
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls() 
            smtp.login(user, password)
            smtp.send_message(msg)
        
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return "✅ Sucesso! O arquivo ZIP foi enviado."

    except Exception as e:
        return f"❌ Erro Técnico: {str(e)}"

# Agendador: executa toda segunda-feira às 03:00h
scheduler = BackgroundScheduler()
scheduler.add_job(func=enviar_backup, trigger="cron", day_of_week="mon", hour=3)
scheduler.start()

# --- ROTAS DE NAVEGAÇÃO ---

@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    busca = request.args.get('q', '')
    query = Tarefa.query.filter_by(usuario_id=session['user_id'])
    if busca:
        query = query.filter(Tarefa.texto.contains(busca))
    
    minhas_tarefas = query.order_by(Tarefa.prioridade.desc(), Tarefa.data_vencimento).all()
    
    # Cálculo de Progresso
    total = len(minhas_tarefas)
    concluidas = len([t for t in minhas_tarefas if t.feito])
    p = int((concluidas / total) * 100) if total > 0 else 0
    
    return render_template('index.html', tarefas=minhas_tarefas, progresso=p, busca=busca, tela='app')

@app.route('/admin-dashboard')
def admin():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    u_count = Usuario.query.count()
    t_count = Tarefa.query.count()
    c_count = Tarefa.query.filter_by(feito=True).count()
    
    return render_template('index.html', tela='admin', u_count=u_count, t_count=t_count, c_count=c_count)

@app.route('/backup-manual')
def backup_manual():
    # Rota secreta para validar as variáveis de ambiente agora mesmo
    resultado = enviar_backup()
    return resultado

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
    # Uso do db.session.get para evitar avisos de código legado
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