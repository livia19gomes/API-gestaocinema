from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from main import app, con
import re
import jwt
from fpdf import FPDF
import os
from flask_bcrypt import generate_password_hash, check_password_hash

app = Flask(__name__)

CORS(app, origins=["*"])

app.config.from_pyfile('config.py')
senha_secreta = app.config['SECRET_KEY']

if not os.path.exists(app.config['UPLOAD_FILMES']):
    os.makedirs(app.config['UPLOAD_FILMES'])


def remover_bearer(token):  # Remove o bearer
    if token.startswith('Bearer '):
        return token[len('Bearer '):]
    else:
        return token

def generate_token(user_id):  # Gera um token para o usuario
    payload = {'id_usuario': user_id}
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
    cursor.execute("SELECT ID_FILME, TITULO , GENERO , CLASSIFICACAO FROM filme")
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

    ativo = usuario[3]

    if ativo != False:
        senha_armazenada = usuario[0]
        tipo = usuario[1]
        id_cadastro = usuario[2]

        if check_password_hash(senha_armazenada, senha):
            token = generate_token(id_cadastro)

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
def filme_imagem():
    token = request.headers.get('Authorization')  # Verifica token
    print(token)  # Exibe o token
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

    cursor = con.cursor()
    # Verifica se o filme já existe
    cursor.execute("SELECT 1 FROM filmes WHERE TITULO = ?", (titulo,))
    if cursor.fetchone():
        cursor.close()
        return jsonify({"error": "Filme já cadastrado"}), 400

    # Insere o novo filme e retorna o ID gerado
    cursor.execute(
        "INSERT INTO filmes (TITULO, CLASSIFICACAO, GENERO, SINOPSE) VALUES (?, ?, ?, ?) RETURNING ID_filme",
        (titulo, classificacao, genero, sinopse)
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
            'imagem_path': imagem_path
        }
    }), 201

@app.route('/filmes', methods=['GET'])
def listar_filmes():
    cur = con.cursor()
    cur.execute("SELECT id_filme, titulo, classificacao, genero, sinopse FROM filmes")
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
    cur.execute("SELECT id_filme, titulo, genero, classificacao, sinopse FROM FILMES WHERE id_filme =?", (id,))
    filme_data = cur.fetchone()

    titulo_armazenado = filme_data[1]  # Armazena o título do filme

    if not filme_data:  # Se não existir, vai retornar um erro
        cur.close()
        return jsonify({"error": "Filme não foi encontrado"}), 404

    titulo = request.form.get('titulo')
    classificacao = request.form.get('classificacao')
    genero = request.form.get('genero')
    sinopse = request.form.get('sinopse')
    imagem = request.files.get('imagem')  # Arquivo enviado

    if titulo_armazenado != titulo:  # Se o título não for modificado
        cur.execute("SELECT 1 FROM filmes WHERE titulo = ?", (titulo,))

        if cur.fetchone():  # Retorna com o erro
            return jsonify({"message": "Este filme já foi cadastrado!"}), 400

    cur.execute("update filmes set titulo = ?, genero = ?, classificacao = ?, sinopse = ? where id_filme = ?",
                (titulo, genero, classificacao, sinopse, id))  # Atualiza as informações trocadas

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
            'titulo': titulo,
            'genero': genero,
            'classificacao': classificacao,
            'sinopse': sinopse,
            'imagem_path': imagem_path
        }
    })


@app.route('/filme_imagem/<int:id>', methods=['DELETE'])
def deletar_filme(id):
    cur = con.cursor()

    cur.execute("SELECT 1 FROM FILMES WHERE ID_FILME = ?", (id,))
    if not cur.fetchone():
        cur.close()
        return jsonify({"error": "Filme não encontrado"}), 404

    cur.execute("DELETE FROM filmes WHERE ID_filme = ?", (id,))
    con.commit()
    cur.close()

    return jsonify({
        'message': "Filme excluído com sucesso!",
        'id_filme': id
    })

