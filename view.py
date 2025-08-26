
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
from itsdangerous import URLSafeTimedSerializer
from itsdangerous import SignatureExpired, BadSignature
import os
import base64
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import fdb
from datetime import date
import random
from werkzeug.security import generate_password_hash


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

import unicodedata

def normalizar_texto(texto):
    if texto is None:
        return ""
    texto = str(texto)
    return unicodedata.normalize('NFC', texto)


def enviar_email_para(destinatario, corpo_html,  assunto="PrimeCine", caminho_anexo=None):

    try:
        msg = MIMEMultipart()
        msg['From'] = 'primecine00@gmail.com'
        msg['To'] = destinatario
        msg['Subject'] = assunto

        # Corpo do e-mail (HTML)
        msg.attach(MIMEText(corpo_html, 'html'))

        # Anexo (caso exista)
        if caminho_anexo and os.path.exists(caminho_anexo):
            with open(caminho_anexo, 'rb') as f:
                parte = MIMEBase('application', 'octet-stream')
                parte.set_payload(f.read())
                encoders.encode_base64(parte)
                parte.add_header(
                    'Content-Disposition',
                    f'attachment; filename={os.path.basename(caminho_anexo)}'
                )
                msg.attach(parte)

        # Envia e-mail via Gmail
        servidor = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        servidor.login('primecine00@gmail.com', 'zzzj kwhn mnhb vtrx')  # Senha de app do Gmail
        servidor.send_message(msg)
        servidor.quit()
        print('E-mail enviado com sucesso!')

    except smtplib.SMTPConnectError as e:
        print(f"Erro de conexão com SMTP: {e}")
    except smtplib.SMTPAuthenticationError as e:
        print(f"Erro de autenticação SMTP: {e}")
    except smtplib.SMTPException as e:
        print(f"Erro ao enviar e-mail: {e}")
    except Exception as e:
        print(f"Erro inesperado: {e}")

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
@app.route('/teste')
def teste():
    return 'OK'

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

    # Hash da senha com Werkzeug — NÃO usa .decode()
    senha = generate_password_hash(senha)

    cur.execute(
        "INSERT INTO CADASTROS (NOME, TELEFONE, EMAIL, SENHA, TIPO, ativo) VALUES (?, ?, ?, ?, ?, ?)",
        (nome, telefone, email, senha, tipo, True)
    )

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
    }), 200

@app.route('/cadastros/<int:id>', methods=['DELETE'])
def deletar_Usuario(id):
    cur = con.cursor()

    cur.execute("SELECT 1 FROM cadastros WHERE id_cadastro = ?", (id,))
    if not cur.fetchone():
        cur.close()
        return jsonify({"error": "Usuario não encontrado"}), 404

    cur.execute("DELETE FROM cadastros WHERE id_cadastro = ?", (id,))
    con.commit()
    cur.close()

    return jsonify({
        'message': "Usuario excluído com sucesso!",
        'id_usuario': id
    })



@app.route('/relatorio', methods=['GET'])
def criar_pdf():
    cur = con.cursor()

    # Adicionando a cláusula WHERE para filtrar apenas os filmes ativos
    cur.execute(
        "SELECT ID_FILME, TITULO, GENERO, CLASSIFICACAO FROM filmes WHERE situacao = ?", (1,))
    filmes = cur.fetchall()
    cur.close()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Título - Ajustando o tamanho da fonte
    pdf.set_font("Arial", style='B', size=14)  # Tamanho da fonte do título foi alterado para 14
    pdf.cell(200, 10, "Relatório de Filmes Cadastrados", ln=True, align='C')
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)

    # Cabeçalho da tabela
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(30, 10, "ID", border=1, align='C')
    pdf.cell(70, 10, "Título", border=1, align='C')
    pdf.cell(50, 10, "Gênero", border=1, align='C')
    pdf.cell(40, 10, "Classificação", border=1, align='C')
    pdf.ln()

    # Dados da tabela
    pdf.set_font("Arial", size=12)
    for filme in filmes:
        pdf.cell(30, 10, str(filme[0]), border=1, align='C')

        # Evitar quebra de linha no título
        titulo = str(filme[1])
        pdf.cell(70, 10, titulo, border=1, align='C')  # Título sem quebra de linha

        pdf.cell(50, 10, str(filme[2]), border=1, align='C')
        pdf.cell(40, 10, str(filme[3]), border=1, align='C')

        pdf.ln()  # Nova linha após cada linha de dados

    # Total
    pdf.ln(10)
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(200, 10, f"Total de filmes cadastrados: {len(filmes)}", ln=True, align='C')

    # Salvar e enviar
    pdf_path = "relatorio_filmes.pdf"
    pdf.output(pdf_path)
    return send_file(pdf_path, as_attachment=True, mimetype='application/pdf')


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

    senha = generate_password_hash(senha)

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

    senha_armazenada = usuario[0]
    tipo = usuario[1]
    id_cadastro = usuario[2]
    ativo = usuario[3]

    if ativo != False:
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

codigos_temp = {}

