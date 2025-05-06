from flask import Flask, jsonify, request, send_file, render_template
from flask_cors import CORS
from main import app, con
import re
import jwt
from fpdf import FPDF
from flask_bcrypt import generate_password_hash, check_password_hash
import unicodedata
from datetime import datetime, time
from datetime import timedelta
import qrcode
from qrcode.constants import ERROR_CORRECT_H
import crcmod
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os

app = Flask(__name__)

CORS(app, origins=["*"])

app.config.from_pyfile('config.py')
senha_secreta = app.config['SECRET_KEY']

if not os.path.exists(app.config['UPLOAD_FILMES']):
    os.makedirs(app.config['UPLOAD_FILMES'])


def verificar_adm(id_cadastro):
    cur = con.cursor()
    cur.execute("SELECT tipo FROM cadastros WHERE id_cadastro = ?", (id_cadastro,))
    tipo = cur.fetchone()

    if tipo and tipo[0] == 'adm':
        return True
    else:
        return False

def normalizar_texto(texto):
    if texto:
        return unicodedata.normalize('NFC', texto)
    return texto

def enviar_email_para(destinatario, corpo, caminho_anexo=None):
    try:
        # Criação da mensagem
        msg = MIMEMultipart()
        msg['From'] = 'primecine00@gmail.com'
        msg['To'] = destinatario
        msg['Subject'] = 'Confirmação de Reserva - PrimeCine'

        # Corpo do e-mail
        msg.attach(MIMEText(corpo, 'plain'))

        # Adicionando anexo, se houver
        if caminho_anexo:
            with open(caminho_anexo, 'rb') as f:
                parte = MIMEBase('application', 'octet-stream')
                parte.set_payload(f.read())
                encoders.encode_base64(parte)
                parte.add_header('Content-Disposition', f'attachment; filename={os.path.basename(caminho_anexo)}')
                msg.attach(parte)

        # Conexão segura via SSL com o servidor SMTP
        servidor = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        servidor.set_debuglevel(1)  # Habilita o modo de depuração para ver os detalhes da conexão

        # Login
        servidor.login('primecine00@gmail.com', 'zzzj kwhn mnhb vtrx')  # Senha de app

        # Envio do e-mail
        servidor.send_message(msg)
        print('E-mail enviado com sucesso!')

    except smtplib.SMTPConnectError as e:
        print(f"Erro ao conectar ao servidor SMTP: {e}")
    except smtplib.SMTPAuthenticationError as e:
        print(f"Erro de autenticação SMTP: {e}")
    except smtplib.SMTPException as e:
        print(f"Erro ao enviar o e-mail: {e}")
    finally:
        try:
            servidor.quit()  # Fecha a conexão com o servidor SMTP
        except Exception as e:
            print(f"Erro ao fechar a conexão com o servidor: {e}")

def remover_bearer(token):  # Remove o bearer
    if token.startswith('Bearer '):
        return token[len('Bearer '):]
    else:
        return token

def generate_token(user_id, email):  # Gera um token para o usuario
    payload = {'id_usuario': user_id, 'email':email}
    token = jwt.encode(payload, senha_secreta, algorithm='HS256')
    return token

def validar_senha(senha):
    if len(senha) < 8:
        return jsonify({"error": "A senha deve ter pelo menos 8 caracteres"}), 400

    if not re.search(r"[!@#$%¨&*(),.?\":<>{}|]", senha):
        return jsonify({"error": "A senha deve conter pelo menos um símbolo especial"}), 400

    if not re.search(r"[A-Z]", senha):
        return jsonify({"error": "A senha deve conter pelo menos uma letra maiúscula"}), 400

    if len(re.findall(r"\d", senha)) < 2:
        return jsonify({"error": "A senha deve conter pelo menos dois números"}), 400

    return True

@app.route('/cadastros', methods=['GET'])
def usuarios():
        cur = con.cursor()
        cur.execute("SELECT id_cadastro, nome, telefone, email, senha, tipo FROM cadastros")
        usuarios = cur.fetchall()
        usuarios_dic = []

        for usuario in usuarios:
            usuarios_dic.append({
            'id_usuario': usuario[0],
            'nome': usuario[1],
            'telefone': usuario[2],
            'email': usuario[3],
            'senha': usuario[4],
            'tipo': usuario[5]
            })

        return jsonify(mensagem='Lista de usuarios', usuarios=usuarios_dic)

@app.route('/cadastros', methods=['POST'])
def cadastro_usuario():
    data = request.get_json()
    nome = data.get('nome')
    telefone = data.get('telefone')
    email = data.get('email')
    senha = data.get('senha')
    tipo = data.get('tipo')

    senha_check = validar_senha(senha)
    if senha_check is not True:
        return senha_check

    cur = con.cursor()

    cur.execute("SELECT 1 FROM cadastros WHERE email = ?", (email,))

    if cur.fetchone():
        return jsonify({"error": "Este usuário já foi cadastrado!"}), 400

    senha = generate_password_hash(senha).decode('utf-8')

    cur.execute("INSERT INTO CADASTROS (NOME, TELEFONE, EMAIL, SENHA, TIPO, ativo) VALUES(?, ?, ?, ?, ?, ?)", (nome, telefone, email, senha, tipo, True))

    con.commit()
    cur.close()

    return jsonify({
        'message': "Usuário cadastrado!",
        'usuarios': {
            'nome': nome,
            'telefone': telefone,
            'email': email,
            'tipo': tipo
        }
    }),200

