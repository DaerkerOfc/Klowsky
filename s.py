from flask import Flask, request, jsonify
import sqlite3
import random
import string

app = Flask(__name__)

# Função para gerar uma chave no formato XXX-XXX
def gerar_chave():
    return f"{''.join(random.choices(string.ascii_uppercase + string.digits, k=3))}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=3))}"

# Função para gerar um UID aleatório de 19 caracteres
def gerar_uid():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=19))

# Função para inicializar o banco de dados SQLite
def init_db():
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    chave TEXT NOT NULL,
                    uid TEXT NOT NULL,
                    coin REAL DEFAULT 0.00)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transferencias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chave_origem TEXT,
                    chave_destino TEXT,
                    valor REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

# Rota para criar uma conta
@app.route('/api/create', methods=['POST'])
def create_account():
    data = request.get_json()
    nome = data.get('nome')

    if not nome:
        return jsonify({"status": 400, "error": "Nome é obrigatório"}), 400

    chave = gerar_chave()
    uid = gerar_uid()
    coin = 0.00

    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute("INSERT INTO usuarios (nome, chave, uid, coin) VALUES (?, ?, ?, ?)", (nome, chave, uid, coin))
    conn.commit()
    conn.close()

    return jsonify({"status": 200, "nome": nome, "chave": chave, "uid": uid, "coin": coin}), 200

# Rota para buscar uma conta pelo chave
@app.route('/api/search/<chave>', methods=['GET'])
def search_account(chave):
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute("SELECT nome, chave FROM usuarios WHERE chave = ?", (chave,))
    result = c.fetchone()
    conn.close()

    if result:
        return jsonify({"nome": result[0], "chave": result[1]}), 200
    else:
        return jsonify({"error": "Chave não encontrada"}), 404

# Rota para transferir valores entre contas
@app.route('/api/transferir', methods=['POST'])
def transferir():
    data = request.get_json()
    valor_str = data.get('valor')
    chave_destino = data.get('chave')
    chave_origem = data.get('chave_enviar')

    if not valor_str or not chave_destino or not chave_origem:
        return jsonify({"error": "Dados incompletos"}), 400

    # Converter o valor de "1.000,00" para "1000.00"
    try:
        valor = float(valor_str.replace('.', '').replace(',', '.'))
    except ValueError:
        return jsonify({"error": "Formato de valor inválido"}), 400

    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()

    # Verificar a conta de origem
    c.execute("SELECT coin FROM usuarios WHERE chave = ?", (chave_origem,))
    origem = c.fetchone()

    if not origem:
        conn.close()
        return jsonify({"error": "Chave de origem não encontrada"}), 404

    if origem[0] < valor:
        conn.close()
        return jsonify({"error": "Saldo insuficiente"}), 400

    # Verificar a conta de destino
    c.execute("SELECT coin FROM usuarios WHERE chave = ?", (chave_destino,))
    destino = c.fetchone()

    if not destino:
        conn.close()
        return jsonify({"error": "Chave de destino não encontrada"}), 404

    # Realizar a transferência
    c.execute("UPDATE usuarios SET coin = coin - ? WHERE chave = ?", (valor, chave_origem))
    c.execute("UPDATE usuarios SET coin = coin + ? WHERE chave = ?", (valor, chave_destino))
    
    # Registrar a transferência
    c.execute("INSERT INTO transferencias (chave_origem, chave_destino, valor) VALUES (?, ?, ?)",
              (chave_origem, chave_destino, valor))
    
    conn.commit()
    conn.close()

    return jsonify({"message": "Transferência realizada com sucesso!"}), 200

# Rota para verificar o saldo de um usuário
@app.route('/api/saldo/<chave>', methods=['GET'])
def get_saldo(chave):
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute("SELECT coin FROM usuarios WHERE chave = ?", (chave,))
    result = c.fetchone()
    conn.close()

    if result:
        return jsonify({"saldo": "{:.2f}".format(result[0])}), 200
    else:
        return jsonify({"error": "Chave não encontrada"}), 404

# Rota para admin enviar valor para um usuário
@app.route('/send', methods=['GET'])
def send_coin():
    valor_str = request.args.get('coin')
    chave = request.args.get('chave')

    if not valor_str or not chave:
        return jsonify({"error": "Parâmetros 'coin' e 'chave' são obrigatórios"}), 400

    # Converter o valor de "1.000,00" para "1000.00"
    try:
        valor = float(valor_str.replace('.', '').replace(',', '.'))
    except ValueError:
        return jsonify({"error": "Formato de valor inválido"}), 400

    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()

    # Verificar se a chave existe
    c.execute("SELECT coin FROM usuarios WHERE chave = ?", (chave,))
    result = c.fetchone()

    if not result:
        conn.close()
        return jsonify({"error": "Chave não encontrada"}), 404

    # Atualizar o saldo do usuário
    c.execute("UPDATE usuarios SET coin = coin + ? WHERE chave = ?", (valor, chave))
    conn.commit()
    conn.close()

    return jsonify({"message": "Valor enviado com sucesso"}), 200

# Rota para verificar a última transferência recebida
@app.route('/api/checkNew/<chave>', methods=['GET'])
def check_new_transfer(chave):
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()

    # Buscar a última transferência recebida pela chave
    c.execute('''
    SELECT chave_origem, valor, timestamp
    FROM transferencias
    WHERE chave_destino = ?
    ORDER BY timestamp DESC
    LIMIT 1
    ''', (chave,))
    result = c.fetchone()
    conn.close()

    if result:
        response = {
            "de": result[0],
            "valor": "{:.2f}".format(result[1]),
            "timestamp": result[2]
        }
        return jsonify(response), 200
    else:
        return jsonify({"message": "Nenhuma transferência encontrada"}), 404

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