# Endpoint: Solicitar recuperação de senha
@app.route('/esqueci-minha-senha', methods=['POST'])
def esqueci_minha_senha():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"error": "Informe o email."}), 400

    # Simula a busca no banco
    cur = con.cursor()
    cur.execute("SELECT id_cadastro, nome FROM cadastros WHERE email = ?", (email,))
    usuario = cur.fetchone()
    cur.close()

    if not usuario:
        return jsonify({"error": "Email não encontrado."}), 404

    id_cadastro, nome = usuario

    # Gera código e define validade de 10 minutos
    codigo = str(random.randint(100000, 999999))
    expiracao = datetime.now() + timedelta(minutes=10)
    codigos_temp[email] = (codigo, expiracao)

    corpo_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px; color: #333;">
        <div style="max-width: 600px; margin: auto; background-color: #fff; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.05); padding: 20px;">
          <h2 style="color: #cc0000;">Olá, {nome}!</h2>
          <p>Recebemos uma solicitação para redefinir a sua senha.</p>

          <p style="margin-top: 20px;">Use o código abaixo para continuar com o processo de redefinição. Ele é válido por <strong>10 minutos</strong>:</p>

          <div style="font-size: 24px; font-weight: bold; color: #cc0000; background-color: #f2f2f2; padding: 15px; text-align: center; border-radius: 5px; margin: 20px 0;">
            {codigo}
          </div>

          <p style="margin-top: 30px;">Se você não solicitou essa alteração, ignore este e-mail com segurança.</p>

          <p style="color: #888; font-size: 12px; margin-top: 40px;">Atenciosamente,<br>Equipe <strong>PrimeCine</strong></p>
        </div>
      </body>
    </html>
    """

    enviar_email_para(email, corpo_html, assunto="Código de Recuperação - PrimeCine")
    return jsonify({"message": "Código enviado para o e-mail."})


@app.route('/verificar-codigo', methods=['POST'])
def verificar_codigo():
    data = request.get_json()
    email = data.get('email')
    codigo_recebido = data.get('codigo')

    print(f"Verificando código para email: {email}, código recebido: {codigo_recebido}")

    if not email or not codigo_recebido:
        return jsonify({"error": "Informe o email e o código."}), 400

    codigo_salvo, validade = codigos_temp.get(email, (None, None))

    print(f"Código salvo: {codigo_salvo}, validade: {validade}")

    if not codigo_salvo:
        return jsonify({"error": "Nenhum código encontrado para este e-mail."}), 404

    if datetime.now() > validade:
        del codigos_temp[email]
        return jsonify({"error": "Código expirado."}), 410

    if codigo_recebido != codigo_salvo:
        return jsonify({"error": "Código incorreto."}), 401

    # Código está válido
    del codigos_temp[email]  # remove para evitar reuso
    return jsonify({"message": "Código verificado com sucesso."})


@app.route('/redefinir-senha', methods=['POST'])
def redefinir_senha():
    data = request.get_json()
    email = data.get('email')
    nova_senha = data.get('nova_senha')

    if not email or not nova_senha:
        return jsonify({"error": "Informe o email e a nova senha."}), 400

    senha_hash = generate_password_hash(nova_senha)  # ✅ Usa hash compatível com login

    cur = con.cursor()
    cur.execute("SELECT id_cadastro FROM cadastros WHERE email = ?", (email,))
    if not cur.fetchone():
        cur.close()
        return jsonify({"error": "Email não encontrado."}), 404

    cur.execute("UPDATE cadastros SET senha = ? WHERE email = ?", (senha_hash, email))
    con.commit()
    cur.close()

    return jsonify({"message": "Senha redefinida com sucesso."})

@app.route('/filme_imagem', methods=['POST'])
def cadastrar_filme_imagem():
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
    link = request.form.get('link')  # Novo campo para o link

    # Validação simples para evitar campos vazios (exemplo)
    if not titulo:
        return jsonify({"error": "O campo título é obrigatório."}), 400

    cursor = con.cursor()
    # Verifica se o filme já existe
    cursor.execute("SELECT 1 FROM filmes WHERE LOWER(TRIM(TITULO)) = LOWER(TRIM(?))", (titulo,))
    if cursor.fetchone():
        cursor.close()
        return jsonify({"error": "Filme já cadastrado"}), 400

    # Insere o novo filme e retorna o ID gerado
    cursor.execute(
        "INSERT INTO filmes (TITULO, CLASSIFICACAO, GENERO, SINOPSE, DURACAO, LINK) VALUES (?, ?, ?, ?, ?, ?)",
        (titulo, classificacao, genero, sinopse, duracao, link)
    )
    con.commit()

    # Recupera o ID do filme inserido
    cursor.execute("SELECT ID_filme FROM filmes WHERE LOWER(TRIM(TITULO)) = LOWER(TRIM(?))", (titulo,))
    filme_id = cursor.fetchone()[0]

    imagem_path = None  # Define imagem_path para evitar erro se não enviar imagem
    if imagem:
        nome_imagem = f"{filme_id}.jpeg"
        pasta_destino = os.path.join(app.config['UPLOAD_FILMES'], "Filmes")
        os.makedirs(pasta_destino, exist_ok=True)
        imagem_path = os.path.join(pasta_destino, nome_imagem)
        imagem.save(imagem_path)

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
            'duracao': duracao,
            'link': link
        }
    }), 201


@app.route('/filmes', methods=['GET'])
def listar_filmes():
    cur = con.cursor()
    cur.execute("SELECT id_filme, titulo, classificacao, genero, sinopse, duracao, link FROM filmes WHERE SITUACAO = 1")
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
            'duracao': filme [5],
            'link': filme[6]
        })

    cur.close()  # Fecha o cursor
    return jsonify({
        'mensagem': "Lista de filmes",  # Mensagem explicando que a resposta contém a lista de filmes
        'filmes': filmes_lista  # Retorna a lista de filmes na chave 'filmes'
    })

@app.route('/filme_imagem/<int:id>', methods=['PUT'])
def atualizar_filme(id):
    cur = con.cursor()
    cur.execute("SELECT id_filme, titulo, genero, classificacao, sinopse, duracao, link, situacao FROM filmes WHERE id_filme = ?", (id,))
    filme_data = cur.fetchone()

    if not filme_data:
        cur.close()
        return jsonify({"error": "Filme não foi encontrado"}), 404

    titulo_armazenado = filme_data[1]
    situacao_armazenada = filme_data[7]

    # Pega dados do formulário, se não vierem mantém os antigos
    titulo = normalizar_texto(request.form.get('titulo') or titulo_armazenado)
    classificacao = normalizar_texto(request.form.get('classificacao') or filme_data[3])
    genero = normalizar_texto(request.form.get('genero') or filme_data[2])
    sinopse = normalizar_texto(request.form.get('sinopse') or filme_data[4])
    duracao = normalizar_texto(request.form.get('duracao') or filme_data[5])
    link = normalizar_texto(request.form.get('link') or filme_data[6])
    situacao = normalizar_texto(request.form.get('situacao') or situacao_armazenada)

    imagem = request.files.get('imagem')

    # Verifica se o título foi alterado e se já existe outro filme com o mesmo título
    if titulo_armazenado != titulo:
        cur.execute("SELECT 1 FROM filmes WHERE titulo = ? AND id_filme != ?", (titulo, id))
        if cur.fetchone():
            cur.close()
            return jsonify({"message": "Este filme já foi cadastrado!"}), 400

    cur.execute(
        "UPDATE filmes SET titulo = ?, genero = ?, classificacao = ?, sinopse = ?, duracao = ?, link = ?, situacao = ? WHERE id_filme = ?",
        (titulo, genero, classificacao, sinopse, duracao, link, situacao, id)
    )
    con.commit()

    imagem_path = None
    if imagem:
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
            'duracao': duracao,
            'link': link,
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
        ORDER BY s.data_sessao ASC, s.horario ASC
    """, (id_filme,))

    sessoes = cur.fetchall()
    sessoes_dic = []

    for sessao in sessoes:
        horario = sessao[3]
        data_sessao = sessao[4]

        if isinstance(horario, str):
            horario = datetime.strptime(horario, "%H:%M:%S").time()
        if isinstance(data_sessao, str):
            data_sessao = datetime.strptime(data_sessao, "%Y-%m-%d").date()

        data_hora_sessao = datetime.combine(data_sessao, horario)
        if data_hora_sessao <= datetime.now():
            continue

        valor_unitario = float(sessao[7]) if sessao[7] is not None else 0.0
        valor_promocional = float(sessao[8]) if sessao[8] is not None else None
        duracao = int(sessao[9]) if sessao[9] is not None else 0

        sessao_dict = {
            'id_sessao': sessao[0],
            'id_sala': sessao[1],
            'descricao': sessao[2],
            'horario': horario.strftime("%H:%M:%S"),
            'data_sessao': data_sessao.strftime("%Y-%m-%d"),
            'id_filme': sessao[5],
            'titulo': sessao[6],
            'duracao': duracao
        }

        if valor_promocional:
            sessao_dict['valor_promocional'] = valor_promocional
        else:
            sessao_dict['valor_unitario'] = valor_unitario

        sessoes_dic.append(sessao_dict)

    cur.close()

    # Esse return tem que ficar FORA do for
    if not sessoes_dic:
        return jsonify({
            "mensagem": "Nenhuma sessão encontrada para este filme.",
            "sessoes": []
        })

    return jsonify({
        "mensagem": "Lista de sessões",
        "sessoes": sessoes_dic
    })