@app.route('/cadastros/<int:id>', methods=['DELETE'])
def deletar_Usuario(id):
    cur = con.cursor()

    cur.execute("SELECT 1 FROM cadastros WHERE ID_USUARIO = ?", (id,))
    if not cur.fetchone():
        cur.close()
        return jsonify({"error": "Usuario não encontrado"}), 404

    cur.execute("DELETE FROM cadastros WHERE ID_USUARIO = ?", (id,))
    con.commit()
    cur.close()

    return jsonify({
        'message': "Usuario excluído com sucesso!",
        'id_usuario': id
    })

@app.route('/relatorio', methods=['GET'])
def criar_pdf():
    cursor = con.cursor()
    cursor.execute("SELECT ID_FILME, TITULO , GENERO , CLASSIFICACAO FROM filmes")
    usuarios = cursor.fetchall()
    cursor.close()

    pdf = FPDF()  # Configuração PDF
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", style='B', size=16)
    pdf.cell(200, 10, "Relatorio de Cadastro Usuário", ln=True, align='C')

    pdf.ln(5)  # Espaço entre o título e a linha
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())  # Linha abaixo do título
    pdf.ln(5)  # Espaço após a linha

    pdf.set_font("Arial", size=12)

    for usuario in usuarios:
        pdf.cell(200, 10, f"ID: {usuario[0]}", ln=True)
        pdf.cell(200, 10, f"Título: {usuario[1]}", ln=True)
        pdf.cell(200, 10, f"Gênero: {usuario[2]}", ln=True)
        pdf.cell(200, 10, f"Classificação: {usuario[3]}", ln=True)
        pdf.ln(5)  # Espaço entre cada usuário

    contador_usuarios = len(usuarios)  # Contagem dos filmes

    pdf.ln(10)  # Espaço antes do contador
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(200, 10, f"Total de usuários cadastrados: {contador_usuarios}", ln=True, align='C')

    pdf_path = "relatorio_usuarios.pdf"  # Define o caminho do PDF
    pdf.output(pdf_path)  # Salva o PDF no caminho especificado

    return send_file(pdf_path, as_attachment=True, mimetype='application/pdf')  # Envia o PDF gerado como anexo na resposta HTTP

@app.route('/cadastros/<int:id>', methods=['PUT'])
def atualizar_usuario(id):
    cur = con.cursor()
    cur.execute("SELECT id_cadastro, nome, telefone, email, senha, tipo, ativo FROM CADASTROS WHERE id_cadastro =?", (id,))
    usuarios_data = cur.fetchone()

    email_armazenado = usuarios_data[3]
    tipo_armazenado = usuarios_data[5]
    ativo_armazenado = usuarios_data[6]

    if not usuarios_data:
        cur.close()
        return jsonify({"error": "Usuário não foi encontrado"}), 404

    data = request.get_json()
    nome = data.get('nome')
    telefone = data.get('telefone')
    email = data.get('email')
    senha = data.get('senha')
    tipo = data.get('tipo')
    ativo = data.get('ativo')

    if tipo is None:
        tipo = tipo_armazenado
    if ativo is None:
        ativo = ativo_armazenado

    if email_armazenado != email:
        cur.execute("SELECT 1 FROM cadastros WHERE email = ?", (email,))

        if cur.fetchone():
            return jsonify({"message": "Este usuário já foi cadastrado!"}), 400

    senha = generate_password_hash(senha).decode('utf-8')

    cur.execute("update cadastros set nome = ?, telefone = ?, email = ?, senha = ?, tipo = ?, ativo = ?  where id_cadastro = ?",
                (nome, telefone, email, senha,tipo, ativo, id))

    con.commit()
    cur.close()

    return jsonify({
        'message': "Usuário atualizado com sucesso!",
        'usuarios': {
            'nome': nome,
            'telefone': telefone,
            'email': email,
            'senha': senha,
            'tipo': tipo,
            'ativo': ativo
        }
    })

tentativas = 0
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    senha = data.get('senha')
    global tentativas

    if not email or not senha:
        return jsonify({"error": "Todos os campos (email, senha) são obrigatórios."}), 400

    cur = con.cursor()
    cur.execute("SELECT senha, tipo, id_cadastro, ativo, nome, telefone, email FROM CADASTROS WHERE EMAIL = ?", (email,))
    usuario = cur.fetchone()
    cur.close()

    if not usuario:
        return jsonify({"error": "Usuário ou senha inválidos."}), 401
    email = usuario[6]

    ativo = usuario[3]

    if ativo != False:
        senha_armazenada = usuario[0]
        tipo = usuario[1]
        id_cadastro = usuario[2]

        if check_password_hash(senha_armazenada, senha):
            token = generate_token(id_cadastro, email)

            return jsonify({
                'message': "Login realizado com sucesso!",
                'usuarios': {
                    'nome': usuario[4],
                    'telefone': usuario[5],
                    'email': usuario[6],
                    'id_cadastro': usuario[2],
                    'tipo': usuario[1],
                    'token': token
                }
            })

        if tipo != 'adm':
            tentativas = tentativas + 1

            if tentativas == 3:
                cur = con.cursor()
                cur.execute("UPDATE CADASTROS SET ATIVO = false WHERE id_cadastro = ?", (id_cadastro,))
                con.commit()
                cur.close()
                return jsonify({"error": "Usuário inativado por excesso de tentativas."}), 403

        return jsonify({"error": "Senha incorreta."}), 401

    return jsonify({"error": "Usuário Inativo."}), 401

