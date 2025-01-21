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

# Configuração do banco de dados (ajustada para Render ou persistência local)
def get_database_path():
    default_path = "/var/data/chamados.db"  # Caminho persistente para o banco de dados
    return os.getenv('DATABASE_PATH', default_path)

db_path = get_database_path()
os.makedirs(os.path.dirname(db_path), exist_ok=True)  # Garante que o diretório exista
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
    if not os.path.exists(db_path):
        with app.app_context():
            db.create_all()
            logging.info("Banco de dados criado com sucesso.")

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

@app.route('/gerenciar_usuarios', methods=['GET', 'POST'])
def gerenciar_usuarios():
    if 'usuario_id' not in session or session.get('usuario_tipo') != 'Administrador':
        return redirect(url_for('login'))

    usuarios = Usuario.query.all()
    postos = [f"{i:03}" for i in range(1, 201)] + ["SIH"]

    if request.method == 'POST':
        nome_posto = request.form.get('nome_posto')
        nome_usuario = request.form.get('nome_usuario')
        email_unidade = request.form.get('email_unidade')
        telefone = request.form.get('telefone')
        senha = request.form.get('senha')
        tipo = request.form.get('tipo')

        try:
            novo_usuario = Usuario(
                nome_posto=nome_posto,
                nome_usuario=nome_usuario,
                email_unidade=email_unidade,
                telefone=telefone,
                senha=senha,
                tipo=tipo
            )
            db.session.add(novo_usuario)
            db.session.commit()
            return redirect(url_for('gerenciar_usuarios'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao adicionar usuário: {e}")
            erro = "Erro ao salvar usuário. Verifique os dados e tente novamente."
            return render_template('gerenciar_usuarios.html', usuarios=usuarios, postos=postos, erro=erro)

    return render_template('gerenciar_usuarios.html', usuarios=usuarios, postos=postos)

# Adicionar as outras rotas mantendo a estrutura do código enviada.

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
        usuario.senha = request.form.get('senha').strip()
        usuario.tipo = request.form.get('tipo').strip()

        try:
            db.session.commit()
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
        resposta = request.form['resposta'].strip()  # Obtém a resposta dada pelo administrador
        status = request.form['status'].strip()  # Obtém o status do chamado

        # Armazenando a resposta tanto no campo 'resposta' quanto no campo 'acao'
        chamado.resposta = resposta
        chamado.acao = resposta  # Armazenando a resposta na coluna 'acao'

        # Atualizando o status e a data de fechamento se necessário
        if status == 'Resolvido':
            chamado.status = 'Fechado'
            chamado.data_fechamento = datetime.utcnow()  # Define a data de fechamento para o momento atual
        else:
            chamado.status = status  # Atualiza o status com o valor informado

        db.session.commit()  # Comita as alterações no banco de dados
        flash('Chamado atualizado com sucesso!', 'success')  # Exibe uma mensagem de sucesso
        return redirect(url_for('chamados_abertos'))  # Redireciona para a lista de chamados abertos

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