@app.route('/promocao', methods=['PUT'])
def adicionar_promocao():
    dados = request.get_json()

    id_sessao = dados.get('id_sessao')
    valor_promocional = dados.get('valor_promocional')

    if id_sessao is None or valor_promocional is None:
        return jsonify({'erro': 'Campos obrigatórios: id_sessao e valor_promocional'}), 400

    cur = con.cursor()

    # Verifica se a sessão existe
    cur.execute("SELECT ID_SESSAO FROM SESSOES WHERE ID_SESSAO = ?", (id_sessao,))
    if not cur.fetchone():
        cur.close()
        return jsonify({'erro': 'Sessão não encontrada'}), 404

    # Atualiza o valor promocional
    cur.execute("""
        UPDATE SESSOES
        SET VALOR_PROMOCIONAL = ?
        WHERE ID_SESSAO = ?
    """, (valor_promocional, id_sessao))

    con.commit()
    cur.close()

    return jsonify({
        'mensagem': 'Promoção atualizada com sucesso!',
        'id_sessao': id_sessao,
        'valor_promocional': valor_promocional
    }), 200

@app.route('/promocao/<int:id_sessao>', methods=['DELETE'])
def deletar_promocao(id_sessao):
    cur = con.cursor()

    # Verifica se a sessão existe
    cur.execute("SELECT ID_SESSAO FROM SESSOES WHERE ID_SESSAO = ?", (id_sessao,))
    if not cur.fetchone():
        cur.close()
        return jsonify({'erro': 'Sessão não encontrada'}), 404

    # Remove o valor promocional (define como NULL)
    cur.execute("""
        UPDATE SESSOES
        SET VALOR_PROMOCIONAL = NULL
        WHERE ID_SESSAO = ?
    """, (id_sessao,))

    con.commit()
    cur.close()

    return jsonify({
        'mensagem': 'Promoção removida com sucesso!',
        'id_sessao': id_sessao
    }), 200


