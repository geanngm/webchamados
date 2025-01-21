from flask import Flask, send_from_directory, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import logging
from flask_migrate import Migrate
import os
import secrets

# Configuração do app
app = Flask(__name__)

# Geração de uma chave secreta persistente
def generate_secret_key():
    secret_file = "secret.key"
    if not os.path.exists(secret_file):
        with open(secret_file, "wb") as f:
            f.write(secrets.token_bytes(24))
    with open(secret_file, "rb") as f:
        return f.read()

app.secret_key = generate_secret_key()

# Configuração do banco de dados
def get_database_path():
    # Usa /tmp como diretório padrão para persistência temporária
    default_path = "/tmp/chamados.db"  # Caminho permitível para escrita na Render
    return os.getenv('DATABASE_PATH', default_path)

db_path = get_database_path()
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Logger
logging.basicConfig(level=logging.INFO)
logging.info(f"Banco de dados configurado em: {db_path}")

# Inicialização do banco de dados
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Criação do banco de dados manualmente no início
def create_db():
    try:
        if not os.path.exists(db_path):
            with app.app_context():
                db.create_all()
                logging.info("Banco de dados criado com sucesso.")
    except Exception as e:
        logging.error(f"Erro ao criar o banco de dados: {e}")

create_db()

# Modelos
class Chamado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(10), unique=True, nullable=False)
    defeito = db.Column(db.Text, nullable=False)
    posto = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(15), nullable=False)
    ip_maquina = db.Column(db.String(15), nullable=False)
    solicitante = db.Column(db.String(100), nullable=False)
    resposta = db.Column(db.Text, nullable=True)
    acao = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Aberto")
    data_abertura = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    data_fechamento = db.Column(db.DateTime, nullable=True)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_posto = db.Column(db.String(100), nullable=False)
    nome_usuario = db.Column(db.String(100), nullable=False)
    email_unidade = db.Column(db.String(100), unique=True, nullable=False)
    telefone = db.Column(db.String(15), nullable=False)
    senha = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default="Cliente")

# Rotas
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        usuario = Usuario.query.filter_by(email_unidade=email, senha=senha).first()
        if usuario:
            session['usuario_id'] = usuario.id
            session['usuario_tipo'] = usuario.tipo
            return redirect(url_for('index'))
        else:
            return render_template('login.html', erro="Usuário ou senha inválidos")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/index')
def index():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario_id = session.get('usuario_id')
    usuario = Usuario.query.get(usuario_id)
    if not usuario:
        return redirect(url_for('logout'))

    return render_template('index.html', nome_usuario=usuario.nome_usuario, usuario_tipo=usuario.tipo)

# Rota para visualizar chamados abertos
@app.route('/chamados_abertos')
def chamados_abertos():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario_id = session['usuario_id']
    usuario = Usuario.query.get_or_404(usuario_id)

    # Verifica o tipo de usuário e filtra chamados pelo posto
    if usuario.tipo == 'Cliente':
        chamados = Chamado.query.filter(
            Chamado.data_fechamento.is_(None),
            (Chamado.posto == usuario.nome_posto) | (Chamado.posto == None) | (Chamado.posto == "")
        ).all()
    else:
        chamados = Chamado.query.filter(Chamado.data_fechamento.is_(None)).all()

    return render_template('chamados_abertos.html', chamados=chamados)

