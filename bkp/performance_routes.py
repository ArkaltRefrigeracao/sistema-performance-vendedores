# performance_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from models_performance import db, Usuario, QuesitoDesempenho, RegistroDesempenho, PontuacaoVendedor
from datetime import datetime, date, timedelta, timezone
import pytz
from sqlalchemy import func, extract
from sqlalchemy.orm import joinedload

performance_bp = Blueprint('performance_bp', __name__, template_folder='templates', static_folder='static')

brasilia_tz = pytz.timezone('America/Sao_Paulo')

# Decorador simples para verificar se o usuário está logado
def login_required_performance(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Você precisa estar logado para acessar esta página.', 'error')
            return redirect(url_for('performance_bp.login_performance'))
        return f(*args, **kwargs)
    return decorated_function

# Função auxiliar para calcular ou atualizar a pontuação total do vendedor no mês/ano
def atualizar_pontuacao_total_vendedor(vendedor_id, data_registro):
    mes = data_registro.month
    ano = data_registro.year

    # Calcula a soma das pontuações aplicadas para o mês/ano
    # Considera o tipo do quesito (positivo soma, negativo subtrai)
    total_pontuacao_mensal = db.session.query(
        func.sum(
            db.case(
                (QuesitoDesempenho.tipo == 'positivo', RegistroDesempenho.pontuacao_aplicada),
                (QuesitoDesempenho.tipo == 'negativo', -RegistroDesempenho.pontuacao_aplicada), # Garante que subtrai
                else_=0
            )
        )
    ).join(QuesitoDesempenho).filter(
        RegistroDesempenho.vendedor_id == vendedor_id,
        func.strftime('%Y', RegistroDesempenho.data_registro) == str(ano),
        func.strftime('%m', RegistroDesempenho.data_registro) == f"{mes:02d}"
    ).scalar()

    if total_pontuacao_mensal is None:
        total_pontuacao_mensal = 0

    pontuacao_vendedor = PontuacaoVendedor.query.filter_by(
        vendedor_id=vendedor_id, mes=mes, ano=ano
    ).first()

    if pontuacao_vendedor:
        pontuacao_vendedor.pontuacao_total = total_pontuacao_mensal
    else:
        pontuacao_vendedor = PontuacaoVendedor(
            vendedor_id=vendedor_id,
            mes=mes,
            ano=ano,
            pontuacao_total=total_pontuacao_mensal
        )
        db.session.add(pontuacao_vendedor)
    db.session.commit()
    return pontuacao_vendedor


@performance_bp.route('/')
@login_required_performance
def index_performance():
    return redirect(url_for('performance_bp.dashboard_performance'))

@performance_bp.route('/login', methods=['GET', 'POST'])
def login_performance():
    if request.method == 'POST':
        nome = request.form['nome']
        senha = request.form['senha']
        usuario = Usuario.query.filter_by(nome=nome).first()

        if usuario and usuario.check_senha(senha):
            session['usuario_id'] = usuario.id
            session['usuario_nome'] = usuario.nome
            flash('Login bem-sucedido!', 'success')
            return redirect(url_for('performance_bp.dashboard_performance'))
        else:
            flash('Nome de usuário ou senha inválidos.', 'error')
    return render_template('login_performance.html')

@performance_bp.route('/logout')
@login_required_performance
def logout_performance():
    session.pop('usuario_id', None)
    session.pop('usuario_nome', None)
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('performance_bp.login_performance'))

@performance_bp.route('/cadastro_vendedor', methods=['GET', 'POST'])
def cadastro_vendedor_performance():
    if request.method == 'POST':
        nome = request.form['nome']
        senha = request.form['senha']

        usuario_existente = Usuario.query.filter_by(nome=nome).first()
        if usuario_existente:
            flash('Já existe um usuário com este nome.', 'error')
        else:
            novo_usuario = Usuario(nome=nome)
            novo_usuario.set_senha(senha)
            db.session.add(novo_usuario)
            db.session.commit()
            flash('Vendedor cadastrado com sucesso!', 'success')
            return redirect(url_for('performance_bp.login_performance'))
    return render_template('cadastro_vendedor_performance.html')

