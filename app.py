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

# --- CONFIGURAÇÕES DE AMBIENTE ---
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-fallback-123')

base_dir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(base_dir, 'database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
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

# --- MOTOR DE BACKUP ---
def enviar_backup():
    user = os.environ.get('EMAIL_USER')
    pwd = os.environ.get('EMAIL_PASS')
    dest = os.environ.get('EMAIL_DESTINO')
    if all([user, pwd, dest]):
        try:
            zip_path = "/tmp/backup_db.zip"
            with zipfile.ZipFile(zip_path, 'w') as z:
                if os.path.exists(db_path): z.write(db_path, arcname="database.db")
            msg = EmailMessage()
            msg['Subject'] = "📦 Backup Automatizado - Task Master SQL"
            msg['From'], msg['To'] = user, dest
            msg.set_content("Backup do banco de dados SQLite.")
            with open(zip_path, 'rb') as f:
                msg.add_attachment(f.read(), maintype='application', subtype='zip', filename="backup.zip")
            with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
                smtp.starttls()
                smtp.login(user, pwd)
                smtp.send_message(msg)
            if os.path.exists(zip_path): os.remove(zip_path)
            return "✅ Backup enviado!"
        except Exception as e: return f"❌ Erro: {str(e)}"
    return "❌ Variáveis ausentes."

scheduler = BackgroundScheduler()
scheduler.add_job(func=enviar_backup, trigger="cron", day_of_week="mon", hour=3)
scheduler.start()

# --- ROTAS ---
@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    busca = request.args.get('q', '')
    query = Tarefa.query.filter_by(usuario_id=session['user_id'])
    if busca: query = query.filter(Tarefa.texto.contains(busca))
    tarefas = query.order_by(Tarefa.prioridade.desc(), Tarefa.data_vencimento).all()
    
    total = len(tarefas)
    concluidas = len([t for t in tarefas if t.feito])
    p = int((concluidas / total) * 100) if total > 0 else 0
    return render_template('index.html', tarefas=tarefas, progresso=p, busca=busca, tela='app', nome=session.get('user_nome'))

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    tarefa = db.session.get(Tarefa, id)
    
    if request.method == 'POST':
        tarefa.texto = request.form.get('texto_tarefa')
        tarefa.data_vencimento = request.form.get('data_vencimento')
        tarefa.prioridade = int(request.form.get('prioridade'))
        db.session.commit()
        return redirect(url_for('index'))
    
    # Se for GET, recarrega a página mas com os dados da tarefa no formulário
    query = Tarefa.query.filter_by(usuario_id=session['user_id'])
    tarefas = query.order_by(Tarefa.prioridade.desc()).all()
    return render_template('index.html', tarefas=tarefas, tarefa_edit=tarefa, tela='app', nome=session.get('user_nome'))

@app.route('/adicionar', methods=['POST'])
def adicionar():
    if 'user_id' in session:
        db.session.add(Tarefa(texto=request.form.get('texto_tarefa'), data_vencimento=request.form.get('data_vencimento'),
                             prioridade=int(request.form.get('prioridade', 2)), usuario_id=session['user_id']))
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/completar/<int:id>')
def completar(id):
    t = db.session.get(Tarefa, id)
    if t and t.usuario_id == session.get('user_id'):
        t.feito = not t.feito # Alterna entre feito e não feito
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/deletar/<int:id>')
def deletar(id):
    t = db.session.get(Tarefa, id)
    if t and t.usuario_id == session.get('user_id'):
        db.session.delete(t)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/admin-dashboard')
def admin():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('index.html', tela='admin', u_count=Usuario.query.count(), t_count=Tarefa.query.count(), c_count=Tarefa.query.filter_by(feito=True).count())

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

@app.route('/backup-manual')
def backup_manual(): return enviar_backup()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)