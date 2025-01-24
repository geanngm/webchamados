from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import logging
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
import json

# Configuração do Flask e SQLite
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chamados_db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'chave_secreta'

db = SQLAlchemy(app)

# Configuração do logger
logging.basicConfig(level=logging.DEBUG)

# Configuração do Google Drive
GOOGLE_DRIVE_FOLDER_ID = '12DKMnx7avXf8YADVzwpjuly0D9CZRzWt'

# Usar a variável de ambiente para as credenciais
google_credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

if google_credentials_json is None:
    raise RuntimeError("A variável de ambiente GOOGLE_APPLICATION_CREDENTIALS não foi definida.")

# Carregar as credenciais do Google Drive a partir da variável de ambiente
try:
    # As credenciais precisam ser passadas como um JSON carregado da variável de ambiente
    credentials_info = json.loads(google_credentials_json)
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=['https://www.googleapis.com/auth/drive']
    )
    drive_service = build('drive', 'v3', credentials=credentials)
    logging.info("Conexão com o Google Drive configurada com sucesso.")
except Exception as e:
    raise RuntimeError(f"Erro ao configurar as credenciais do Google Drive: {e}")

# Função para fazer upload do banco de dados para o Google Drive
def upload_to_drive():
    arquivo = 'chamados_db.sqlite'
    if not os.path.exists(arquivo):
        logging.error("O arquivo do banco de dados não foi encontrado.")
        return "Arquivo do banco de dados não encontrado."

    try:
        # Configurar os metadados do arquivo
        file_metadata = {'name': arquivo, 'parents': [GOOGLE_DRIVE_FOLDER_ID]}
        media = MediaFileUpload(arquivo, mimetype='application/x-sqlite3')

        # Fazer upload do arquivo
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        logging.info(f"Banco de dados enviado com sucesso. File ID: {file.get('id')}")
        return f"Banco de dados enviado com sucesso! File ID: {file.get('id')}"
    except Exception as e:
        logging.error(f"Erro ao enviar o banco para o Google Drive: {e}")
        raise RuntimeError(f"Erro ao enviar o banco para o Google Drive: {e}")

# Modelos de Banco de Dados
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_posto = db.Column(db.String(100))
    nome_usuario = db.Column(db.String(100))
    email_unidade = db.Column(db.String(100), unique=True)
    telefone = db.Column(db.String(15))
    senha = db.Column(db.String(255))
    tipo = db.Column(db.String(50))

    def set_password(self, password):
        self.senha = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.senha, password)

class Chamado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20))
    defeito = db.Column(db.Text)
    posto = db.Column(db.String(100))
    telefone = db.Column(db.String(15))
    ip_maquina = db.Column(db.String(15))
    solicitante = db.Column(db.String(100))
    resposta = db.Column(db.Text)
    acao = db.Column(db.Text)
    status = db.Column(db.String(20))
    data_abertura = db.Column(db.DateTime, default=datetime.utcnow)
    data_fechamento = db.Column(db.DateTime, nullable=True)

# Rotas para criar o banco e testar upload
@app.route('/criar_bd')
def criar_bd():
    try:
        db.create_all()
        logging.info("Banco de dados criado com sucesso.")
        return "Banco de dados criado com sucesso!"
    except Exception as e:
        logging.error(f"Erro ao criar o banco de dados: {e}")
        return f"Erro ao criar o banco de dados: {e}"

@app.route('/fazer_upload')
def fazer_upload():
    try:
        mensagem = upload_to_drive()
        return mensagem if mensagem else "Banco de dados enviado para o Google Drive com sucesso!"
    except Exception as e:
        return f"Erro ao enviar o banco para o Google Drive: {e}"

# Inicialização
if __name__ == '__main__':
    app.run(debug=True)


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']

        # Buscar o usuário no banco pelo email
        usuario = Usuario.query.filter_by(email_unidade=email).first()

        if usuario and check_password_hash(usuario.senha, senha):
            # Login bem-sucedido
            session['user_id'] = usuario.id  # Exemplo: armazene o ID do usuário na sessão
            return redirect('/dashboard')   # Redirecione para uma página segura após o login

        flash('E-mail ou senha incorretos!', 'error')  # Exibe mensagem de erro no frontend
    return render_template('login.html')

@app.before_request
def require_login():
    # Ignorar a verificação para as rotas 'home', 'login' e 'static'
    if 'user_id' not in session and request.endpoint not in ['home', 'login', 'static', 'login']:  # Exclui explicitamente 'login'
        return redirect(url_for('home'))

# Rota para login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = Usuario.query.filter_by(nome_usuario=username).first()  # Corrigir para `Usuario`
        if user and user.check_password(password):  # Verificação de hash da senha
            session['user_id'] = user.id
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha inválidos', 'danger')
    return render_template('login.html')