@performance_bp.route('/config_quesitos', methods=['GET', 'POST'])
@login_required_performance
def config_performance():
    if request.method == 'POST':
        if 'add_quesito' in request.form:
            nome = request.form['nome']
            pontuacao_padrao = int(request.form['pontuacao_padrao'])
            tipo = request.form['tipo']

            quesito_existente = QuesitoDesempenho.query.filter_by(nome=nome).first()
            if quesito_existente:
                flash('Já existe um quesito com este nome.', 'error')
            else:
                novo_quesito = QuesitoDesempenho(nome=nome, pontuacao_padrao=pontuacao_padrao, tipo=tipo)
                db.session.add(novo_quesito)
                db.session.commit()
                flash('Quesito adicionado com sucesso!', 'success')
        elif 'edit_quesito' in request.form:
            quesito_id = request.form['quesito_id']
            quesito = QuesitoDesempenho.query.get(quesito_id)
            if quesito:
                quesito.nome = request.form['nome']
                quesito.pontuacao_padrao = int(request.form['pontuacao_padrao'])
                quesito.tipo = request.form['tipo']
                db.session.commit()
                flash('Quesito atualizado com sucesso!', 'success')
            else:
                flash('Quesito não encontrado.', 'error')
        elif 'delete_quesito' in request.form:
            quesito_id = request.form['quesito_id']
            quesito = QuesitoDesempenho.query.get(quesito_id)
            if quesito:
                db.session.delete(quesito)
                db.session.commit()
                flash('Quesito excluído com sucesso!', 'success')
            else:
                flash('Quesito não encontrado.', 'error')
        return redirect(url_for('performance_bp.config_performance'))

    quesitos = QuesitoDesempenho.query.all()
    return render_template('config_performance.html', quesitos=quesitos)


@performance_bp.route('/lancamento_diario', methods=['GET', 'POST'])
@login_required_performance
def lancamento_diario_performance():
    vendedores = Usuario.query.all()
    quesitos = QuesitoDesempenho.query.all()

    if request.method == 'POST':
        vendedor_id = request.form.get('vendedor_id')
        data_lancamento_str = request.form.get('data_lancamento')

        if not vendedor_id or not data_lancamento_str:
            flash('Selecione o vendedor e a data/hora de lançamento.', 'error')
            return redirect(url_for('performance_bp.lancamento_diario_performance'))

        try:
            data_lancamento_utc = datetime.strptime(data_lancamento_str, '%Y-%m-%dT%H:%M')
            data_lancamento_utc = data_lancamento_utc.replace(tzinfo=timezone.utc)
        except ValueError:
            flash('Formato de data e hora inválido.', 'error')
            return redirect(url_for('performance_bp.lancamento_diario_performance'))

        vendedor = Usuario.query.get(vendedor_id)
        if not vendedor:
            flash('Vendedor não encontrado.', 'error')
            return redirect(url_for('performance_bp.lancamento_diario_performance'))

        registros_salvos = 0
        for quesito in quesitos:
            if request.form.get(f'quesito_{quesito.id}_selected'):
                pontuacao_str = request.form.get(f'pontuacao_{quesito.id}')
                observacao = request.form.get(f'obs_{quesito.id}', '').strip()

                try:
                    pontuacao_aplicada = int(pontuacao_str)
                except (ValueError, TypeError):
                    flash(f'Pontuação inválida para o quesito "{quesito.nome}".', 'error')
                    continue

                novo_registro = RegistroDesempenho(
                    vendedor_id=vendedor.id,
                    quesito_id=quesito.id,
                    data_registro=data_lancamento_utc,
                    pontuacao_aplicada=pontuacao_aplicada,
                    observacao=observacao if observacao else None
                )
                db.session.add(novo_registro)
                registros_salvos += 1

        try:
            db.session.commit()
            if registros_salvos > 0:
                flash(f'{registros_salvos} registros de desempenho lançados com sucesso para {vendedor.nome}!', 'success')
                atualizar_pontuacao_total_vendedor(vendedor.id, data_lancamento_utc)
            else:
                flash('Nenhum quesito foi selecionado para lançamento.', 'info')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar registros: {str(e)}', 'error')
            print(f"Erro ao salvar registros: {e}")
            return redirect(url_for('performance_bp.lancamento_diario_performance'))

        return redirect(url_for('performance_bp.lancamento_diario_performance'))

    return render_template('lancamento_diario_performance.html', vendedores=vendedores, quesitos=quesitos)

@performance_bp.route('/dashboard')
@login_required_performance
def dashboard_performance():
    vendedores = Usuario.query.all()
    now = datetime.now()
    return render_template('dashboard_performance.html', vendedores=vendedores, now=now)