@app.route('/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization')

    if not token:
        return jsonify({"error": "Token de autenticação necessário"}), 401

    # Remove o 'Bearer' se presente no toke
    token = remover_bearer(token)

    try:
        #  validar sua assinatura e verificar a validade
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])

        # "removendo" o token no cliente.
        return jsonify({"message": "Logout realizado com sucesso!"}), 200

    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expirado"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token inválido"}), 401

@app.route('/filme_imagem', methods=['POST'])
def cadastar_filme_imagem():
    token = request.headers.get('Authorization')  # Verifica token

    if not token:  # Se não tiver token
        return jsonify({'mensagem': 'Token de autenticação necessário'}), 401

    token = remover_bearer(token)
    try:
        payload = jwt.decode(token, senha_secreta, algorithms=['HS256'])  # Identifica o código
        id_usuario = payload['id_usuario']  # Extrai id do usuário
    except jwt.ExpiredSignatureError:
        return jsonify({'mensagem': 'Token expirado'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'mensagem': 'Token inválido'}), 401

    titulo = request.form.get('titulo')
    classificacao = request.form.get('classificacao')
    genero = request.form.get('genero')
    sinopse = request.form.get('sinopse')
    imagem = request.files.get('imagem')  # Arquivo enviado
    duracao = request.form.get('duracao')

    cursor = con.cursor()
    # Verifica se o filme já existe
    cursor.execute("SELECT 1 FROM filmes WHERE TITULO = ?", (titulo,))
    if cursor.fetchone():
        cursor.close()
        return jsonify({"error": "Filme já cadastrado"}), 400

    # Insere o novo filme e retorna o ID gerado
    cursor.execute(
        "INSERT INTO filmes (TITULO, CLASSIFICACAO, GENERO, SINOPSE, DURACAO) VALUES (?, ?, ?, ?, ?) RETURNING ID_filme",
        (titulo, classificacao, genero, sinopse, duracao)
    )
    filme_id = cursor.fetchone()[0]
    con.commit()

    if imagem:
        nome_imagem = f"{filme_id}.jpeg"
        pasta_destino = os.path.join(app.config['UPLOAD_FILMES'], "Filmes")  # Onde vai ser salvo
        os.makedirs(pasta_destino, exist_ok=True)  # Cria o diretório de destino (caso não exista)
        imagem_path = os.path.join(pasta_destino, nome_imagem)
        imagem.save(imagem_path)  # Salva a imagem no caminho definido

    cursor.close()

    return jsonify({
        'message': "Filme cadastrado com sucesso!",
        'Filmes': {
            'id': filme_id,
            'titulo': titulo,
            'classificacao': classificacao,
            'genero': genero,
            'sinopse': sinopse,
            'imagem_path': imagem_path,
            'duracao': duracao
        }
    }), 201

@app.route('/filmes', methods=['GET'])
def listar_filmes():
    cur = con.cursor()
    cur.execute("SELECT id_filme, titulo, classificacao, genero, sinopse FROM filmes WHERE SITUACAO = 1")
    filmes = cur.fetchall()

    filmes_lista = []  # Cria uma lista vazia para armazenar os filmes

    # Itera sobre os resultados obtidos
    for filme in filmes:
        filmes_lista.append({
            'id_filme': filme[0],  # Armazena o 'id_filme' na chave 'id_filme'
            'titulo': filme[1],    # Armazena o 'titulo' na chave 'titulo'
            'classificacao': filme[2],  # Armazena a 'classificacao' na chave 'classificacao'
            'genero': filme[3],    # Armazena o 'genero' na chave 'genero'
            'sinopse': filme[4],   # Armazena a 'sinopse' na chave 'sinopse'
        })

    cur.close()  # Fecha o cursor
    return jsonify({
        'mensagem': "Lista de filmes",  # Mensagem explicando que a resposta contém a lista de filmes
        'filmes': filmes_lista  # Retorna a lista de filmes na chave 'filmes'
    })