# Rota para página principal após login
@app.route('/index')
def index():
    if 'user_id' not in session:
        flash('Por favor, faça login primeiro.', 'warning')
        return redirect(url_for('home'))
    
    # Obter informações do usuário logado
    user = Usuario.query.get(session['user_id'])
    if user:
        return render_template('index.html', 
                               nome_usuario=user.nome_usuario, 
                               usuario_tipo=user.tipo)
    else:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('home'))

@app.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
def editar_usuario(id):
    if 'usuario_id' not in session or session.get('usuario_tipo') != 'Administrador':
        return redirect(url_for('login'))

    usuario = Usuario.query.get_or_404(id)
    postos = [f"{i:03}" for i in range(1, 201)] + ["SIH"]

    if request.method == 'POST':
        usuario.nome_posto = request.form.get('nome_posto').strip()
        usuario.nome_usuario = request.form.get('nome_usuario').strip()
        usuario.email_unidade = request.form.get('email_unidade').strip()
        usuario.telefone = request.form.get('telefone').strip()
        if request.form.get('senha'):
            usuario.set_password(request.form.get('senha').strip())
        usuario.tipo = request.form.get('tipo').strip()

        try:
            db.session.commit()
            upload_to_drive()  # Enviar o banco atualizado para o Google Drive
            return redirect(url_for('gerenciar_usuarios'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao editar usuário: {e}")
            erro = "Erro ao salvar alterações. Verifique os dados e tente novamente."
            return render_template('editar_usuario.html', usuario=usuario, postos=postos, erro=erro)

    return render_template('editar_usuario.html', usuario=usuario, postos=postos)


@app.route('/excluir_usuario/<int:id>', methods=['POST'])
def excluir_usuario(id):
    if 'usuario_id' not in session or session.get('usuario_tipo') != 'Administrador':
        return redirect(url_for('login'))

    usuario = Usuario.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    upload_to_drive()  # Enviar o banco atualizado para o Google Drive
    return redirect(url_for('gerenciar_usuarios'))


@app.route('/abrir_chamado', methods=['GET', 'POST'])
def abrir_chamado():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    postos = [f"{i:03}" for i in range(1, 201)] + ["SIH"]

    if request.method == 'POST':
        try:
            ultimo_chamado = Chamado.query.order_by(Chamado.id.desc()).first()
            numero = f"CH-{(ultimo_chamado.id + 1) if ultimo_chamado else 1:06d}"

            defeito = request.form['defeito'].strip()
            posto = request.form['posto'].strip()
            telefone = request.form['telefone'].strip()
            ip_maquina = request.form['ip_maquina'].strip()
            solicitante = request.form['solicitante'].strip()
            patrimonio = request.form['patrimonio'].strip()

            novo_chamado = Chamado(
                numero=numero,
                defeito=defeito,
                posto=posto,
                telefone=telefone,
                ip_maquina=ip_maquina,
                solicitante=solicitante,
                resposta=f"Patrimônio/Número de Série: {patrimonio}",
                status="Aberto",
                data_abertura=datetime.utcnow()
            )
            db.session.add(novo_chamado)
            db.session.commit()
            upload_to_drive()  # Enviar o banco atualizado para o Google Drive
            flash(f"Chamado criado com sucesso! Número: {numero}", "success")
            return redirect(url_for('chamados_abertos'))

        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao criar chamado: {e}")
            flash("Erro ao criar o chamado.", "error")
            return render_template('abrir_chamado.html', postos=postos, erro="Erro ao criar o chamado.")

    return render_template('abrir_chamado.html', postos=postos)


@app.route('/responder_chamado/<int:id>', methods=['GET', 'POST'])
def responder_chamado(id):
    if 'usuario_id' not in session or session.get('usuario_tipo') != 'Administrador':
        return redirect(url_for('login'))

    chamado = Chamado.query.get_or_404(id)

    if request.method == 'POST':
        resposta = request.form['resposta'].strip()
        status = request.form['status'].strip()

        chamado.resposta = resposta
        chamado.acao = resposta

        if status == 'Resolvido':
            chamado.status = 'Fechado'
            chamado.data_fechamento = datetime.utcnow()
        else:
            chamado.status = status

        db.session.commit()
        upload_to_drive()  # Enviar o banco atualizado para o Google Drive
        flash('Chamado atualizado com sucesso!', 'success')
        return redirect(url_for('chamados_abertos'))

    return render_template('responder_chamado.html', chamado=chamado)


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

        # Verificar se o usuário administrador já existe
        if not Usuario.query.filter_by(email_unidade='admin@admin.com').first():
            # Armazenar a senha como hash
            hashed_password = generate_password_hash('admin123', method='sha256')

            # Criar usuário administrador com senha protegida
            admin = Usuario(
                nome_posto='Admin',
                nome_usuario='Administrador',
                email_unidade='admin@admin.com',
                telefone='0000000000',
                senha=hashed_password,
                tipo='Administrador'
            )
            db.session.add(admin)
            db.session.commit()

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
