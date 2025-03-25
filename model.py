import fdb

class Filme:
    def __init__(self, id_filme, titulo, genero, classificacao):
        self.id_filme = id_filme
        self.titulo = titulo
        self.genero = genero
        self.classificacao = classificacao

class Cadastros:
    def __init__(self, id_cadastro, nome, telefone, email, senha, tipo, ativo):
        self.id_cadastro = id_cadastro
        self.nome = nome
        self.telefone = telefone
        self.email = email
        self.senha = senha
        self.tipo = tipo
        self.ativo = ativo

class Promocoes:
    def __init__(self, id_promocoes, id_filme, valor):
        self.id_filme = id_filme
        self.valor = valor
        self.qtd_ingresso = valor

class Sessao:
    def __init__(self, id_sessao, id_sala, horario, data_sessao):
        self.id_sessao = id_sessao
        self.id_sala = id_sala
        self.horario = horario
        self.data_sessao = data_sessao

class Salas:
    def __init__(self, id_salas, capacidade):
        self.id_salas = id_salas
        self.capacidade = capacidade

class Reserva:
    def __init__(self, id_reserva, id_cadastro, id_sessao):
        self.id_reserva = id_reserva
        self.id_cadastro = id_cadastro
        self.id_sessao = id_sessao






