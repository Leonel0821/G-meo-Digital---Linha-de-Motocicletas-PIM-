import sqlite3
import json
import paho.mqtt.client as mqtt
import pandas as pd
from datetime import datetime

DB_NAME = "gmeo_digital_grupo8.db"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "fabrica/pim/estacao/#"

def inicializar_banco():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS series_temporais_producao (
            id INTEGER PRIMARY KEY AUTOINCREMENT, horario_registro TEXT,
            moto_id INTEGER, modelo TEXT, estacao TEXT,
            tempo_espera REAL, tempo_processo REAL, status_andon TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("🗄️ [Camada 3] Banco configurado com segurança para o Grupo 8.")

def on_connect(client, userdata, flags, rc):
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO series_temporais_producao 
            (horario_registro, moto_id, modelo, estacao, tempo_espera, tempo_processo, status_andon)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), payload.get("moto_id"), payload.get("modelo"), payload.get("estacao"), payload.get("tempo_espera", 0.0), payload.get("tempo_processo"), payload.get("status_andon", "OK")))
        conn.commit()
        conn.close()
    except:
        pass

def analisar_dados_com_pandas():
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM series_temporais_producao", conn)
        conn.close()
        
        if df.empty:
            print("\n⚠ Banco vazio. Gerando dados simulados automaticamente para o Pandas...")
            gerar_dados_teste()
            return
            
        print("\n" + "="*60)
        print("📈 COMPUTAÇÃO ESTATÍSTICA DA PRODUÇÃO (ANÁLISE VIA PANDAS)")
        print("="*60)
        balanco_linha = df.groupby('estacao').agg({'tempo_processo': 'mean', 'tempo_espera': 'mean', 'moto_id': 'count'}).rename(columns={'moto_id': 'motos_processadas'})
        print(balanco_linha)
        print("="*60 + "\n")
    except Exception as e:
        print(f"❌ Erro: {e}")

def gerar_dados_teste():
    import random
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    for m_id in range(1, 321):
        for i in range(1, 19):
            t_proc = random.normalvariate(85, 5) if i != 11 else random.normalvariate(110, 15)
            status = "Defeito" if i == 11 and random.random() < 0.035 else "OK"
            cursor.execute('INSERT INTO series_temporais_producao (horario_registro, moto_id, modelo, estacao, tempo_espera, tempo_processo, status_andon) VALUES (?,?,?,?,?,?,?)', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), m_id, "XTZ 150", f"E{i:02d}", random.uniform(0, 5), t_proc, status))
    conn.commit()
    conn.close()
    analisar_dados_com_pandas()

if __name__ == "__main__":
    inicializar_banco()
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        analisar_dados_com_pandas()