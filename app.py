import streamlit as st
import random
import time

# ==============================================================================
# CONFIGURAÇÕES BÁSICAS (MODELOS DE MOTOCICLETAS)
# ==============================================================================
MODELOS = ["XTZ 150", "Factor 150", "Crosser 150", "Lander 250"]
CICLO_SIMULACAO_MAX = 10  # Simula os 90s do Takt Time da esteira real

st.set_page_config(page_title="Simulação Operador E11 - Grupo 8", layout="wide")

# ==============================================================================
# ESTADOS DO OPERADOR E DA ESTAÇÃO 11
# ==============================================================================
if "sim_ativa" not in st.session_state:
    st.session_state.sim_ativa = False
    st.session_state.tempo_ciclo = 0
    st.session_state.esteira_travada = False
    st.session_state.tempo_travada_atual = 0
    st.session_state.tempo_parada_total = 0
    st.session_state.moto_atual = 1
    st.session_state.modelo_moto = random.choice(MODELOS)
    st.session_state.kit_escolhido = None
    st.session_state.ciclo_finalizado = False
    st.session_state.comparacao_status = "Aguardando"

def avancar_proxima_moto():
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

    # Caso a esteira já esteja travada após os 10s e o operador esteja corrigindo o erro:
    if st.session_state.esteira_travada:
        if kit_escolhido == st.session_state.modelo_moto:
            st.session_state.esteira_travada = False
            st.session_state.tempo_travada_atual = 0
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

    if st.button("↺ Resetar", use_container_width=True):
        st.session_state.sim_ativa = False
        st.session_state.tempo_ciclo = 0
        st.session_state.esteira_travada = False
        st.session_state.tempo_travada_atual = 0
        st.session_state.tempo_parada_total = 0
        st.session_state.moto_atual = 1
        st.session_state.modelo_moto = random.choice(MODELOS)
        st.session_state.kit_escolhido = None
        st.session_state.ciclo_finalizado = False
        st.session_state.comparacao_status = "Aguardando"

    operador_auto = st.checkbox("Operador Automático", value=False)

# ==============================================================================
# TELA PRINCIPAL (INDICADORES + CAIXAS DOS PAINÉIS + ESPAÇO DO OPERADOR)
# ==============================================================================
st.title("Simulação do Operador na E11 (segundos)")

# 1. Indicadores essenciais
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Moto na E11", st.session_state.modelo_moto)
k2.metric("QRcode Moto", "OK")
k3.metric("Comparação QRcode", st.session_state.comparacao_status)
k4.metric("Ciclo (Takt 90s)", str(st.session_state.tempo_ciclo) + " ")
k5.metric("Esteira Travada", str(st.session_state.tempo_travada_atual) + " ")
k6.metric("Parada Total", str(st.session_state.tempo_parada_total) + " ")

st.divider()

# 2. Barra de status da esteira (só exibe resultado ao completar os 10s!)
if st.session_state.esteira_travada:
    if st.session_state.kit_escolhido is None:
        st.error("⛔ NÃO CONFORME (ESTEIRA TRAVADA AOS 10s): Nenhum painel foi bipado! Aperte o botão de '" + st.session_state.modelo_moto + "' para liberar.")
    else:
        st.error("⛔ NÃO CONFORME (ESTEIRA TRAVADA AOS 10s): Foi montado '" + st.session_state.kit_escolhido + "', mas a moto exige '" + st.session_state.modelo_moto + "'! Corrija para liberar.")
elif st.session_state.ciclo_finalizado and st.session_state.comparacao_status == "Conforme":
    st.success("✅ CONFORME (FIM DO CICLO DE 10s): Painel '" + st.session_state.modelo_moto + "' montado corretamente! Liberando moto...")
else:
    if st.session_state.kit_escolhido is not None:
        st.info("⚙️ ESTEIRA EM MOVIMENTO (" + str(st.session_state.tempo_ciclo) + "s / 10s): Painel selecionado (" + st.session_state.kit_escolhido + "). Aguardando conclusão do ciclo...")
    else:
        st.info("🔵 ESTEIRA EM MOVIMENTO (" + str(st.session_state.tempo_ciclo) + "s / 10s): Moto '" + st.session_state.modelo_moto + "' na estação. Escolha o painel indicado pelo LED.")

# 3. Quadrados das 4 caixas com o botão embaixo de cada uma
st.subheader("Caixas com Kits de Painel")
cols_caixas = st.columns(4)

for idx, modelo in enumerate(MODELOS):
    with cols_caixas[idx]:
        is_alvo = (modelo == st.session_state.modelo_moto)

        if is_alvo:
            if st.session_state.esteira_travada:
                st.error("🔴 **LED ALERTA**\n\n### " + modelo + "\nPegue ESTE painel!")
            else:
                st.success("🟢 **LED ACESO**\n\n### " + modelo + "\nCaixa Indicada")
        else:
            st.warning("⚪ LED Apagado\n\n### " + modelo + "\nEm espera")

        if st.button("Escolher " + modelo, key="btn_" + modelo, use_container_width=True):
            registrar_escolha_operador(modelo)
            st.rerun()

st.divider()


# ==============================================================================
# MOTOR DO RELÓGIO (1 SEGUNDO POR VEZ)
# ==============================================================================
if st.session_state.sim_ativa:
    time.sleep(1)

    # Caso 1: Esteira travada após o fim dos 10s (aguardando correção do operador)
    if st.session_state.esteira_travada:
        st.session_state.tempo_travada_atual += 1
        st.session_state.tempo_parada_total += 1
        if operador_auto and st.session_state.tempo_travada_atual >= 4:
            registrar_escolha_operador(st.session_state.modelo_moto)

    # Caso 2: Se o ciclo acabou de finalizar com sucesso (10s), avança para a próxima moto
    elif st.session_state.ciclo_finalizado:
        avancar_proxima_moto()

    # Caso 3: Esteira em movimento normal (contando de 0 até 10 segundos)
    else:
        st.session_state.tempo_ciclo += 1

        # Operador automático faz a escolha no segundo 3, mas o tempo segue até 10s
        if operador_auto and st.session_state.tempo_ciclo == 3 and st.session_state.kit_escolhido is None:
            if random.random() < 0.25:
                errados = [m for m in MODELOS if m != st.session_state.modelo_moto]
                registrar_escolha_operador(random.choice(errados))
            else:
                registrar_escolha_operador(st.session_state.modelo_moto)

        # Quando o tempo atinge 10 segundos (fim do trajeto da moto na estação)
        if st.session_state.tempo_ciclo >= CICLO_SIMULACAO_MAX:
            if st.session_state.kit_escolhido == st.session_state.modelo_moto:
                st.session_state.comparacao_status = "Conforme"
                st.session_state.ciclo_finalizado = True
            else:
                st.session_state.comparacao_status = "Não conforme"
                st.session_state.esteira_travada = True

    st.rerun()
