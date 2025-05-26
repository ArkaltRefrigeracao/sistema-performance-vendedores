# app_performance.py
from flask import Flask, render_template, redirect, url_for, session, flash, request
from models_performance import db, Usuario, QuesitoDesempenho, RegistroDesempenho, PontuacaoVendedor
import pytz
from datetime import datetime
from werkzeug.security import generate_password_hash # Importe para criar o admin

app = Flask(__name__)
app.config['SECRET_KEY'] = 'uma_chave_secreta_bem_forte_e_unica_para_performance' # Chave secreta diferente do outro projeto
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///performance_db.db' # Banco de dados exclusivo para este projeto
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Configura o fuso horário para Brasília
brasilia_tz = pytz.timezone('America/Sao_Paulo')

# Importa e registra o Blueprint de performance_routes
from performance_routes import performance_bp
app.register_blueprint(performance_bp, url_prefix='/performance')

# Context processor para adicionar informações da sessão em todos os templates
@app.context_processor
def inject_user_info():
    return dict(
        usuario_logado=session.get('usuario_nome'),
        usuario_id=session.get('usuario_id')
    )

@app.before_request
def make_session_permanent():
    from datetime import timedelta # Importe timedelta aqui
    session.permanent = True # Torna a sessão permanente por padrão (duração de 31 dias)
    app.permanent_session_lifetime = timedelta(days=31) # Define o tempo de vida

# Função para criar o banco de dados e dados iniciais
with app.app_context():
    db.create_all() # Cria todas as tabelas

    # Cria o usuário GerenteVendas (administrador) se não existir
    admin_user = Usuario.query.filter_by(nome='GerenteVendas').first()
    if not admin_user:
        admin_user = Usuario(nome='GerenteVendas')
        admin_user.set_senha('Arkalt@2025')
        db.session.add(admin_user)
        print("Usuário 'GerenteVendas' criado.")
    else:
        print("Usuário 'GerenteVendas' já existe.")
    
    # Cadastra os vendedores se não existirem
    vendedores_nomes = ['TANY', 'JOSÉ', 'GUSTAVO', 'ALINE', 'FELIPE']
    for nome_vendedor in vendedores_nomes:
        vendedor_existente = Usuario.query.filter_by(nome=nome_vendedor).first()
        if not vendedor_existente:
            novo_vendedor = Usuario(nome=nome_vendedor)
            # Define uma senha padrão simples para os vendedores (pode ser alterada depois)
            novo_vendedor.set_senha('senha123') 
            db.session.add(novo_vendedor)
            print(f"Vendedor '{nome_vendedor}' criado.")
        else:
            print(f"Vendedor '{nome_vendedor}' já existe.")

    # Cria quesitos de desempenho padrão se não existirem
    quesitos_iniciais = [
        {'nome': 'Clientes Diários', 'pontuacao_padrao': 100, 'tipo': 'positivo'},
    ]
    for q_data in quesitos_iniciais:
        if not QuesitoDesempenho.query.filter_by(nome=q_data['nome']).first():
            quesito = QuesitoDesempenho(**q_data)
            db.session.add(quesito)
            print(f"Quesito '{q_data['nome']}' criado.")

    db.session.commit()
    print("Banco de dados e dados iniciais verificados/criados.")


if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0') # Roda na porta 5001