@app.route('/filme_imagem/<int:id>', methods=['PUT'])
def atualizar_filme(id):
    cur = con.cursor()
    cur.execute("SELECT id_filme, titulo, genero, classificacao, sinopse, situacao FROM FILMES WHERE id_filme =?", (id,))
    filme_data = cur.fetchone()

    if not filme_data:  # Se não existir, vai retornar um erro
        cur.close()
        return jsonify({"error": "Filme não foi encontrado"}), 404

    titulo_armazenado = filme_data[1]  # Armazena o título do filme
    situacao_armazenada = filme_data[5]

    # Captura os dados do formulário e normaliza
    titulo = normalizar_texto(request.form.get('titulo'))
    classificacao = normalizar_texto(request.form.get('classificacao'))
    genero = normalizar_texto(request.form.get('genero'))
    sinopse = normalizar_texto(request.form.get('sinopse'))
    situacao = normalizar_texto(request.form.get('situacao'))
    imagem = request.files.get('imagem')  # Arquivo enviado

    if not situacao:
        situacao = situacao_armazenada

    if titulo_armazenado != titulo:  # Verifica se o título foi modificado
        cur.execute("SELECT 1 FROM filmes WHERE titulo = ?", (titulo,))
        if cur.fetchone():  # Retorna com o erro
            cur.close()
            return jsonify({"message": "Este filme já foi cadastrado!"}), 400

    cur.execute(
        "UPDATE filmes SET titulo = ?, genero = ?, classificacao = ?, sinopse = ?, situacao = ? WHERE id_filme = ?",
        (titulo, genero, classificacao, sinopse, situacao, id)
    )

    con.commit()
    imagem_path = None
    if imagem:  # Define nova imagem
        nome_imagem = f"{filme_data[0]}.jpeg"
        pasta_destino = os.path.join(app.config['UPLOAD_FILMES'], "Filmes")
        os.makedirs(pasta_destino, exist_ok=True)
        imagem_path = os.path.join(pasta_destino, nome_imagem)
        imagem.save(imagem_path)

    cur.close()

    return jsonify({
        'message': "Filme atualizado com sucesso!",
        'filmes': {
            'titular': titulo,
            'genero': genero,
            'classificacao': classificacao,
            'sinopse': sinopse,
            'situacao': situacao,
            'imagem_path': imagem_path
        }
    })

@app.route('/filmes/<int:id_filme>/inativar', methods=['PUT'])
def inativar_filme(id_filme):
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'mensagem': 'Token de autenticação necessário'}), 401

    token = remover_bearer(token)

    try:
        payload = jwt.decode(token, senha_secreta, algorithms=['HS256'])
        id_cadastro = payload.get('id_usuario')  # Alterado para user_type
    except jwt.ExpiredSignatureError:
        return jsonify({'mensagem': 'Token expirado'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'mensagem': 'Token inválido'}), 401

    # Verificar se o usuário é um administrador
    adm = verificar_adm(id_cadastro)
    if not adm:
        return jsonify({'mensagem': 'Apenas administradores podem inativar filmes.'}), 403

    # Conectar ao banco de dados
    cur = con.cursor()

    # Verificar se o filme existe no banco de dados
    cur.execute("SELECT situacao FROM FILMES WHERE ID_FILME = ?", (id_filme,))
    filme = cur.fetchone()

    if not filme:
        cur.close()
        return jsonify({'error': 'Filme não encontrado'}), 404

    # Atualizar a situação do filme
    nova_situacao = 0 if filme[0] == 1 else 1  # Alterna entre 0 e 1

    cur.execute("UPDATE FILMES SET situacao = ? WHERE ID_FILME = ?", (nova_situacao, id_filme))
    con.commit()
    cur.close()

    # Retornar mensagem de sucesso
    situacao_str = "inativo" if nova_situacao == 0 else "ativo"
    return jsonify({'mensagem': f'Filme {situacao_str} com sucesso!'}), 200

@app.route('/sessoes', methods=['POST'])
def cadastrar_sessao():
    data = request.get_json()
    id_sala = data.get('id_sala')
    horario = data.get('horario')  # esperado: HH:MM
    data_sessao = data.get('data_sessao')  # esperado: AAAA-MM-DD
    id_filme = data.get('id_filme')
    valor_unitario = data.get('valor_unitario')

    if not all([id_sala, horario, data_sessao, id_filme, valor_unitario]):
        return jsonify({"error": "Todos os campos são obrigatórios"}), 400

    # Verifica se a data e o horário não são retroativos
    try:
        data_hora_sessao = datetime.strptime(f"{data_sessao} {horario}", "%Y-%m-%d %H:%M")
        if data_hora_sessao <= datetime.now():
            return jsonify({"error": "A data e o horário da sessão estão inválidos"}), 400
    except ValueError:
        return jsonify({"error": "Formato inválido de data ou horário."}), 400

    cur = con.cursor()

    # Verifica se o filme existe e pega a duração
    cur.execute("SELECT duracao FROM filmes WHERE id_filme = ?", (id_filme,))
    resultado = cur.fetchone()
    if not resultado:
        cur.close()
        return jsonify({"error": "Filme não encontrado"}), 404

    duracao = resultado[0]  # Duração do filme em minutos
    fim_sessao = data_hora_sessao + timedelta(minutes=duracao)

    # Verifica se a sala existe
    cur.execute("SELECT 1 FROM salas WHERE id_salas = ?", (id_sala,))
    if not cur.fetchone():
        cur.close()
        return jsonify({"error": "Sala não encontrada"}), 404

    # Verifica se já existe uma sessão em conflito na mesma sala, data e horário
    cur.execute("""
        SELECT id_sessao, data_sessao, horario
        FROM sessoes
        WHERE id_sala = ? AND data_sessao = ?
        AND (
            (data_sessao = ? AND horario BETWEEN ? AND ?) OR -- A nova sessão começa durante a sessão existente
            (data_sessao = ? AND ? BETWEEN horario AND ?)   -- A nova sessão termina durante a sessão existente
        )
    """, (id_sala, data_sessao, data_sessao, data_hora_sessao.time(), fim_sessao.time(), data_sessao, data_hora_sessao.time(), fim_sessao.time()))

    if cur.fetchone():
        cur.close()
        return jsonify({"error": "Sala indisponível, já existe uma sessão nesse horário!"}), 409

    # Insere a nova sessão
    cur.execute("INSERT INTO sessoes (id_sala, horario, data_sessao, id_filme, valor_unitario) VALUES (?, ?, ?, ?, ?)",
                (id_sala, horario, data_sessao, id_filme, valor_unitario))

    con.commit()
    cur.close()

    return jsonify({"message": "Sessão adicionada com sucesso!"}), 201

