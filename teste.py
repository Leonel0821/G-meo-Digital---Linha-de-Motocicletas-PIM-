import json
import paho.mqtt.client as mqtt
import simpy
import random
import pandas as pd
from datetime import datetime
import streamlit as st
import time

# ==========================================
# CONFIGURAÇÃO DA BARRA LATERAL (STREAMLIT)
# ==========================================
st.sidebar.header("⚙️ Configurações do Gêmeo Digital")

# Inputs interativos que substituem as constantes fixas
TEMPO_SIMULACAO = st.sidebar.number_input("Tempo de Simulação (segundos)", value=28800)
TAKT_TIME_META = st.sidebar.number_input("Meta Takt Time (segundos)", value=90)
PPM_DEFEITO = st.sidebar.number_input("PPM de Defeito (Estação 11)", value=35000)
TEMPO_SETUP_MODELO = st.sidebar.number_input("Tempo de Setup (segundos)", value=180)

# Botão para disparar a simulação e atualizar o Dashboard
if st.sidebar.button("🚀 Rodar Simulação e Enviar Dados"):
    
    # Tempos médios de processamento das 18 estações
    TEMPOS_ESTACOES = {
        "E01": 75, "E02": 85, "E03": 80, "E04": 85, "E05": 70, "E06": 90,
        "E07": 85, "E08": 80, "E09": 85, "E10": 80, 
        "E11_Painel": 85,  
        "E12": 80, "E13": 85, "E14": 75, "E15": 80, "E16": 85, "E17": 85, "E18": 80
    }

    historico_producao = []

    def linha_montagem(env, nome_moto, modelo, estacoes_recursos):
        for estacao, tempo_base in TEMPOS_ESTACOES.items():
            with estacoes_recursos[estacao].request() as req:
                yield req
                tempo_processo = max(10, random.normalvariate(tempo_base, 3))
                status_qualidade = "Aprovado"
                tempo_ocioso_setup = 0
                
                if estacao == "E11_Painel":
                    if random.random() < 0.20:  
                        tempo_ocioso_setup = max(10, random.normalvariate(TEMPO_SETUP_MODELO, 10))
                        yield env.timeout(tempo_ocioso_setup)
                    if random.random() < (PPM_DEFEITO / 1000000):
                        status_qualidade = "Defeito_Painel"
                
                yield env.timeout(tempo_processo)
                historico_producao.append({
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Tempo_Simulado_s": env.now,
                    "Moto_ID": nome_moto,
                    "Modelo": modelo,
                    "Estacao": estacao,
                    "Tempo_Processo_s": round(tempo_processo, 2),
                    "Tempo_Idle_Setup_s": round(tempo_ocioso_setup, 2),
                    "Status_Qualidade": status_qualidade
                })

    def gerador_motos(env, estacoes_recursos):
        moto_id = 1
        modelos_mix = ["XTZ 150", "FACTOR 150", "CROSSER 150", "LANDER 250"]
        while True:
            modelo = random.choice(modelos_mix)
            env.process(linha_montagem(env, f"MOTO_{moto_id:03d}", modelo, estacoes_recursos))
            moto_id += 1
            yield env.timeout(TAKT_TIME_META)

    st.write("🏃 Executando simulação...")
    env = simpy.Environment()
    estacoes_recursos = {estacao: simpy.Resource(env, capacity=1) for estacao in TEMPOS_ESTACOES.keys()}
    env.process(gerador_motos(env, estacoes_recursos))
    env.run(until=TEMPO_SIMULACAO)

    df_resultado = pd.DataFrame(historico_producao)
    
    motos_calc = int(df_resultado['Moto_ID'].nunique())
    defeitos_calc = int(len(df_resultado[df_resultado['Status_Qualidade'] == 'Defeito_Painel']))

    st.success(f"📊 Simulação Concluída! Motos: {motos_calc} | Defeitos: {defeitos_calc}")

    # --- ENVIANDO OS DADOS REAIS CALCULADOS VIA MQTT ---
    try:
        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        client.connect("localhost", 1883, 60)
        client.loop_start()

        payload = {
            "grupo": "Grupo 8 - Motocicletas (PIM)",
            "motos_finalizadas": motos_calc,  
            "defeitos": defeitos_calc
        }

        client.publish("ufam/digitaltwin/producao", json.dumps(payload))
        st.info("📡 Dados publicados no Broker MQTT com sucesso!")
        
        time.sleep(1)
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        st.error(f"Erro ao conectar no MQTT: {e}")