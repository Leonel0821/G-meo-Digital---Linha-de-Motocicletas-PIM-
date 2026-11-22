import streamlit as st
import random
import time
import simpy
import sqlite3
import pandas as pd
from datetime import datetime

# ==============================================================================
# CONFIGURAÇÕES BÁSICAS (MODELOS DE MOTOCICLETAS)
# ==============================================================================
MODELOS = ["XTZ 150", "Factor 150", "Crosser 150", "Lander 250"]
CICLO_SIMULACAO_MAX = 10  # Simula os 90s do Takt Time da esteira real
DB_PATH = "estacao_e11.db"

st.set_page_config(page_title="Simulação Operador E11 - Grupo 8", layout="wide")

# ==============================================================================
# CAMADA 3: BANCO DE DADOS SQLITE (SÉRIES TEMPORAIS E HISTÓRICO)
# ==============================================================================
def inicializar_banco():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eventos_e11 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            moto_numero INTEGER,
            modelo TEXT,
            tempo_ciclo INTEGER,
            tempo_parada INTEGER,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

def registrar_evento_db(moto_num, modelo, ciclo, parada, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO eventos_e11 (timestamp, moto_numero, modelo, tempo_ciclo, tempo_parada, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), moto_num, modelo, ciclo, parada, status))
    conn.commit()
    conn.close()

