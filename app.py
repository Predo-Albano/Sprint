from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

# Inicialização do aplicativo e configurações do banco de dados
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'sua_chave_unica'
database = SQLAlchemy(app)

# Modelo de usuário
class Usuario(database.Model):
    __tablename__ = 'usuarios'
    id = database.Column(database.Integer, primary_key=True)
    nome_usuario = database.Column(database.String(80), unique=True, nullable=False)
    senha_hash = database.Column(database.String(120), nullable=False)
    email_usuario = database.Column(database.String(120), unique=True, nullable=False)

# Modelo de agendamento
class Agendamento(database.Model):
    __tablename__ = 'agendamentos'
    id = database.Column(database.Integer, primary_key=True)
    usuario_id = database.Column(database.Integer, database.ForeignKey('usuarios.id'), nullable=False)
    data_hora = database.Column(database.DateTime, nullable=False)

# Criação do banco de dados no contexto do aplicativo
with app.app_context():
    database.create_all()

# Rota inicial

@app.route('/')
@app.route('/')
def pagina_inicial():
    return render_template('login.html')


# Rota de login
@app.route('/login', methods=['GET', 'POST'])
def login_usuario():
    if request.method == 'POST':
        nome_usuario = request.form['username']
        senha = request.form['password']
        usuario = Usuario.query.filter_by(nome_usuario=nome_usuario).first()
        if usuario and check_password_hash(usuario.senha_hash, senha):
            session['usuario_id'] = usuario.id
            return redirect(url_for('area_usuario'))
        flash('Dados de login inválidos.')
    return render_template('login.html')

# Rota de cadastro
@app.route('/cadastro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nome_usuario = request.form['username']
        senha = generate_password_hash(request.form['password'])
        email = request.form['email']
        novo_usuario = Usuario(nome_usuario=nome_usuario, senha_hash=senha, email_usuario=email)
        database.session.add(novo_usuario)
        database.session.commit()
        flash('Cadastro concluído com sucesso!')
        return redirect(url_for('login_usuario'))
    return render_template('cadastro.html')

# Rota da área do usuário
@app.route('/dashboard')
def area_usuario():
    if 'usuario_id' not in session:
        return redirect(url_for('login_usuario'))
    agendamentos_usuario = Agendamento.query.filter_by(usuario_id=session['usuario_id']).all()
    return render_template('agendamentos.html', agendamentos=agendamentos_usuario)

# Rota para agendar horários
@app.route('/agendar', methods=['POST'])
def marcar_agendamento():
    if 'usuario_id' not in session:
        return redirect(url_for('login_usuario'))
    data_hora_str = request.form['datetime']
    data_hora_agendamento = datetime.strptime(data_hora_str, '%Y-%m-%d %H:%M')
    if Agendamento.query.filter((Agendamento.data_hora >= data_hora_agendamento) & (Agendamento.data_hora < data_hora_agendamento + timedelta(minutes=50))).first():
        flash('Horário indisponível. Selecione outro.')
    else:
        novo_agendamento = Agendamento(usuario_id=session['usuario_id'], data_hora=data_hora_agendamento)
        database.session.add(novo_agendamento)
        database.session.commit()
        flash('Horário agendado com sucesso!')
    return redirect(url_for('area_usuario'))

# Rota para logout
@app.route('/logout')
def sair():
    session.pop('usuario_id', None)
    return redirect(url_for('pagina_inicial'))

# Inicialização do servidor
if __name__ == '__main__':
    app.run(debug=True)