# Rota para buscar dados do dashboard (para AJAX)
@performance_bp.route('/api/pontuacoes_mensais')
@login_required_performance
def get_pontuacoes_mensais():
    mes_str = request.args.get('mes')
    ano_str = request.args.get('ano')
    vendedor_id_str = request.args.get('vendedor_id')

    if not all([mes_str, ano_str]):
        return jsonify({'error': 'Parâmetros de mês e ano são obrigatórios.'}), 400

    try:
        mes = int(mes_str)
        ano = int(ano_str)
    except ValueError:
        return jsonify({'error': 'Mês e ano devem ser números válidos.'}), 400

    # --- Dados para o Gráfico de Pontuação Total por Vendedor (sempre todos os vendedores para o mês/ano) ---
    query_overall = PontuacaoVendedor.query.options(joinedload(PontuacaoVendedor.vendedor_pontuacoes)).filter(
        PontuacaoVendedor.mes == mes,
        PontuacaoVendedor.ano == ano
    )
    overall_performance_data = query_overall.order_by(PontuacaoVendedor.pontuacao_total.desc()).all()

    overall_labels = [p.vendedor_pontuacoes.nome for p in overall_performance_data]
    overall_data = [p.pontuacao_total for p in overall_performance_data]

    # --- Dados para o Gráfico de Desempenho por Quesito (apenas se um vendedor específico for selecionado) ---
    quesito_performance_labels = []
    quesito_performance_data = []

    if vendedor_id_str and vendedor_id_str != 'all':
        try:
            vendedor_id = int(vendedor_id_str)
            # Consulta para obter a soma das pontuações aplicadas para cada quesito
            quesitos_agregados = db.session.query(
                QuesitoDesempenho.nome,
                func.sum(
                    db.case(
                        (QuesitoDesempenho.tipo == 'positivo', RegistroDesempenho.pontuacao_aplicada),
                        (QuesitoDesempenho.tipo == 'negativo', -RegistroDesempenho.pontuacao_aplicada),
                        else_=0
                    )
                ).label('pontuacao_total_quesito')
            ).join(RegistroDesempenho, RegistroDesempenho.quesito_id == QuesitoDesempenho.id).filter(
                RegistroDesempenho.vendedor_id == vendedor_id,
                func.strftime('%Y', RegistroDesempenho.data_registro) == str(ano),
                func.strftime('%m', RegistroDesempenho.data_registro) == f"{mes:02d}"
            ).group_by(QuesitoDesempenho.nome).all()

            for nome_quesito, pontuacao_total_quesito in quesitos_agregados:
                quesito_performance_labels.append(nome_quesito)
                quesito_performance_data.append(pontuacao_total_quesito)

        except ValueError:
            return jsonify({'error': 'ID do vendedor inválido para quesitos.'}), 400
    
    # --- Dados para a Tabela de Detalhes Diários (apenas se um vendedor específico for selecionado) ---
    detalhes_diarios = []
    vendedor_nome_para_detalhes = ""

    if vendedor_id_str and vendedor_id_str != 'all':
        try:
            vendedor_id_int = int(vendedor_id_str)
            vendedor_obj = Usuario.query.get(vendedor_id_int)
            if vendedor_obj:
                vendedor_nome_para_detalhes = vendedor_obj.nome

            registros = RegistroDesempenho.query.options(joinedload(RegistroDesempenho.quesito_rel)).filter(
                RegistroDesempenho.vendedor_id == vendedor_id_int,
                func.strftime('%Y', RegistroDesempenho.data_registro) == str(ano),
                func.strftime('%m', RegistroDesempenho.data_registro) == f"{mes:02d}"
            ).order_by(RegistroDesempenho.data_registro.asc()).all()

            for registro in registros:
                data_local = registro.data_registro.replace(tzinfo=timezone.utc).astimezone(brasilia_tz)
                detalhes_diarios.append({
                    'data': data_local.strftime('%d/%m/%Y %H:%M'),
                    'quesito': registro.quesito_rel.nome,
                    'pontuacao_aplicada': registro.pontuacao_aplicada,
                    'observacao': registro.observacao if registro.observacao else ''
                })

        except ValueError:
            return jsonify({'error': 'ID do vendedor inválido para detalhes diários.'}), 400


    return jsonify({
        'success': True,
        'overall_performance': {
            'labels': overall_labels,
            'data': overall_data
        },
        'quesito_performance': {
            'labels': quesito_performance_labels,
            'data': quesito_performance_data
        },
        'daily_details': {
            'vendedor_nome': vendedor_nome_para_detalhes,
            'detalhes': detalhes_diarios
        }
    })