import json
import paho.mqtt.client as mqtt
import random
import pandas as pd
from datetime import datetime
import streamlit as st
import plotly.express as px
import time

st.set_page_config(layout="wide", page_title="Gêmeo Digital - Grupo 8")

# ==========================================
# INICIALIZAÇÃO DE ESTADOS (MEMÓRIA DO GÊMEO)
# ==========================================
if 'simulacao_ativa' not in st.session_state:
    st.session_state.simulacao_ativa = False
if 'moto_atual' not in st.session_state:
    st.session_state.moto_atual = 0
if 'historico_producao' not in st.session_state:
    st.session_state.historico_producao = []

# Estados específicos da Estação 11 (Operador + Esteira + Andon)
if 'e11_tempo_ciclo' not in st.session_state:
    st.session_state.e11_tempo_ciclo = 0
if 'e11_tempo_travada' not in st.session_state:
    st.session_state.e11_tempo_travada = 0
if 'e11_erro_pendente' not in st.session_state:
    st.session_state.e11_erro_pendente = False
if 'e11_esteira_travada' not in st.session_state:
    st.session_state.e11_esteira_travada = False
if 'e11_montagem_ok' not in st.session_state:
    st.session_state.e11_montagem_ok = False
if 'e11_tempo_parada_acumulado' not in st.session_state:
    st.session_state.e11_tempo_parada_acumulado = 0.0
if 'e11_log' not in st.session_state:
    st.session_state.e11_log = "Clique em 'Iniciar' na barra lateral para começar."

# ==========================================
# CONFIGURAÇÃO DA BARRA LATERAL
# ==========================================
st.sidebar.header("⚙️ Configurações do Gêmeo Digital")
TEMPO_SIMULACAO = st.sidebar.number_input("Tempo de Simulação (segundos)", value=3600, step=90)
TAKT_TIME_META = st.sidebar.number_input("Meta Takt Time (segundos)", value=90)
PPM_DEFEITO = st.sidebar.number_input("PPM de Defeito (Estação 11)", value=35000)
TEMPO_SETUP_MODELO = st.sidebar.number_input("Tempo de troca de modelo (segundos)", value=180)

TEMPOS_ESTACOES = {
    "E01": 75, "E02": 85, "E03": 80, "E04": 85, "E05": 70,
    "E06": 90, "E07": 85, "E08": 80, "E09": 85, "E10": 80,
    "E11": 85, "E12": 80, "E13": 85, "E14": 75, "E15": 80,
    "E16": 85, "E17": 85, "E18": 80
}

col_btn1, col_btn2 = st.sidebar.columns(2)
if col_btn1.button("🚀 Iniciar"):
    st.session_state.simulacao_ativa = True
    st.session_state.moto_atual = 0
    st.session_state.historico_producao = []
    st.session_state.e11_tempo_ciclo = 0
    st.session_state.e11_tempo_travada = 0
    st.session_state.e11_erro_pendente = False
    st.session_state.e11_esteira_travada = False
    st.session_state.e11_montagem_ok = False
    st.session_state.e11_tempo_parada_acumulado = 0.0
    st.session_state.e11_log = "Simulação iniciada! Ciclo de 10 segundos (equivale a 90 segundos)."
    st.rerun()

if col_btn2.button("⏹️ Parar"):
    st.session_state.simulacao_ativa = False
    st.session_state.e11_log = "Simulação pausada pelo usuário."
    st.rerun()

# ==========================================
# FUNÇÃO DE PROCESSAMENTO DE 1 CICLO (MOTO)
# ==========================================
def processar_avanco_esteira(tempo_e11_registrado, teve_erro_e11):
    st.session_state.moto_atual += 1
    moto_num = st.session_state.moto_atual
    moto_id = f"{moto_num:03d}"

    modelos_mix = ["XTZ 150", "FACTOR 150", "CROSSER 150", "LANDER 250"]
    modelo_atual = random.choice(modelos_mix)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for estacao, tempo_base in TEMPOS_ESTACOES.items():
        if estacao == "E11":
            tempo_processo = float(tempo_e11_registrado)
            status_qualidade = "Defeito_Painel" if teve_erro_e11 else "Aprovado"
            tempo_espera = round(tempo_e11_registrado - 85.0, 2) if tempo_e11_registrado > 85 else 0.0
        else:
            tempo_processo = round(max(10, random.normalvariate(tempo_base, 2)), 2)
            status_qualidade = "Aprovado"
            tempo_espera = round(random.uniform(0.1, 1.5), 2)

        st.session_state.historico_producao.append({
            "horario_registro": agora,
            "moto_id": moto_id,
            "modelo": modelo_atual,
            "estacao": estacao,
            "tempo_espera": tempo_espera,
            "tempo_processo": tempo_processo,
            "Status_Qualidade": status_qualidade
        })

    try:
        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        client.connect("localhost", 1883, 60)
        df_temp = pd.DataFrame(st.session_state.historico_producao)
        defeitos_atual = int(len(df_temp[df_temp['Status_Qualidade'] == 'Defeito_Painel']))

        payload = {
            "grupo": "Grupo 8 - Motocicletas (PIM)",
            "moto_atual": moto_id,
            "modelo": modelo_atual,
            "motos_finalizadas": moto_num,
            "defeitos": defeitos_atual,
            "tempo_e11": tempo_e11_registrado,
            "tempo_parada_acumulado": st.session_state.e11_tempo_parada_acumulado,
            "lampada_vermelha_e11": st.session_state.e11_esteira_travada
        }
        client.publish("ufam/digitaltwin/producao", json.dumps(payload))
        client.disconnect()
    except Exception:
        pass