@app.route('/sessoes/<int:id_filme>', methods=['GET'])
def listar_sessoes(id_filme):
    cur = con.cursor()
    cur.execute("""
        SELECT s.id_sessao, 
               s.id_sala, 
               sa.descricao, 
               s.horario, 
               s.data_sessao, 
               s.id_filme, 
               f.titulo, 
               s.valor_unitario, 
               f.duracao
        FROM sessoes s 
        LEFT JOIN filmes f ON f.id_filme = s.id_filme
        LEFT JOIN salas sa ON sa.id_salas = s.id_sala
        WHERE s.id_filme = ?
    """, (id_filme,))

    sessoes = cur.fetchall()
    sessoes_dic = []

    for sessao in sessoes:
        horario = sessao[3]
        data_sessao = sessao[4]

        # Converte horário e data corretamente
        if isinstance(horario, str):
            horario = datetime.strptime(horario, "%H:%M:%S").time()
        if isinstance(data_sessao, str):
            data_sessao = datetime.strptime(data_sessao, "%Y-%m-%d").date()

        # Junta data + hora e compara
        data_hora_sessao = datetime.combine(data_sessao, horario)
        if data_hora_sessao <= datetime.now():
            continue  # pula sessões passadas

        valor_unitario = sessao[7]
        duracao = sessao[8]

        valor_unitario = float(valor_unitario) if valor_unitario is not None else 0.0
        duracao = int(duracao) if duracao is not None else 0

        sessoes_dic.append({
            'id_sessao': sessao[0],
            'id_sala': sessao[1],
            'descricao': sessao[2],
            'horario': horario.strftime("%H:%M:%S"),
            'data_sessao': data_sessao.strftime("%Y-%m-%d"),
            'id_filme': sessao[5],
            'titulo': sessao[6],
            'valor_unitario': valor_unitario,
            'duracao': duracao
        })

    cur.close()

    return jsonify({
        "mensagem": "Lista de sessões",
        "sessoes": sessoes_dic
    })

@app.route('/sessoes/<int:id>', methods=['PUT'])
def editar_sessao(id):
    cur = con.cursor()

    # Busca a sessão pelo id
    cur.execute("SELECT id_sessao, id_sala, horario, data_sessao, id_filme FROM sessoes WHERE id_sessao =?", (id,))
    sessao_data = cur.fetchone()

    if not sessao_data:
        cur.close()
        return jsonify({"error": "Sessão não foi encontrada"}), 404

    # Recebe os dados da requisição
    data = request.get_json()
    id_sala = data.get('id_sala', sessao_data[1])
    horario = data.get('horario', sessao_data[2])
    data_sessao = data.get('data_sessao', sessao_data[3])
    id_filme = data.get('id_filme', sessao_data[4])

    # Atualiza os dados da sessão
    cur.execute("""UPDATE sessoes SET id_sala = ?, horario = ?, data_sessao = ?, id_filme = ? WHERE id_sessao = ?""",
                (id_sala, horario, data_sessao, id_filme, id))

    con.commit()
    cur.close()

    return jsonify({
        'message': "Sessão atualizada com sucesso!",
        'sessao': {
            'id_sessao': id,
            'id_sala': id_sala,
            'horario': horario,
            'data_sessao': data_sessao,
            'id_filme': id_filme
        }
    })

@app.route('/sessoes/<int:id>', methods=['DELETE'])
def deletar_sessao(id):
    cur = con.cursor()

    # Verifica se a sessão existe
    cur.execute("SELECT 1 FROM sessoes WHERE id_sessao = ?", (id,))
    if not cur.fetchone():
        cur.close()
        return jsonify({"error": "Sessão não encontrada"}), 404

    # Deleta a sessão
    cur.execute("DELETE FROM sessoes WHERE id_sessao = ?", (id,))
    con.commit()
    cur.close()

    return jsonify({
        'message': "Sessão excluída com sucesso!",
        'id_sessao': id
    })

