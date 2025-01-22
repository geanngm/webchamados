from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
import logging
import os
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.sql import text

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

# Configuração do banco de dados usando PostgreSQL
DB_USER = os.getenv('DB_USER', 'projeto_chamados_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'RwV8G694QxAyCdhGNb3WYznrwqyjC6C6')
DB_HOST = os.getenv('DB_HOST', 'dpg-cu8gtshopnds73d63isg-a')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'projeto_chamados')

app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_size": 10,
    "max_overflow": 20
}

# Logger
logging.basicConfig(level=logging.INFO)
logging.info(f"Banco de dados configurado: postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# Inicialização do banco de dados
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Função para testar conexão ao banco de dados
def test_db_connection():
    try:
        db.session.execute(text('SELECT 1'))
        logging.info("Conexão com o banco de dados bem-sucedida.")
    except Exception as e:
        logging.error("Erro ao conectar ao banco de dados.", exc_info=True)
        raise

# Modelos
class Chamado(db.Model):
    __tablename__ = 'chamados'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(10), unique=True, nullable=False, index=True)
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
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    usuario = db.relationship('Usuario', backref=db.backref('chamados', lazy=True))

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome_posto = db.Column(db.String(100), nullable=False)
    nome_usuario = db.Column(db.String(100), nullable=False)
    email_unidade = db.Column(db.String(100), unique=True, nullable=False, index=True)
    telefone = db.Column(db.String(15), nullable=False)
    senha = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default="Cliente")

    def set_senha(self, senha):
        self.senha = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha, senha)

# Função de inicialização do banco
def inicializar_app():
    with app.app_context():
        db.create_all()
        test_db_connection()
        logging.info("Tabelas criadas ou verificadas.")

# Configuração para gunicorn
if __name__ != "__main__":
    with app.app_context():
        test_db_connection()

# Ponto de entrada do aplicativo
if __name__ == "__main__":
    inicializar_app()
    app.run(debug=True)