# ==========================================
# INTERFACE PRINCIPAL (SEMPRE VISÍVEL)
# ==========================================
total_motos = max(1, int(TEMPO_SIMULACAO // TAKT_TIME_META))

st.markdown("## Gêmeo Digital - Grupo 8 - Cenário 09 - Linha de Motocicletas (PIM)")
st.markdown("###  Simulação do montador da estação 11")

col_op1, col_op2, col_op3, col_lamp = st.columns([2, 2, 2, 1.5])

with col_op1:
    desabilitar_verde = (not st.session_state.simulacao_ativa) or st.session_state.e11_esteira_travada or st.session_state.e11_erro_pendente or st.session_state.e11_montagem_ok
    if st.button("🟢 PAINEL CORRETO", use_container_width=True, disabled=desabilitar_verde):
        st.session_state.e11_montagem_ok = True
        st.session_state.e11_log = "🟢 OPERADOR: Botão Verde acionado! Aguardando fechar 10 segundos"
        st.rerun()

with col_op2:
    desabilitar_vermelho = (not st.session_state.simulacao_ativa) or st.session_state.e11_erro_pendente
    if st.button("🔴 PAINEL ERRADO", use_container_width=True, disabled=desabilitar_vermelho):
        st.session_state.e11_erro_pendente = True
        st.session_state.e11_montagem_ok = False
        st.session_state.e11_log = "🟡 OPERADOR: Botão Vermelho acionado. O erro será acusado se passar de 10 segundos!"
        st.rerun()

with col_op3:
    desabilitar_laranja = (not st.session_state.simulacao_ativa) or (not st.session_state.e11_erro_pendente)
    if st.button("🟠 CORRIGIR / DESTRAVAR", use_container_width=True, disabled=desabilitar_laranja):
        if not st.session_state.e11_esteira_travada:
            st.session_state.e11_erro_pendente = False
            st.session_state.e11_log = "🟠 CORREÇÃO RÁPIDA: Erro corrigido antes dos 10 segundos. Esteira não travou!"
        else:
            tempo_parado = st.session_state.e11_tempo_travada
            tempo_calculado = round((tempo_parado / 10.0) * TAKT_TIME_META, 2)
            
            # Soma o tempo desta parada ao acumulado total
            st.session_state.e11_tempo_parada_acumulado = round(
                st.session_state.e11_tempo_parada_acumulado + tempo_calculado, 2
            )
            
            # Na estação E11, registra o tempo padrão (85s) + tempo que ficou parada
            tempo_total_ciclo_e11 = round(85.0 + tempo_calculado, 2)
            processar_avanco_esteira(tempo_total_ciclo_e11, teve_erro_e11=True)
            
            st.session_state.e11_log = (
                f"🟠 CORRIGIDO: Esteira ficou {tempo_parado}s parada (+{tempo_calculado}s) -> "
                f"Total acumulado de parada: {st.session_state.e11_tempo_parada_acumulado}s!"
            )

        st.session_state.e11_tempo_ciclo = 0
        st.session_state.e11_tempo_travada = 0
        st.session_state.e11_erro_pendente = False
        st.session_state.e11_esteira_travada = False
        st.session_state.e11_montagem_ok = False
        st.rerun()

with col_lamp:
    if st.session_state.e11_esteira_travada:
        st.markdown(
            """
            <div style="background-color:#3a0000; border:2px solid #ff1e1e; border-radius:10px; padding:10px; text-align:center; box-shadow: 0 0 20px #ff1e1e;">
                <div style="width:28px; height:28px; background-color:#ff1e1e; border-radius:50%; margin:0 auto 5px auto; box-shadow: 0 0 15px #ff5252;"></div>
                <strong style="color:#ff5252; font-size:13px;">🚨 DEFEITO<br>ESTEIRA TRAVADA</strong>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div style="background-color:#1a1c23; border:1px solid #333; border-radius:10px; padding:10px; text-align:center;">
                <div style="width:28px; height:28px; background-color:#3a1515; border-radius:50%; margin:0 auto 5px auto; border:1px solid #552222;"></div>
                <span style="color:#888; font-size:13px;">⚪ LÂMPADA APAGADA<br></span>
            </div>
            """,
            unsafe_allow_html=True
        )

# Barra de Status da Estação 11
c_status1, c_status2, c_status3, c_status4 = st.columns(4)
c_status1.metric("Tempo de Simulação", f"{st.session_state.e11_tempo_ciclo} s")
c_status2.metric("Esteira Travada", f"{st.session_state.e11_tempo_travada} s")
c_status3.metric("Tempo Real de Parada da Linha", f"{st.session_state.e11_tempo_parada_acumulado} s")
c_status4.metric("Progresso da Linha", f"{st.session_state.moto_atual} / {total_motos}")

if st.session_state.e11_esteira_travada:
    st.error(st.session_state.e11_log)
elif st.session_state.e11_erro_pendente:
    st.warning(st.session_state.e11_log)
else:
    st.info(st.session_state.e11_log)

st.markdown("---")

# ==========================================
# DASHBOARD DO GÊMEO DIGITAL (MÉTRICAS E GRÁFICOS)
# ==========================================

if len(st.session_state.historico_producao) > 0:
    df_parcial = pd.DataFrame(st.session_state.historico_producao)
    moto_num = st.session_state.moto_atual
    defeitos_atual = int(len(df_parcial[df_parcial['Status_Qualidade'] == 'Defeito_Painel']))
    taxa_defeito_pct = (defeitos_atual / moto_num) * 100

    meta_proporcional = 37
    fator_proporcional = max(0.0, min(1.0, (PPM_DEFEITO - 17500) / (35000 - 17500)))

    nota_5s_calc = max(0, min(100, int(85.0 - (55.0 * fator_proporcional))))
    variacao_5s = nota_5s_calc - 30

    deslocamento_base = 30.0 + (20.0 * fator_proporcional)
    deslocamento_total_calc = round(deslocamento_base + random.uniform(-1.0, 1.0), 1)
    variacao_deslocamento = deslocamento_total_calc - 50.0
    porcentagem_reducao_deslocamento = (variacao_deslocamento / 50.0) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Motos Finalizadas (Saída E18)", f"{moto_num}", f"{moto_num - meta_proporcional} vs Meta ({meta_proporcional})")
    c2.metric("Defeito de montagem (E11)", f"{defeitos_atual}")
    c3.metric("Taxa de Defeito (%)", f"{taxa_defeito_pct:.2f}%", f"{taxa_defeito_pct - 3.50:.2f}% vs Inicial")

    c4, c5, c6 = st.columns(3)
    c4.metric("Tempo de Troca de Modelo", f"{TEMPO_SETUP_MODELO} s", "Sem alteração")
    c5.metric("Deslocamento do Montador", f"{deslocamento_total_calc} m", f"{variacao_deslocamento:.1f} m ({porcentagem_reducao_deslocamento:.0f}%) vs Inicial")
    c6.metric("Auditoria 5S", f"{nota_5s_calc} / 100", f"{variacao_5s} pts vs Linha de base")

    df_media_estacao = df_parcial.groupby("estacao", as_index=False)["tempo_processo"].mean()
    df_media_estacao["Cor"] = df_media_estacao["tempo_processo"].apply(
        lambda x: "Acima da Meta" if x > TAKT_TIME_META else "Dentro da Meta"
    )
    fig = px.bar(
        df_media_estacao, x="estacao", y="tempo_processo", color="Cor",
        color_discrete_map={"Dentro da Meta": "#1f77b4", "Acima da Meta": "#d62728"},
        title="📊 Gráfico de Balanceamento de Linha (Tempo Médio por Estação)"
    )
    fig.add_hline(y=TAKT_TIME_META, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("🗄️ Banco de Dados Local (Histórico em Tempo Real)")
    st.dataframe(df_parcial.iloc[::-1], use_container_width=True)

# ==========================================
# MOTOR DO RELÓGIO (RODA 1 SEGUNDO POR VEZ)
# ==========================================
if st.session_state.simulacao_ativa and st.session_state.moto_atual < total_motos:
    time.sleep(1)

    if not st.session_state.e11_esteira_travada:
        st.session_state.e11_tempo_ciclo += 1
        if st.session_state.e11_tempo_ciclo >= 10:
            if st.session_state.e11_erro_pendente:
                st.session_state.e11_esteira_travada = True
                st.session_state.e11_log = "🚨 ALERTA: Passaram 10s! Erro acusado, LÂMPADA VERMELHA ACESA e esteira TRAVADA."
            else:
                processar_avanco_esteira(85.0, teve_erro_e11=False)
                if st.session_state.e11_montagem_ok:
                    st.session_state.e11_log = "✅ CICLO OK: Botão verde confirmado."
                else:
                    st.session_state.e11_log = "⚙️ CICLO AUTOMÁTICO: 10 segundos"
                st.session_state.e11_tempo_ciclo = 0
                st.session_state.e11_montagem_ok = False
    else:
        st.session_state.e11_tempo_travada += 1

    if st.session_state.moto_atual >= total_motos:
        st.session_state.simulacao_ativa = False

    st.rerun()