@app.route('/reservas', methods=['POST'])
def fazer_reserva():
    # Autenticação via token
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'mensagem': 'Token de autenticação necessário'}), 401

    token = remover_bearer(token)
    try:
        payload = jwt.decode(token, senha_secreta, algorithms=['HS256'])
        id_cadastro = payload['id_usuario']
        email = payload['email']
    except jwt.ExpiredSignatureError:
        return jsonify({'mensagem': 'Token expirado'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'mensagem': 'Token inválido'}), 401

    # Dados da requisição
    data = request.get_json()
    id_sessao = int(data.get('id_sessao'))
    id_assentos = data.get('id_assento')  # deve ser uma lista
    id_assentos = [int(i) for i in id_assentos]

    try:
        id_assentos = list(map(int, id_assentos))
    except (ValueError, TypeError):
        return jsonify({'erro': 'id_assento deve conter apenas valores inteiros'}), 400

    if not isinstance(id_assentos, list) or not id_assentos:
        return jsonify({'erro': 'id_assento deve ser uma lista com pelo menos um valor'}), 400

    cur = con.cursor()

    # Verifica se a sessão existe
    cur.execute("SELECT 1 FROM SESSOES WHERE ID_SESSAO = ?", (id_sessao,))
    if not cur.fetchone():
        cur.close()
        return jsonify({"error": "Sessão não encontrada"}), 404

    # Verifica se todos os assentos existem
    query = f"SELECT ID_ASSENTO FROM ASSENTO WHERE ID_ASSENTO IN ({','.join('?' * len(id_assentos))})"
    cur.execute(query, id_assentos)
    assentos_existentes = [row[0] for row in cur.fetchall()]
    if set(id_assentos) != set(assentos_existentes):
        cur.close()
        return jsonify({"error": "Um ou mais assentos não existem"}), 404

    # Verifica se os assentos já estão reservados
    query = f"""
        SELECT ar.ID_ASSENTO
        FROM ASSENTOS_RESERVADOS ar
        JOIN RESERVA r ON ar.ID_RESERVA = r.ID_RESERVA
        WHERE r.ID_SESSAO = ? AND ar.ID_ASSENTO IN ({','.join('?' * len(id_assentos))})
    """
    cur.execute(query, [id_sessao] + id_assentos)
    reservados = [row[0] for row in cur.fetchall()]
    if reservados:
        cur.close()
        return jsonify({"error": f"Os assentos {reservados} já estão reservados"}), 400

    # Cria a reserva principal
    cur.execute("""
        INSERT INTO RESERVA (ID_SESSAO, ID_CADASTRO, STATUS)
        VALUES (?, ?, ?)
        RETURNING ID_RESERVA
    """, (id_sessao, id_cadastro, 'Confirmada'))
    id_reserva = cur.fetchone()[0]

    # Relaciona os assentos com a reserva
    for assento in id_assentos:
        cur.execute("""
            INSERT INTO ASSENTOS_RESERVADOS (ID_RESERVA, ID_ASSENTO)
            VALUES (?, ?)
        """, (id_reserva, assento))

    con.commit()

    # 1. Buscar o valor unitário da sessão
    cur.execute("SELECT COALESCE(valor_unitario,0) FROM sessoes WHERE id_sessao = ?", (id_sessao,))
    resultado = cur.fetchone()
    cur.close()

    if not resultado:
        return jsonify({"error": "Sessão não encontrada para cálculo de valor"}), 404

    valor_unitario = resultado[0]

    # 2. Calcular o valor total da reserva
    valor_total = len(id_assentos) * float(valor_unitario)

    cursor = con.cursor()
    cursor.execute("update reserva set valor_total = ? where id_reserva = ?",(valor_total, id_reserva))
    con.commit()
    cursor.close()

    # 3. Buscar dados da chave PIX
    cursor = con.cursor()
    cursor.execute("SELECT RAZAO_SOCIAL, CHAVE_PIX, CIDADE FROM CONFIG_CINE")
    res = cursor.fetchone()
    cursor.close()

    # Separa as informações trazidas do banco
    razao_social, chave_pix, cidade = res
    razao_social = razao_social[:25]
    cidade = cidade[:15]

    # 4. Gerar código PIX

    # Monta as informações do recebedor
    merchant_info = format_tlv("00", "br.gov.bcb.pix") + format_tlv("01", chave_pix)
    campo_26 = format_tlv("26", merchant_info)

    # Monta o Payload PIX (sem o CRC ainda)
    payload_sem_crc = (
        "000201"
        "010212"
        f"{campo_26}"
        "52040000"
        "5303986"
        f"{format_tlv('54', f'{valor_total:.2f}')}"
        "5802BR"
        f"{format_tlv('59', razao_social)}"
        f"{format_tlv('60', cidade)}"
        f"{format_tlv('62', format_tlv('05', '***'))}"
        "6304"
    )

    # Calcula o CRC16 do payload (para garantir a validade do QR Code)
    crc = calcula_crc16(payload_sem_crc)
    codigo_pix = payload_sem_crc + crc

    # Gerar o QR Code imagem
    qr = qrcode.make(codigo_pix)
    nome_arquivo_qr = f"pix_reserva_{id_reserva}.png"
    caminho_qr = os.path.join(os.getcwd(), "upload", "qrcodes")
    os.makedirs(caminho_qr, exist_ok=True)
    caminho_qr_completo = os.path.join(caminho_qr, nome_arquivo_qr)
    qr.save(caminho_qr_completo)


    # EMAIL
    cursor = con.cursor()
    cursor.execute("SELECT nome FROM CADASTROS WHERE ID_CADASTRO = ?", (id_cadastro,))
    nome_usuario = cursor.fetchone()[0]
    cursor.close()

    # Detalhes da sessão
    cursor = con.cursor()
    cursor.execute("""
        SELECT f.titulo, sa.descricao, s.data_sessao, s.horario
        FROM sessoes s
        JOIN filmes f ON f.id_filme = s.ID_FILME
        JOIN salas sa ON sa.ID_SALAS = s.ID_SALA
        WHERE s.ID_SESSAO = ?
    """, (id_sessao,))
    titulo_filme, sala, data_sessao, horario = cursor.fetchone()
    cursor.close()

    data_formatada = data_sessao.strftime('%d-%m-%Y')

    # Monta e envia o e-mail
    texto = f"""Olá, {nome_usuario}!

Sua reserva foi realizada com sucesso. Aqui estão os detalhes da sua sessão:

🎬 Filme: {titulo_filme}
🎟 Sala: {sala}
📅 Data: {data_formatada}
⏰ Horário: {horario}
💺 Assentos: {', '.join(map(str, id_assentos))}
💰 Valor total: R$ {valor_total:.2f}

Para efetuar o pagamento via PIX, copie o código abaixo e cole no app do seu banco:

🔢 Código PIX:
{codigo_pix}

Ou, se preferir, escaneie o QR Code em anexo! 📲

Estamos ansiosos para te receber na sessão! Prepare a pipoca! 🍿✨

Atenciosamente,
Equipe PrimeCine
"""

    mensagem = "Reserva realizada com sucesso!"
    erro_email = None
    try:
        enviar_email_para(email, texto, caminho_qr_completo)
    except Exception as e:
        mensagem = "Reserva feita com sucesso, mas falha ao enviar e-mail."
        erro_email = str(e)

    return jsonify({
        'mensagem': mensagem,
        'reserva': {
            'id_reserva': id_reserva,
            'id_sessao': id_sessao,
            'id_assentos': id_assentos,
            'id_cadastro': id_cadastro
        },
        'erro_email': erro_email
    }), 200

