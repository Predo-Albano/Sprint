from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'chave_secreta'  # Altere para uma chave segura
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///banco.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Classe Observer
class Observer:
    def update(self, message):
        raise NotImplementedError("Método 'update' não implementado.")

# Modelo de Usuário (Factory Method)
class UsuarioFactory:
    @staticmethod
    def create_usuario(nome, email, senha, is_admin=False):
        if is_admin:
            return Admin(nome, email, senha)
        else:
            return Usuario(nome, email, senha)

# Modelo de Usuário Comum
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def __init__(self, nome, email, senha, is_admin=False):
        self.nome = nome
        self.email = email
        self.senha = senha
        self.is_admin = is_admin

# Modelo de Admin (Observer)
class Admin(Usuario, Observer):
    def __init__(self, nome, email, senha, is_admin=True):
        super().__init__(nome, email, senha, is_admin)

    def update(self, message):
        print(f"Notificação para {self.nome} (Admin): {message}")

# Modelo de Agendamento
class Agendamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    horario = db.Column(db.DateTime, nullable=False)
    servico = db.Column(db.String(100), nullable=False)
    usuario = db.relationship('Usuario', backref='agendamentos')

# Função para criar o admin automaticamente, caso não exista
@app.before_first_request
def criar_admin():
    admin = Usuario.query.filter_by(email='admin@exemplo.com').first()

    if not admin:
        admin = UsuarioFactory.create_usuario(
            nome='Admin', 
            email='admin@exemplo.com', 
            senha=generate_password_hash('admin123'), 
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin criado com sucesso!")

# Decorador para rotas de admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin', False):
            flash("Acesso negado! Apenas administradores podem acessar esta página.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Rota de Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and check_password_hash(usuario.senha, senha):
            session['user_id'] = usuario.id
            session['is_admin'] = usuario.is_admin  # Armazena o status de admin na sessão
            return redirect(url_for('dashboard'))
        else:
            flash("Login falhou. Verifique suas credenciais.", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')

# Rota de Cadastro
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']

        senha_hash = generate_password_hash(senha)

        if Usuario.query.filter_by(email=email).first():
            flash('Este e-mail já está registrado. Tente outro.', 'danger')
            return redirect(url_for('cadastro'))

        novo_usuario = UsuarioFactory.create_usuario(nome, email, senha_hash)
        db.session.add(novo_usuario)
        db.session.commit()

        flash('Cadastro realizado com sucesso!', 'success')
        return redirect(url_for('login'))

    return render_template('cadastro.html')

# Rota do Dashboard
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    agendamentos = Agendamento.query.filter_by(user_id=user_id).all()

    return render_template('dashboard.html', agendamentos=agendamentos)

# Rota para Agendar
@app.route('/agendar', methods=['POST'])
def agendar():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    datetime_str = request.form['datetime']
    service = request.form['service']

    appointment_time = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M')

    # Recupera as configurações do admin
    settings = {
        'start_time': datetime.strptime('08:00', '%H:%M').time(),  # Hora de início
        'end_time': datetime.strptime('18:00', '%H:%M').time()     # Hora de fim
    }

    # Log de depuração para ver o horário do agendamento
    print(f"Horário do agendamento: {appointment_time.time()}")
    print(f"Intervalo permitido: {settings['start_time']} - {settings['end_time']}")

    # Verifica se o horário do agendamento está dentro do intervalo permitido
    if not (settings['start_time'] <= appointment_time.time() <= settings['end_time']):
        flash(f"Horário inválido. O agendamento deve estar entre {settings['start_time']} e {settings['end_time']}.", 'danger')
        return redirect(url_for('dashboard'))

    novo_agendamento = Agendamento(user_id=user_id, horario=appointment_time, servico=service)
    db.session.add(novo_agendamento)
    db.session.commit()

    # Notifica todos os administradores sobre o novo agendamento
    admins = Usuario.query.filter_by(is_admin=True).all()
    for admin in admins:
        admin.update(f"Novo agendamento de {novo_agendamento.usuario.nome} para o serviço {novo_agendamento.servico} às {novo_agendamento.horario}")

    flash("Agendamento realizado com sucesso!", 'success')
    return redirect(url_for('detalhes_agendamento', agendamento_id=novo_agendamento.id))

# Rota para Detalhes do Agendamento
@app.route('/detalhes_agendamento/<int:agendamento_id>')
def detalhes_agendamento(agendamento_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    agendamento = Agendamento.query.get(agendamento_id)
    
    if not agendamento or agendamento.user_id != session['user_id']:
        return "Agendamento não encontrado", 404

    return render_template('detalhes_agendamento.html', agendamento=agendamento)

# Rota para Configurações de Admin (exemplo)
@app.route('/admin/config')
@admin_required
def admin_config():
    # Exemplo de configuração
    settings = {
        'start_time': '09:00',
        'end_time': '18:00'
    }
    return render_template('admin_config.html', settings=settings)

@app.route('/configurar', methods=['POST'])
@admin_required
def configurar():
    # Lógica de configuração do admin
    flash('Configurações salvas com sucesso!', 'success')
    return redirect(url_for('admin_config'))

# Rota de Logout
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_admin', None)  # Remover status de admin da sessão ao deslogar
    return redirect(url_for('login'))

# Criar banco de dados (execute uma vez antes de rodar o servidor)
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