def carregar_historico_db():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT 
            timestamp AS "Horário Registro",
            moto_numero AS "Moto ID",
            modelo AS "Modelo",
            tempo_ciclo AS "Tempo Ciclo (s)",
            tempo_parada AS "Tempo Parada/Falha (s)",
            (tempo_ciclo + tempo_parada) AS "Tempo Total Gasto (s)",
            status AS "Status Qualidade"
        FROM eventos_e11
        ORDER BY id DESC
    """, conn)
    conn.close()
    return df

def limpar_banco():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM eventos_e11")
    conn.commit()
    conn.close()

inicializar_banco()

# ==============================================================================
# CAMADA 1: MOTOR DE SIMULAÇÃO DE EVENTOS DISCRETOS (SIMPY)
# ==============================================================================
def processo_estacao_e11(env, estacao_resource):
    """Processo SimPy que modela a ocupação da estação E11 e o avanço do ciclo."""
    with estacao_resource.request() as req:
        yield req
        yield env.timeout(1)

def avancar_relogio_simpy():
    st.session_state.simpy_env.run(until=st.session_state.simpy_env.now + 1)

# ==============================================================================
# ESTADOS DO OPERADOR E DA ESTAÇÃO 11
# ==============================================================================
def resetar_estado():
    st.session_state.sim_ativa = False
    st.session_state.simpy_env = simpy.Environment()
    st.session_state.simpy_estacao = simpy.Resource(st.session_state.simpy_env, capacity=1)
    st.session_state.tempo_ciclo = 0
    st.session_state.esteira_travada = False
    st.session_state.tempo_travada_atual = 0
    st.session_state.tempo_parada_total = 0
    st.session_state.moto_atual = 1
    st.session_state.motos_produzidas = 0
    st.session_state.modelo_moto = random.choice(MODELOS)
    st.session_state.kit_escolhido = None
    st.session_state.ciclo_finalizado = False
    st.session_state.comparacao_status = "Aguardando"

if "sim_ativa" not in st.session_state:
    resetar_estado()

def avancar_proxima_moto():
    # Define o status final considerando se houve parada por falha durante o ciclo
    status_final = "Conforme (Com Retrabalho)" if st.session_state.tempo_travada_atual > 0 else "Conforme"
    
    registrar_evento_db(
        st.session_state.moto_atual,
        st.session_state.modelo_moto,
        st.session_state.tempo_ciclo,
        st.session_state.tempo_travada_atual,
        status_final
    )
    st.session_state.motos_produzidas += 1
    st.session_state.moto_atual += 1
    st.session_state.modelo_moto = random.choice(MODELOS)
    st.session_state.tempo_ciclo = 0
    st.session_state.esteira_travada = False
    st.session_state.tempo_travada_atual = 0
    st.session_state.kit_escolhido = None
    st.session_state.ciclo_finalizado = False
    st.session_state.comparacao_status = "Aguardando"

def registrar_escolha_operador(kit_escolhido):
    st.session_state.kit_escolhido = kit_escolhido
    if st.session_state.esteira_travada:
        if kit_escolhido == st.session_state.modelo_moto:
            st.session_state.esteira_travada = False
            st.session_state.comparacao_status = "Conforme"
            avancar_proxima_moto()
        else:
            st.session_state.comparacao_status = "Não conforme"

# ==============================================================================
# BARRA LATERAL SIMPLES (CONTROLE DE PLAY/PAUSE)
# ==============================================================================
with st.sidebar:
    st.header("Controle")
    col1, col2 = st.columns(2)
    if col1.button("▶ Iniciar", use_container_width=True):
        st.session_state.sim_ativa = True
    if col2.button("⏸ Pausar", use_container_width=True):
        st.session_state.sim_ativa = False
    if st.button("↺ Resetar Simulação", use_container_width=True):
        resetar_estado()
    if st.button("🗑️ Limpar Histórico", use_container_width=True):
        limpar_banco()
        st.rerun()

    operador_auto = st.checkbox("Operador Automático", value=False)

# ==============================================================================
# TELA PRINCIPAL (INDICADORES + CAIXAS DOS PAINÉIS)
# ==============================================================================
st.title("Simulação do Operador na E11 (segundos)")

k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
k1.metric("Moto na E11", st.session_state.modelo_moto)
k2.metric("Motos Produzidas", st.session_state.motos_produzidas)
k3.metric("QRcode Moto", "OK")
k4.metric("Comparação QRcode", st.session_state.comparacao_status)
k5.metric("Tempo de Apresentação", f"{st.session_state.tempo_ciclo}")
k6.metric("Esteira Travada", f"{st.session_state.tempo_travada_atual}")
k7.metric("Parada Total", f"{st.session_state.tempo_parada_total}")

st.divider()

if st.session_state.esteira_travada:
    if st.session_state.kit_escolhido is None:
        st.error(f"⛔ NÃO CONFORME (ESTEIRA TRAVADA AOS 10s): Nenhum painel foi bipado! Aperte o botão de '{st.session_state.modelo_moto}' para liberar.")
    else:
        st.error(f"⛔ NÃO CONFORME (ESTEIRA TRAVADA AOS 10s): Foi montado '{st.session_state.kit_escolhido}', mas a moto exige '{st.session_state.modelo_moto}'! Corrija para liberar.")
elif st.session_state.ciclo_finalizado and st.session_state.comparacao_status == "Conforme":
    st.success(f"✅ CONFORME (FIM DO CICLO DE 10s): Painel '{st.session_state.modelo_moto}' montado corretamente! Liberando moto...")
else:
    if st.session_state.kit_escolhido is not None:
        st.info(f"⚙️ ESTEIRA EM MOVIMENTO ({st.session_state.tempo_ciclo}s / 10s): Painel selecionado ({st.session_state.kit_escolhido}). Aguardando conclusão do ciclo...")
    else:
        st.info(f"🔵 ESTEIRA EM MOVIMENTO ({st.session_state.tempo_ciclo}s / 10s): Moto '{st.session_state.modelo_moto}' na estação. Escolha o painel indicado pelo LED.")

st.subheader("Caixas com Kits de Painel")
cols_caixas = st.columns(4)
for idx, modelo in enumerate(MODELOS):
    with cols_caixas[idx]:
        is_alvo = (modelo == st.session_state.modelo_moto)
        if is_alvo:
            if st.session_state.esteira_travada:
                st.error(f"🔴 **LED ALERTA**\n\n### {modelo}\nPegue ESTE painel!")
            else:
                st.success(f"🟢 **LED ACESO**\n\n### {modelo}\nCaixa Indicada")
        else:
            st.warning(f"⚪ LED Apagado\n\n### {modelo}\nEm espera")

        if st.button(f"Escolher {modelo}", key=f"btn_{modelo}", use_container_width=True):
            registrar_escolha_operador(modelo)
            st.rerun()

st.divider()

# ==============================================================================
# HISTÓRICO DE PRODUÇÃO (MOTOS FINALIZADAS, TEMPO GASTO E FALHAS)
# ==============================================================================
st.subheader("📋 Histórico de Produção (Estação E11)")

df_historico = carregar_historico_db()

if not df_historico.empty:
    # Separa apenas os registros de motos finalizadas para métricas reais
    df_finalizadas = df_historico[df_historico["Status Qualidade"].str.contains("Conforme")]
    total_falhas = len(df_historico[df_historico["Status Qualidade"] != "Conforme"])
    tempo_medio = df_finalizadas["Tempo Total Gasto (s)"].mean() if not df_finalizadas.empty else 0.0

    m1, m2, m3 = st.columns(3)
    m1.metric("Motos Finalizadas (Banco)", len(df_finalizadas))
    m2.metric("Total de Falhas / Retrabalhos", total_falhas)
    m3.metric("Tempo Médio Total / Moto", f"{tempo_medio:.1f}s")

    st.dataframe(
        df_historico,
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Nenhuma moto finalizada ou falha registrada ainda. Clique em 'Iniciar' na barra lateral.")

# ==============================================================================
# MOTOR DO RELÓGIO DIRIGIDO PELO SIMPY
# ==============================================================================
if st.session_state.sim_ativa:
    time.sleep(1)

    st.session_state.simpy_env.process(
        processo_estacao_e11(st.session_state.simpy_env, st.session_state.simpy_estacao)
    )
    avancar_relogio_simpy()

    if st.session_state.esteira_travada:
        st.session_state.tempo_travada_atual += 1
        st.session_state.tempo_parada_total += 1
        
        # Operador automático corrige o erro após 4 segundos de parada
        if operador_auto and st.session_state.tempo_travada_atual >= 4:
            registrar_escolha_operador(st.session_state.modelo_moto)

    elif st.session_state.ciclo_finalizado:
        avancar_proxima_moto()

    else:
        st.session_state.tempo_ciclo += 1

        # Simula a ação do operador no segundo 3 do ciclo
        if operador_auto and st.session_state.tempo_ciclo == 3 and st.session_state.kit_escolhido is None:
            if random.random() < 0.25:
                errados = [m for m in MODELOS if m != st.session_state.modelo_moto]
                registrar_escolha_operador(random.choice(errados))
            else:
                registrar_escolha_operador(st.session_state.modelo_moto)

        # Verifica o status ao atingir o tempo máximo do ciclo (10s)
        if st.session_state.tempo_ciclo >= CICLO_SIMULACAO_MAX:
            if st.session_state.kit_escolhido == st.session_state.modelo_moto:
                st.session_state.comparacao_status = "Conforme"
                st.session_state.ciclo_finalizado = True
            else:
                st.session_state.comparacao_status = "Não conforme"
                st.session_state.esteira_travada = True
                motivo_falha = (
                    "Falha: Painel não bipado"
                    if st.session_state.kit_escolhido is None
                    else f"Falha: Bipado {st.session_state.kit_escolhido}"
                )
                registrar_evento_db(
                    st.session_state.moto_atual,
                    st.session_state.modelo_moto,
                    st.session_state.tempo_ciclo,
                    0,
                    motivo_falha
                )

    st.rerun()