@app.route('/reservas', methods=['GET'])
def listar_reservas():

 # Autenticação via token
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'mensagem': 'Token de autenticação necessário'}), 401

    token = remover_bearer(token)
    try:
        payload = jwt.decode(token, senha_secreta, algorithms=['HS256'])
        id_cadastro = payload['id_usuario']
        email = payload['email']
    except jwt.ExpiredSignatureError:
        return jsonify({'mensagem': 'Token expirado'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'mensagem': 'Token inválido'}), 401

    # Consulta ao banco de dados
    cur = con.cursor()

    # Obter todas as reservas, juntando as tabelas RESERVA, SESSOES e FILMES
    cur.execute("""
        SELECT r.ID_RESERVA, f.TITULO, s.DATA_SESSAO, s.HORARIO, sa.DESCRICAO, r.STATUS
        FROM RESERVA r
        JOIN SESSOES s ON r.ID_SESSAO = s.ID_SESSAO
        JOIN FILMES f ON s.ID_FILME = f.ID_FILME
        JOIN SALAS sa ON s.ID_SALA = sa.ID_SALAS
        where r.id_cadastro = ? 
    """, (id_cadastro, ))

    reservas = cur.fetchall()
    cur.close()

    # Formatar as reservas para um formato mais legível
    reservas_formatadas = []

    for reserva in reservas:
        id_reserva, titulo_filme, data_sessao, horario, sala, status = reserva

    # Buscar os assentos dessa reserva
        cur.execute("SELECT ID_ASSENTO FROM ASSENTOS_RESERVADOS WHERE ID_RESERVA = ?", (id_reserva,))
        assentos_raw = cur.fetchall()
        assentos = [row[0] for row in assentos_raw]


        # Convertendo o horário para string, caso seja do tipo time
        if isinstance(horario, time):
            horario = horario.strftime('%H:%M:%S')

        reservas_formatadas.append({
            "id_reserva": id_reserva,
            "titulo_filme": titulo_filme,
            "data_sessao": data_sessao,
            "horario": horario,
            "sala": sala,
            "status": status,
            "assentos":assentos
        })

    # Retorna os dados como JSON
    return jsonify(reservas=reservas_formatadas)

@app.route('/assentos_reservados/<int:id_sessao>', methods=['GET'])
def listar_assentos(id_sessao):
    cur = con.cursor()

    query = """
        SELECT 
            a.id_assento,
            a.id_sala,
            a.fileira,
            a.numero,
            r.id_sessao,
            r.id_reserva
        FROM assentos_reservados ar
        JOIN assento a ON a.id_assento = ar.id_assento
        JOIN reserva r ON r.id_reserva = ar.id_reserva
        WHERE r.id_sessao = ?
    """

    cur.execute(query, (id_sessao,))
    assentos = cur.fetchall()
    cur.close()

    lista_reservados = []
    for assento in assentos:
        lista_reservados.append({
            'id_assento': assento[0],
            'id_sala': assento[1],
            'fileira': assento[2],
            'numero': assento[3],
            'id_sessao': assento[4],
            'id_reserva': assento[5]
        })

    return jsonify({
        'mensagem': f'Assentos reservados para a sessão {id_sessao}',
        'assentos': lista_reservados
    }), 200