@app.route('/promocao', methods=['GET'])
def listar_promocoes():
    cur = con.cursor()

    cur.execute("""
        SELECT s.ID_SESSAO,
               f.TITULO,
               s.DATA_SESSAO,
               s.HORARIO,
               COALESCE(s.VALOR_PROMOCIONAL, 0) AS VALOR_PROMOCIONAL
        FROM SESSOES s
        JOIN FILMES f ON s.ID_FILME = f.ID_FILME
        WHERE s.VALOR_PROMOCIONAL IS NOT NULL
          AND s.DATA_SESSAO >= CURRENT_DATE
    """)

    sessoes = cur.fetchall()
    cur.close()

    lista = [{
        'id_sessao': s[0],
        'filme': s[1],
        'data': str(s[2]),
        'horario': str(s[3]),
        'valor_promocional': s[4]
    } for s in sessoes]

    return jsonify({
        'mensagem': 'Sessões com promoção',
        'sessoes_promocionais': lista
    })


@app.route('/sessoes/<int:id>', methods=['DELETE'])
def deletar_sessao(id):
    cur = con.cursor()

    # Verifica se a sessão existe
    cur.execute("SELECT 1 FROM sessoes WHERE id_sessao = ?", (id,))
    if not cur.fetchone():
        cur.close()
        return jsonify({"error": "Sessão não encontrada"}), 404

    # Verifica se existem reservas associadas
    cur.execute("SELECT 1 FROM reserva WHERE id_sessao = ?", (id,))
    if cur.fetchone():
        cur.close()
        return jsonify({"error": "Não é possível excluir esta sessão pois existem reservas associadas."}), 400

    # Se não tiver reservas, pode deletar
    cur.execute("DELETE FROM sessoes WHERE id_sessao = ?", (id,))
    con.commit()
    cur.close()

    return jsonify({
        'message': "Sessão excluída com sucesso!",
        'id_sessao': id
    }), 200


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

    # Cria a reserva principal COM A DATA DA RESERVA
    cur.execute("""
        INSERT INTO RESERVA (ID_SESSAO, ID_CADASTRO, STATUS, DATA_RESERVA)
        VALUES (?, ?, ?, ?)
        RETURNING ID_RESERVA
    """, (id_sessao, id_cadastro, 'Confirmada', date.today()))
    id_reserva = cur.fetchone()[0]

    # Relaciona os assentos com a reserva
    for assento in id_assentos:
        cur.execute("""
            INSERT INTO ASSENTOS_RESERVADOS (ID_RESERVA, ID_ASSENTO)
            VALUES (?, ?)
        """, (id_reserva, assento))

    con.commit()

    # 1. Buscar o valor unitário da sessão
    cur.execute("""
        SELECT 
            CASE 
                WHEN valor_promocional IS NOT NULL AND valor_promocional > 0 
                THEN valor_promocional 
                ELSE valor_unitario 
            END 
        FROM sessoes 
        WHERE id_sessao = ?
    """, (id_sessao,))
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
    caminho_qr = os.path.join(os.getcwd(), "static", "upload", "qrcodes")
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
        SELECT f.titulo, sa.descricao, s.data_sessao, s.horario FROM sessoes s JOIN filmes f ON f.id_filme = s.ID_FILME JOIN salas sa ON sa.ID_SALAS = s.ID_SALA
        WHERE s.ID_SESSAO = ?""", (id_sessao,))
    titulo_filme, sala, data_sessao, horario = cursor.fetchone()
    cursor.close()

    data_formatada = data_sessao.strftime('%d-%m-%Y')


    # Monta e envia o e-mail
    texto = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px; color: #333;">
        <div style="max-width: 600px; margin: auto; background-color: #fff; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.05); padding: 20px;">
          <h2 style="color: #cc0000;">Olá, {nome_usuario}!</h2>
          <p>Sua reserva foi realizada com sucesso. Aqui estão os detalhes da sua sessão:</p>

          <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
            <tr style="background-color: #eee;">
              <th align="left" style="padding: 8px;">🎬 Filme:</th>
              <td style="padding: 8px;">{titulo_filme}</td>
            </tr>
            <tr>
              <th align="left" style="padding: 8px;">🎟 Sala:</th>
              <td style="padding: 8px;">{sala}</td>
            </tr>
            <tr style="background-color: #eee;">
              <th align="left" style="padding: 8px;">📅 Data:</th>
              <td style="padding: 8px;">{data_formatada}</td>
            </tr>
            <tr>
              <th align="left" style="padding: 8px;">⏰ Horário:</th>
              <td style="padding: 8px;">{horario}</td>
            </tr>
            <tr style="background-color: #eee;">
              <th align="left" style="padding: 8px;">💺 Assentos:</th>
              <td style="padding: 8px;">{', '.join(map(str, id_assentos))}</td>
            </tr>
            <tr>
              <th align="left" style="padding: 8px;">💰 Valor total:</th>
              <td style="padding: 8px;">R$ {valor_total:.2f}</td>
            </tr>
          </table>

          <div style="margin-top: 30px;">
            <h3>🔢 Código PIX:</h3>
            <p style="word-wrap: break-word; background-color: #f2f2f2; padding: 10px; border-left: 5px solid #cc0000;">
              {codigo_pix}
            </p>
          <p style="margin-top: 30px;">Estamos ansiosos para te receber na sessão! Prepare a pipoca! 🍿✨</p>

          <p style="color: #888; font-size: 12px;">Atenciosamente,<br>Equipe <strong>PrimeCine</strong></p>
        </div>
      </body>
    </html>
    """

    mensagem = "Reserva realizada com sucesso!"
    erro_email = None
    try:
        enviar_email_para(email, texto, mensagem, caminho_qr_completo)
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

    # Obter todas as reservas, juntando as tabelas RESERVA, SESSOES, FILMES e SALAS, incluindo valor_total
    cur.execute("""
        SELECT r.ID_RESERVA, f.TITULO, s.DATA_SESSAO, s.HORARIO, sa.DESCRICAO, r.STATUS, r.VALOR_TOTAL
        FROM RESERVA r
        JOIN SESSOES s ON r.ID_SESSAO = s.ID_SESSAO
        JOIN FILMES f ON s.ID_FILME = f.ID_FILME
        JOIN SALAS sa ON s.ID_SALA = sa.ID_SALAS
        WHERE r.id_cadastro = ?
    """, (id_cadastro, ))

    reservas = cur.fetchall()

    reservas_formatadas = []

    for reserva in reservas:
        id_reserva, titulo_filme, data_sessao, horario, sala, status, valor_total = reserva

        # Buscar os assentos dessa reserva
        cur.execute("SELECT ID_ASSENTO FROM ASSENTOS_RESERVADOS WHERE ID_RESERVA = ?", (id_reserva,))
        assentos_raw = cur.fetchall()
        assentos = [row[0] for row in assentos_raw]

        # Converter horário para string, se necessário
        if isinstance(horario, time):
            horario = horario.strftime('%H:%M:%S')

        reservas_formatadas.append({
            "id_reserva": id_reserva,
            "titulo_filme": titulo_filme,
            "data_sessao": data_sessao,
            "horario": horario,
            "sala": sala,
            "status": status,
            "assentos": assentos,
            "valor_total": float(valor_total)
        })

    cur.close()

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

