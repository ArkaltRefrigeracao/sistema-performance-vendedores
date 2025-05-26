# models_performance.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timezone # Importe 'date' para campos de data pura
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint, func # Importe 'func' para futuras queries

db = SQLAlchemy()

# Classe Usuario simplificada para o projeto de desempenho
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    senha_hash = db.Column(db.String(128))

    # Relações para as tabelas de desempenho
    pontuacoes_mensais = db.relationship('PontuacaoVendedor', backref='vendedor_pontuacoes', lazy=True)
    registros_diarios_desempenho = db.relationship('RegistroDesempenho', backref='vendedor_do_registro', lazy=True)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def __repr__(self):
        return f'<Usuario {self.nome}>'

class QuesitoDesempenho(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    pontuacao_padrao = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(10), nullable=False) # 'positivo' ou 'negativo'

    # Relação para registros de desempenho
    registros_associados = db.relationship('RegistroDesempenho', backref='quesito_desempenho_obj', lazy=True)

    def __repr__(self):
        return f'<QuesitoDesempenho {self.nome} ({self.pontuacao_padrao})>'

class RegistroDesempenho(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    quesito_id = db.Column(db.Integer, db.ForeignKey('quesito_desempenho.id'), nullable=False)
    # Usando db.DateTime para armazenar data e hora com fuso horário
    data_registro = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    pontuacao_aplicada = db.Column(db.Integer, nullable=False)
    observacao = db.Column(db.Text)

    # Adicione ESTA LINHA para a relação com QuesitoDesempenho
    quesito_rel = db.relationship('QuesitoDesempenho', backref='registros_associados_por_quesito', lazy=True)


    def __repr__(self):
        return f'<RegistroDesempenho Vendedor:{self.vendedor_id} Quesito:{self.quesito_id} Data:{self.data_registro}>'

class PontuacaoVendedor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    pontuacao_total = db.Column(db.Integer, nullable=False, default=0)

    # Garante que cada vendedor tenha apenas uma pontuação total por mês/ano
    __table_args__ = (UniqueConstraint('vendedor_id', 'mes', 'ano', name='_vendedor_mes_ano_uc'),)

    # Relação com a tabela Usuario
    vendedor = db.relationship('Usuario', backref=db.backref('pontuacao_vendedor_mensal', lazy=True))

    def __repr__(self):
        return f'<PontuacaoVendedor Vendedor:{self.vendedor_id} Mes:{self.mes} Ano:{self.ano} Pontuação:{self.pontuacao_total}>'