@app.route('/salas', methods=['POST'])
def cadastro_salas():
    data = request.get_json()
    capacidade = data.get('capacidade')
    descricao = data.get('descricao')

    if not all([capacidade, descricao]):
        return jsonify({"error": "descricao e capacidade são obrigatórios"}), 400

    cur = con.cursor()

    # Insere a nova sala
    cur.execute("INSERT INTO SALAS (CAPACIDADE, DESCRICAO) VALUES ( ?, ?)",
                (capacidade, descricao))

    con.commit()
    cur.close()

    return jsonify({
        'message': "Sala cadastrada com sucesso!",
        'sala': {
            'capacidade': capacidade,
            'descricao': descricao,
        }
    }), 200

@app.route('/salas', methods=['GET'])
def listar_salas():
    cur = con.cursor()

    # Consulta para listar todas as salas
    cur.execute("SELECT * FROM SALAS")
    salas = cur.fetchall()
    cur.close()

    # Se não houver salas cadastradas
    if not salas:
        return jsonify({"message": "Nenhuma sala encontrada."}), 404

    # Formata as salas para uma resposta JSON
    salas_listadas = []
    for sala in salas:
        salas_listadas.append({
            'id_sala': sala[0],
            'capacidade': sala[1],
            'descricao': sala[2],
        })

    return jsonify({
        'message': "Salas encontradas com sucesso!",
        'salas': salas_listadas
    }), 200


def calcula_crc16(payload):
    crc16 = crcmod.mkCrcFun(0x11021, initCrc=0xFFFF, rev=False)
    crc = crc16(payload.encode('utf-8'))
    return f"{crc:04X}"

def format_tlv(id, value):
    return f"{id}{len(value):02d}{value}"

@app.route('/gerar_pix', methods=['POST'])
def gerar_pix():
    try:
        data = request.get_json()
        if not data or 'valor' not in data:
            return jsonify({"erro": "O valor do PIX é obrigatório."}), 400

        valor = f"{float(data['valor']):.2f}"

        cursor = con.cursor()
        cursor.execute("SELECT cg.RAZAO_SOCIAL, cg.CHAVE_PIX, cg.CIDADE FROM CONFIG_CINE cg")
        resultado = cursor.fetchone()
        cursor.close()

        if not resultado:
            return jsonify({"erro": "Chave PIX não encontrada"}), 404

        nome, chave_pix, cidade = resultado
        nome = nome[:25] if nome else "Recebedor PIX"
        cidade = cidade[:15] if cidade else "Cidade"

        # Monta o campo 26 (Merchant Account Information) com TLVs internos
        merchant_account_info = (
                format_tlv("00", "br.gov.bcb.pix") +
                format_tlv("01", chave_pix)
        )

        campo_26 = format_tlv("26", merchant_account_info)

        payload_sem_crc = (
                "000201" +  # Payload Format Indicator
                "010212" +  # Point of Initiation Method
                campo_26 +  # Merchant Account Information
                "52040000" +  # Merchant Category Code
                "5303986" +  # Currency - 986 = BRL
                format_tlv("54", valor) +  # Transaction amount
                "5802BR" +  # Country Code
                format_tlv("59", nome) +  # Merchant Name
                format_tlv("60", cidade) +  # Merchant City
                format_tlv("62", format_tlv("05", "***")) +  # Additional data (TXID)
                "6304"  # CRC placeholder
        )

        crc = calcula_crc16(payload_sem_crc)
        payload_completo = payload_sem_crc + crc

        # Criação do QR Code com configurações aprimoradas
        qr_obj = qrcode.QRCode(
            version=None,  # Permite ajuste automático da versão
            error_correction=ERROR_CORRECT_H,  # Alta correção de erros (30%)
            box_size=10,
            border=4
        )
        qr_obj.add_data(payload_completo)
        qr_obj.make(fit=True)
        qr = qr_obj.make_image(fill_color="black", back_color="white")

        # Cria a pasta 'upload/qrcodes' relativa ao diretório do projeto
        pasta_qrcodes = os.path.join(os.getcwd(), "upload", "qrcodes")
        os.makedirs(pasta_qrcodes, exist_ok=True)

        # Conta quantos arquivos já existem com padrão 'pix_*.png'
        arquivos_existentes = [f for f in os.listdir(pasta_qrcodes) if f.startswith("pix_") and f.endswith(".png")]
        numeros_usados = []
        for nome_arq in arquivos_existentes:
            try:
                num = int(nome_arq.replace("pix_", "").replace(".png", ""))
                numeros_usados.append(num)
            except ValueError:
                continue
        proximo_numero = max(numeros_usados, default=0) + 1
        nome_arquivo = f"pix_{proximo_numero}.png"
        caminho_arquivo = os.path.join(pasta_qrcodes, nome_arquivo)

        # Salva o QR Code no disco
        qr.save(caminho_arquivo)

        print(payload_completo)

        return send_file(caminho_arquivo, mimetype='image/png', as_attachment=True, download_name=nome_arquivo)
    except Exception as e:
        return jsonify({"erro": f"Ocorreu um erro internosse: {str(e)}"}), 500