@app.route('/buscar-filmes', methods=['GET'])
def buscar_filmes():
    termo = request.args.get('termo', '')

    try:
        cur = con.cursor()
        # Busca case-insensitive usando LOWER
        cur.execute("""
            SELECT id_filme, titulo, sinopse, classificacao
            FROM filmes 
            WHERE LOWER(titulo) LIKE LOWER(?)
        """, ('%' + termo + '%',))
        resultados = cur.fetchall()
        cur.close()

        # Montar resposta em JSON incluindo sinopse e classificacao
        filmes = [
            {
                'id': row[0],
                'titulo': row[1],
                'sinopse': row[2],
                'classificacao': row[3]
            } for row in resultados
        ]
        return jsonify(filmes), 200

    except Exception as e:
        return jsonify({'erro': f'Erro na busca: {str(e)}'}), 500


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
        pasta_qrcodes = os.path.join(os.getcwd(), "static", "upload", "qrcodes")
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

@app.route('/pix_qrcode/<int:id_reserva>', methods=['GET'])
def gerar_pix_por_reserva(id_reserva):
    try:
        # 1. Buscar valor total da reserva
        cursor = con.cursor()
        cursor.execute("SELECT VALOR_TOTAL FROM RESERVA WHERE ID_RESERVA = ?", (id_reserva,))
        resultado_reserva = cursor.fetchone()
        cursor.close()

        if not resultado_reserva:
            return jsonify({"erro": "Reserva não encontrada"}), 404

        valor = f"{float(resultado_reserva[0]):.2f}"

        # 2. Buscar dados do cinema (configuração PIX)
        cursor = con.cursor()
        cursor.execute("SELECT RAZAO_SOCIAL, CHAVE_PIX, CIDADE FROM CONFIG_CINE")
        resultado = cursor.fetchone()
        cursor.close()

        if not resultado:
            return jsonify({"erro": "Dados de PIX não configurados"}), 500

        nome, chave_pix, cidade = resultado
        nome = nome[:25] if nome else "Recebedor PIX"
        cidade = cidade[:15] if cidade else "Cidade"

        # 3. Montar o payload do QR Code
        merchant_account_info = (
            format_tlv("00", "br.gov.bcb.pix") +
            format_tlv("01", chave_pix)
        )
        campo_26 = format_tlv("26", merchant_account_info)

        payload_sem_crc = (
            "000201" +
            "010212" +
            campo_26 +
            "52040000" +
            "5303986" +
            format_tlv("54", valor) +
            "5802BR" +
            format_tlv("59", nome) +
            format_tlv("60", cidade) +
            format_tlv("62", format_tlv("05", f"RES{id_reserva}")) +
            "6304"
        )

        crc = calcula_crc16(payload_sem_crc)
        payload_completo = payload_sem_crc + crc

        # 4. Gerar imagem do QR Code
        qr_obj = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_H,
            box_size=10,
            border=4
        )
        qr_obj.add_data(payload_completo)
        qr_obj.make(fit=True)
        qr = qr_obj.make_image(fill_color="black", back_color="white")

        pasta_qrcodes = os.path.join(os.getcwd(), "static", "upload", "qrcodes")
        os.makedirs(pasta_qrcodes, exist_ok=True)

        nome_arquivo = f"pix_reserva_{id_reserva}.png"
        caminho_arquivo = os.path.join(pasta_qrcodes, nome_arquivo)
        qr.save(caminho_arquivo)

        return send_file(caminho_arquivo, mimetype='image/png', as_attachment=True, download_name=nome_arquivo)

    except Exception as e:
        return jsonify({"erro": f"Erro ao gerar QR Code PIX: {str(e)}"}), 500