@app.route('/chamados_fechados', methods=['GET', 'POST'])
def chamados_fechados():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    usuario_id = session['usuario_id']
    usuario = Usuario.query.get_or_404(usuario_id)

    postos = [f"{str(i).zfill(3)}" for i in range(1, 201)] + ["SIH"]
    chamados = []

    if usuario.tipo == 'Cliente':
        chamados = Chamado.query.filter(
            Chamado.data_fechamento.isnot(None),
            (Chamado.posto == usuario.nome_posto) | (Chamado.posto == None) | (Chamado.posto == "")
        ).all()
        return render_template('chamados_fechados.html', postos=[], chamados=chamados, is_cliente=True)

    if request.method == 'POST':
        posto = request.form.get('posto')
        data_inicio = request.form.get('inicio')
        data_fim = request.form.get('fim')
        reset = request.form.get('reset')

        if reset:
            return redirect(url_for('chamados_fechados'))

        query = Chamado.query.filter(Chamado.data_fechamento.isnot(None))

        if posto:
            query = query.filter((Chamado.posto == posto) | (Chamado.posto == None) | (Chamado.posto == ""))
        if data_inicio:
            query = query.filter(Chamado.data_abertura >= data_inicio)
        if data_fim:
            query = query.filter(Chamado.data_abertura <= data_fim)

        chamados = query.all()

    return render_template('chamados_fechados.html', postos=postos, chamados=chamados, is_cliente=False)

@app.route('/trocar_senha', methods=['GET', 'POST'])
def trocar_senha():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        senha_atual = request.form['senha_atual']
        nova_senha = request.form['nova_senha']
        confirmar_senha = request.form['confirmar_senha']

        usuario = Usuario.query.get(session['usuario_id'])
        if usuario and usuario.senha == senha_atual:
            if nova_senha == confirmar_senha:
                usuario.senha = nova_senha
                db.session.commit()
                flash("Senha alterada com sucesso!", "success")
                return redirect(url_for('index'))
            else:
                erro = "As novas senhas não coincidem."
        else:
            erro = "Senha atual incorreta."

        return render_template('trocar_senha.html', erro=erro)

    return render_template('trocar_senha.html')


@app.route('/relatorio', methods=['GET', 'POST'])
def relatorio():
    # Lista de postos
    postos = [f"{i:03}" for i in range(1, 201)] + ["SIH", "Todos"]

    chamados = []  # Garantir que chamados seja uma lista, mesmo que não seja preenchida
    filtro_posto = None
    filtro_inicio = None
    filtro_fim = None

    if request.method == 'POST':
        posto = request.form.get('posto')
        inicio = request.form.get('inicio')
        fim = request.form.get('fim')

        # Tratar os valores vazios
        filtro_posto = posto.strip() if posto and posto != "Todos" else None
        filtro_inicio = datetime.strptime(inicio, '%Y-%m-%d') if inicio else None
        filtro_fim = datetime.strptime(fim, '%Y-%m-%d') if fim else None

        # Buscar os dados conforme os filtros
        query = Chamado.query
        if filtro_posto:
            query = query.filter(Chamado.posto == filtro_posto)
        if filtro_inicio:
            query = query.filter(Chamado.data_abertura >= filtro_inicio)
        if filtro_fim:
            query = query.filter(Chamado.data_abertura <= filtro_fim)

        chamados = query.all()

        # Verificação de resposta e ação, mas isso não é necessário se os campos sempre existirem
        for chamado in chamados:
            if not chamado.resposta:
                chamado.resposta = None
            if not chamado.acao:
                chamado.acao = None

    # Formatar as datas para o formato desejado (YYYY-MM-DD)
    filtro_inicio = filtro_inicio.strftime('%Y-%m-%d') if filtro_inicio else ''
    filtro_fim = filtro_fim.strftime('%Y-%m-%d') if filtro_fim else ''

    return render_template('relatorio.html', chamados=chamados, postos=postos, 
                           filtro_posto=filtro_posto, filtro_inicio=filtro_inicio, filtro_fim=filtro_fim)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # Criar o administrador inicial, se não existir
        if not Usuario.query.filter_by(email_unidade='admin@admin.com').first():
            admin = Usuario(
                nome_posto='Admin',
                nome_usuario='Administrador',
                email_unidade='admin@admin.com',
                telefone='0000000000',
                senha='admin123',
                tipo='Administrador'
            )
            db.session.add(admin)
            db.session.commit()

    app.run(host='0.0.0.0', port=5000)