def administrador_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        if not is_admin():
            return jsonify({'erro': 'Acesso restrito a administradores'}), 403
        return f(*args, **kwargs)
    return decorator

def is_admin():
    return True

@app.route('/configurar-pix', methods=['GET', 'POST'])
@administrador_required
def configurar_pix():
    if request.method == 'GET':
        try:
            cur = con.cursor()
            cur.execute("SELECT RAZAO_SOCIAL, NOME_FANTASIA, CHAVE_PIX, CIDADE FROM CONFIG_CINE WHERE id_config = 1")
            row = cur.fetchone()
            cur.close()

            return jsonify({
                "usuarios": {
                    "razao_social": row[0],
                    "nome_fantasia": row[1],
                    "chave_pix": row[2],
                    "cidade": row[3]
                }
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    if request.method == 'POST':
        try:
            dados = request.get_json()
            print("DEBUG - JSON recebido:", dados)

            if not dados:
                return jsonify({'erro': 'JSON inválido ou ausente'}), 400

            razao_social = dados.get('razao_social')
            nome_fantasia = dados.get('nome_fantasia')
            chave_pix = dados.get('chave_pix')
            cidade = dados.get('cidade')

            if any(x is None for x in [razao_social, nome_fantasia, chave_pix, cidade]):
                return jsonify({'erro': 'Todos os campos são obrigatórios'}), 400

            cur = con.cursor()
            cur.execute("""
                UPDATE CONFIG_CINE
                SET RAZAO_SOCIAL = ?, NOME_FANTASIA = ?, CHAVE_PIX = ?, CIDADE = ?
                WHERE id_config = 1
            """, (razao_social, nome_fantasia, chave_pix, cidade))
            con.commit()
            cur.close()

            return jsonify({
                'mensagem': 'Dados de PIX atualizados com sucesso!',
                'razao_social': razao_social,
                'nome_fantasia': nome_fantasia,
                'chave_pix': chave_pix,
                'cidade': cidade
            }), 200

        except Exception as e:
            print("ERRO INTERNO:", str(e))
            return jsonify({'erro': f'Erro ao atualizar os dados: {str(e)}'}), 500


def conectar():
    try:
        con = fdb.connect(
            host='localhost',  # ou o IP do seu servidor Firebird
            database=r'D:\API-gestaocinema\Banco\BANCO.FDB',  # caminho do seu banco de dados
            user='sysdba',
            password='sysdba',
            port=3050  # ou a porta que você estiver utilizando
        )
        print("Conexão estabelecida com sucesso!")
        return con
    except Exception as e:
        print(f"Erro ao conectar ao banco: {e}")
        return None


@app.route('/avaliar', methods=['POST'])
def avaliar_filme():
    dados = request.get_json()

    id_cadastro = dados.get('id_cadastro')
    id_filme = dados.get('id_filme')
    nota = dados.get('nota')

    if id_cadastro is None or id_filme is None or nota is None:
        return jsonify({"erro": "Faltam dados"}), 400

    try:
        cur = con.cursor()

        # Inserir a nova avaliação
        sql_insert = """
            INSERT INTO avaliacoes (id_cadastro, id_filme, nota, data_avaliacao)
            VALUES (?, ?, ?, ?)
        """
        cur.execute(sql_insert, (id_cadastro, id_filme, nota, date.today()))
        con.commit()

        # Calcular nova média
        sql_media = """
            SELECT AVG(CAST(nota AS FLOAT)) FROM avaliacoes WHERE id_filme = ?
        """
        cur.execute(sql_media, (id_filme,))
        media = cur.fetchone()[0]

        # Atualizar o campo media_avaliacao na tabela filmes
        sql_update = """
            UPDATE filmes SET media_avaliacoes = ? WHERE id_filme = ?
        """
        cur.execute(sql_update, (media, id_filme))
        con.commit()

        return jsonify({
            "mensagem": "Avaliação salva com sucesso",
            "id_cadastro": id_cadastro,
            "id_filme": id_filme,
            "nota": nota,
            "media_atualizada": round(float(media), 2)
        }), 201

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    finally:
        if cur:
            cur.close()
@app.route('/avaliacoes', methods=['GET'])
def verificar_se_usuario_votou():
    id_cadastro = request.args.get('id_cadastro')  # corrigido aqui
    id_filme = request.args.get('id_filme')

    if not id_cadastro or not id_filme:
        return jsonify({"erro": "Parâmetros faltando"}), 400

    try:
        cur = con.cursor()
        sql = """
        SELECT nota FROM avaliacoes
        WHERE id_cadastro = ? AND id_filme = ?
        """
        cur.execute(sql, (id_cadastro, id_filme))
        resultado = cur.fetchone()

        if resultado:
            return jsonify({"voto": resultado[0]}), 200
        else:
            return jsonify({"mensagem": "Usuário ainda não votou"}), 404

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    finally:
        if cur:
            cur.close()


@app.route('/avaliacoes/media', methods=['GET'])
def media_avaliacoes():
    try:
        cur = con.cursor()

        sql = """
            SELECT f.ID_FILME, f.TITULO, AVG(CAST(a.nota AS FLOAT)) AS media_avaliacoes
            FROM avaliacoes a
            JOIN filmes f ON a.id_filme = f.id_filme
            GROUP BY f.id_filme, f.titulo
        """
        cur.execute(sql)
        resultados = cur.fetchall()

        if not resultados:
            return jsonify({"mensagem": "Nenhuma avaliação encontrada."}), 404

        filmes_avaliados = []
        for linha in resultados:
            filmes_avaliados.append({
                "id_filme": linha[0],
                "titulo": linha[1],
                "media_avaliacoes": round(float(linha[2]), 2)
            })

        return jsonify(filmes_avaliados)

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

    finally:
        if cur:
            cur.close()


@app.route('/painel-admin', methods=['POST'])
def painel_admin():
    dados = request.get_json(silent=True) or {}

    data_inicial = dados.get('data_inicial')
    data_final = dados.get('data_final')

    if not data_inicial or not data_final:
        hoje = date.today().isoformat()
        data_inicial = hoje
        data_final = hoje

    cur = con.cursor()

    # Total arrecadado com base na data_reserva
    cur.execute("""
        SELECT r.VALOR_TOTAL
        FROM SESSOES s
        LEFT JOIN RESERVA r ON r.ID_SESSAO = s.ID_SESSAO
        WHERE r.DATA_RESERVA BETWEEN ? AND ?
    """, (data_inicial, data_final))

    total_arrecadado = sum(float(row[0]) for row in cur.fetchall() if row[0] is not None)

    # Vendas por sessão
    cur.execute("""
        SELECT f.TITULO, s.DATA_SESSAO, s.HORARIO, COUNT(ar.ID_RESERVA) AS ingressos
        FROM SESSOES s
        LEFT JOIN FILMES f ON s.ID_FILME = f.ID_FILME
        LEFT JOIN RESERVA r ON r.ID_SESSAO = s.ID_SESSAO
        LEFT JOIN ASSENTOS_RESERVADOS ar ON ar.ID_RESERVA = r.ID_RESERVA
        WHERE r.DATA_RESERVA BETWEEN ? AND ?
        GROUP BY f.TITULO, s.DATA_SESSAO, s.HORARIO
        HAVING COUNT(ar.ID_RESERVA) > 0
        ORDER BY ingressos DESC
    """, (data_inicial, data_final))

    sessoes = cur.fetchall()
    vendas_lista = [{
        'nome': s[0],
        'data': str(s[1]),
        'horario': str(s[2]),
        'ingressos': s[3]
    } for s in sessoes]

    # Filmes com maior bilheteira
    cur.execute("""
        SELECT f.TITULO, r.VALOR_TOTAL
        FROM RESERVA r
        JOIN SESSOES s ON r.ID_SESSAO = s.ID_SESSAO
        JOIN FILMES f ON s.ID_FILME = f.ID_FILME
        WHERE r.DATA_RESERVA BETWEEN ? AND ?
    """, (data_inicial, data_final))

    bilheteira_por_filme = {}
    for titulo, valor in cur.fetchall():
        if valor is not None:
            bilheteira_por_filme[titulo] = bilheteira_por_filme.get(titulo, 0) + float(valor)

    filmes_lista = [
        {'titulo': titulo, 'bilheteira_total': total}
        for titulo, total in sorted(bilheteira_por_filme.items(), key=lambda x: x[1], reverse=True)[:3]
    ]

    # Ingressos vendidos
    cur.execute("""
        SELECT COUNT(ar.ID_ASSENTO)
        FROM SESSOES s
        LEFT JOIN RESERVA r ON r.ID_SESSAO = s.ID_SESSAO
        LEFT JOIN ASSENTOS_RESERVADOS ar ON ar.ID_RESERVA = r.ID_RESERVA
        WHERE r.DATA_RESERVA BETWEEN ? AND ?
    """, (data_inicial, data_final))

    ingressos_vendidos = cur.fetchone()[0] or 0

    return jsonify({
        'mensagem': "Painel Administrativo",
        'total_arrecadado': total_arrecadado,
        'ingressos_vendidos': ingressos_vendidos,
        'vendas_por_sessao': vendas_lista,
        'filmes_mais_bilheteira': filmes_lista
    })

@app.route('/gerar_pdf_painel', methods=['GET'])
def gerar_pdf_painel():
    cursor = con.cursor()
    cursor.execute("""
        SELECT f.titulo, s.DATA_SESSAO, s.horario, COUNT(ar.id_reserva) AS ingressos
          FROM sessoes s
          LEFT JOIN filmes f ON s.id_filme = f.id_filme
          LEFT JOIN RESERVA r ON r.ID_SESSAO = s.ID_SESSAO
          LEFT JOIN assentos_reservados ar ON ar.ID_RESERVA = r.ID_RESERVA
         GROUP BY f.titulo, s.DATA_SESSAO, s.horario
        HAVING COUNT(ar.id_reserva) > 0
         ORDER BY ingressos DESC
    """)
    sessoes = cursor.fetchall()
    cursor.close()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Título
    pdf.set_font("Arial", style='B', size=16)
    pdf.cell(200, 10, "Relatório de Venda Por Sessão", ln=True, align='C')

    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)

    # Cabeçalho da tabela
    pdf.set_font("Arial", style='B', size=12)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(90, 10, "Título", border=1, align='C', fill=True)
    pdf.cell(35, 10, "Data", border=1, align='C', fill=True)
    pdf.cell(30, 10, "Horário", border=1, align='C', fill=True)
    pdf.cell(35, 10, "Ingressos", border=1, align='C', fill=True)
    pdf.ln()

    # Linhas da tabela
    pdf.set_font("Arial", size=12)
    for sessao in sessoes:
        titulo = str(sessao[0])
        data = sessao[1].strftime("%d/%m/%Y") if hasattr(sessao[1], 'strftime') else str(sessao[1])
        horario = str(sessao[2])
        ingressos = str(sessao[3])

        pdf.cell(90, 10, titulo, border=1)
        pdf.cell(35, 10, data, border=1, align='C')
        pdf.cell(30, 10, horario, border=1, align='C')
        pdf.cell(35, 10, ingressos, border=1, align='C')
        pdf.ln()

    # Total de sessões
    pdf.ln(10)
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(200, 10, f"Total de sessões com ingressos vendidos: {len(sessoes)}", ln=True, align='C')

    # Salva PDF
    pdf_path = "relatorio_venda_sessoes.pdf"
    pdf.output(pdf_path)

    cursor.execute("""
        SELECT f.titulo, s.DATA_SESSAO, s.horario, COUNT(ar.id_reserva) AS ingressos
          FROM sessoes s
          LEFT JOIN filmes f ON s.id_filme = f.id_filme
          LEFT JOIN RESERVA r ON r.ID_SESSAO = s.ID_SESSAO
          LEFT JOIN assentos_reservados ar ON ar.ID_RESERVA = r.ID_RESERVA
         GROUP BY f.titulo, s.DATA_SESSAO, s.horario
        HAVING COUNT(ar.id_reserva) > 0
         ORDER BY 4 DESC
    """)

    return send_file(pdf_path, as_attachment=True, mimetype='application/pdf')

    livros = cursor.fetchall()
    cursor.close()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", style='B', size=16)
    pdf.cell(200, 10, "Relatorio de Livros", ln=True, align='C')

    pdf.ln(5)  # Espaço entre o título e a linha
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())  # Linha abaixo do título
    pdf.ln(5)  # Espaço após a linha
    pdf.set_font("Arial", size=12)

    for livro in livros:
        pdf.cell(200, 10, f"Título: {livro[0]}  Data da Sessão: {livro[1]}  Horário: {livro[2]}  Quantidade de Ingressos: {livro[3]}", ln=True)

    contador_livros = len(livros)
    pdf.ln(10)  # Espaço antes do contador
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(200, 10, f"Total de livros cadastrados: {contador_livros}", ln=True, align='C')
    pdf_path = "relatorio_livros.pdf"
    pdf.output(pdf_path)

    return send_file(pdf_path, as_attachment=True, mimetype='application/pdf')


if __name__ == '__main__':
    app.run(debug=True)