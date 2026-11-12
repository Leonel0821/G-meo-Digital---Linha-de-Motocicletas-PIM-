import json
import paho.mqtt.client as mqtt
import random
import pandas as pd
from datetime import datetime
import streamlit as st
import time
import plotly.express as px

st.set_page_config(layout="wide", page_title="Gêmeo Digital - Grupo 8")

# ==========================================
# CONFIGURAÇÃO DA BARRA LATERAL
# ==========================================
st.sidebar.header("⚙️ Configurações do Gêmeo Digital")

TEMPO_SIMULACAO = st.sidebar.number_input("Tempo de Simulação (segundos)", value=3600, step=90)
TAKT_TIME_META = st.sidebar.number_input("Meta Takt Time (segundos)", value=90)
PPM_DEFEITO = st.sidebar.number_input("PPM de Defeito (Estação 11)", value=35000)
TEMPO_SETUP_MODELO = st.sidebar.number_input("Tempo de troca de modelo (segundos)", value=180)

TEMPOS_ESTACOES = {
    "E01": 75, "E02": 85, "E03": 80, "E04": 85, "E05": 70, "E06": 90,
    "E07": 85, "E08": 80, "E09": 85, "E10": 80, "E11": 85, "E12": 80,
    "E13": 85, "E14": 75, "E15": 80, "E16": 85, "E17": 85, "E18": 80
}

# ==========================================
# BOTÃO DE SIMULAÇÃO CONTÍNUA (1 MOTO A CADA 10s)
# ==========================================
if st.sidebar.button("🚀 Rodar Simulação e Enviar Dados"):
    
    # Matemática teórica: 3600s / 90s = 40 motos em 1 hora
    total_motos = max(1, int(TEMPO_SIMULACAO // TAKT_TIME_META))
    modelos_mix = ["XTZ 150", "FACTOR 150", "CROSSER 150", "LANDER 250"]
    historico_producao = []

    # Cálculo base da Auditoria 5S
    fator_proporcional = max(0.0, min(1.0, (PPM_DEFEITO - 17500) / (35000 - 17500)))
    nota_5s_calc = max(0, min(100, int(85.0 - (55.0 * fator_proporcional) + random.randint(-2, 2))))
    variacao_5s = nota_5s_calc - 30
    porcentagem_ganho_5s = (variacao_5s / 30.0) * 100

    # Conecta ao MQTT
    client = None
    try:
        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        client.connect("localhost", 1883, 60)
        client.loop_start()
    except Exception as e:
        st.sidebar.warning(f"MQTT offline: {e}")

    banner_status = st.empty()
    barra_progresso = st.progress(0)
    painel_ao_vivo = st.empty()

    meta_proporcional = 37  # Meta de referência do cenário

    # Loop contínuo: monta moto 1, 2, 3... até completar as 40 motos
    for moto_num in range(1, total_motos + 1):
        moto_id = f"{moto_num:03d}"
        modelo_atual = random.choice(modelos_mix)
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        teve_setup_nesta_moto = False

        # Gera os registros das 18 estações para esta moto
        for estacao, tempo_base in TEMPOS_ESTACOES.items():
            tempo_processo = max(10, random.normalvariate(tempo_base, 2))
            status_qualidade = "Aprovado"
            tempo_espera = round(random.uniform(0.1, 1.5), 2)

            if estacao == "E11":
                if random.random() < 0.15:
                    tempo_espera = round(max(10, random.normalvariate(TEMPO_SETUP_MODELO, 5)), 2)
                    teve_setup_nesta_moto = True
                if random.random() < (PPM_DEFEITO / 1000000):
                    status_qualidade = "Defeito_Painel"

            historico_producao.append({
                "horario_registro": agora,
                "moto_id": moto_id,
                "modelo": modelo_atual,
                "estacao": estacao,
                "tempo_espera": tempo_espera,
                "tempo_processo": round(tempo_processo, 2),
                "Status_Qualidade": status_qualidade
            })

        # CÁLCULO DINÂMICO DO DESLOCAMENTO DO MONTADOR (Atualiza a cada moto!)
        deslocamento_base = 30.0 + (20.0 * fator_proporcional)
        extra_setup = 2.5 if teve_setup_nesta_moto else 0.0
        deslocamento_total_calc = round(deslocamento_base + extra_setup + random.uniform(-1.8, 1.8), 1)
        variacao_deslocamento = deslocamento_total_calc - 50.0
        porcentagem_reducao_deslocamento = (variacao_deslocamento / 50.0) * 100

        df_parcial = pd.DataFrame(historico_producao)
        defeitos_atual = int(len(df_parcial[df_parcial['Status_Qualidade'] == 'Defeito_Painel']))
        taxa_defeito_pct = (defeitos_atual / moto_num) * 100

        banner_status.info(f"🏍️ **Produzindo ao Vivo:** Moto **#{moto_id} ({modelo_atual})** finalizada na E18! ({moto_num}/{total_motos})")
        barra_progresso.progress(moto_num / total_motos)

        with painel_ao_vivo.container():
            st.markdown("---")
            st.markdown("## Gêmeo Digital - Grupo 8 - Cenário 09 - Linha de Motocicletas (PIM)")
            st.markdown("#### Monitoramento em Tempo Real - Linha de Montagem de Motocicletas")
            st.markdown("---")

            c1, c2, c3 = st.columns(3)
            c1.metric("Motos Finalizadas (Saída E18)", f"{moto_num}", f"{moto_num - meta_proporcional} vs Meta do Período ({meta_proporcional})")
            c2.metric("Defeito de montagem (E11)", f"{defeitos_atual}")
            c3.metric("Taxa de Defeito (%)", f"{taxa_defeito_pct:.2f}%", f"{taxa_defeito_pct - 3.50:.2f}% vs Inicial")

            c4, c5, c6 = st.columns(3)
            c4.metric("Tempo de Troca de Modelo", f"{TEMPO_SETUP_MODELO} s", "Sem alteração")
            c5.metric("Deslocamento do Montador", f"{deslocamento_total_calc} m", f"{variacao_deslocamento:.1f} m ({porcentagem_reducao_deslocamento:.0f}%) vs Inicial")
            c6.metric("Auditoria 5S", f"{nota_5s_calc} / 100", f"{variacao_5s} pts vs Linha de base")

            st.success("💡 **IMPACTO DA MELHORIA NESTA RODADA:** O Poka-Yoke trouxe uma economia de R$ 50.000,00 em custos por turno!")

            df_media_estacao = df_parcial.groupby("estacao", as_index=False)["tempo_processo"].mean()
            df_media_estacao["Cor"] = df_media_estacao["tempo_processo"].apply(lambda x: "Acima da Meta" if x > TAKT_TIME_META else "Dentro da Meta")
            fig = px.bar(
                df_media_estacao, x="estacao", y="tempo_processo", color="Cor",
                color_discrete_map={"Dentro da Meta": "#1f77b4", "Acima da Meta": "#d62728"},
                title="📊 Gráfico de Balanceamento de Linha (Tempo Médio por Estação)"
            )
            fig.add_hline(y=TAKT_TIME_META, line_dash="dash", line_color="red")
            st.plotly_chart(fig, use_container_width=True, key=f"grafico_vivo_{moto_num}")

            st.subheader("🗄️ Banco de Dados Local (Histórico em Tempo Real)")
            st.dataframe(df_parcial.iloc[::-1], use_container_width=True)

        if client:
            payload = {
                "grupo": "Grupo 8 - Motocicletas (PIM)",
                "moto_atual": moto_id,
                "modelo": modelo_atual,
                "motos_finalizadas": moto_num,
                "defeitos": defeitos_atual,
                "deslocamento_total_m": deslocamento_total_calc,
                "nota_5s": nota_5s_calc
            }
            client.publish("ufam/digitaltwin/producao", json.dumps(payload))

        if moto_num < total_motos:
            time.sleep(10)

    if client:
        client.loop_stop()
        client.disconnect()

    # Salva os dados finais e recarrega a tela limpa
    st.session_state['simulacao_rodada'] = True
    st.session_state['df_resultado'] = pd.DataFrame(historico_producao)
    st.session_state['motos_calc'] = total_motos
    st.session_state['defeitos_calc'] = int(len(st.session_state['df_resultado'][st.session_state['df_resultado']['Status_Qualidade'] == 'Defeito_Painel']))
    st.session_state['deslocamento_total_calc'] = deslocamento_total_calc
    st.session_state['variacao_deslocamento'] = variacao_deslocamento
    st.session_state['porcentagem_reducao_deslocamento'] = porcentagem_reducao_deslocamento
    st.session_state['nota_5s_calc'] = nota_5s_calc
    st.session_state['variacao_5s'] = variacao_5s
    st.session_state['porcentagem_ganho_5s'] = porcentagem_ganho_5s
    st.rerun()

# =========================================================
# RENDERIZAÇÃO DA TELA PERSISTENTE APÓS A SIMULAÇÃO
# =========================================================
if st.session_state.get('simulacao_rodada', False):
    df_resultado = st.session_state['df_resultado']
    motos_calc = st.session_state['motos_calc']
    defeitos_calc = st.session_state['defeitos_calc']
    deslocamento_total_calc = st.session_state['deslocamento_total_calc']
    variacao_deslocamento = st.session_state['variacao_deslocamento']
    porcentagem_reducao_deslocamento = st.session_state['porcentagem_reducao_deslocamento']
    nota_5s_calc = st.session_state['nota_5s_calc']
    variacao_5s = st.session_state['variacao_5s']
    porcentagem_ganho_5s = st.session_state['porcentagem_ganho_5s']

    st.markdown("---")
    st.markdown("## Gêmeo Digital - Grupo 8 - Cenário 09 - Linha de Motocicletas (PIM)")
    st.markdown("#### Monitoramento em Tempo Real - Linha de Montagem de Motocicletas")
    st.markdown("---")

    meta_proporcional = 37
    taxa_defeito_pct = (defeitos_calc / motos_calc) * 100 if motos_calc > 0 else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Motos Finalizadas (Saída E18)", f"{motos_calc}", f"{motos_calc - meta_proporcional} vs Meta do Período ({meta_proporcional})")
    c2.metric("Defeito de montagem (E11)", f"{defeitos_calc}")
    c3.metric("Taxa de Defeito (%)", f"{taxa_defeito_pct:.2f}%", f"{taxa_defeito_pct - 3.50:.2f}% vs Inicial")

    c4, c5, c6 = st.columns(3)
    c4.metric("Tempo de Troca de Modelo", f"{TEMPO_SETUP_MODELO} s", "Sem alteração")
    c5.metric("Deslocamento do Montador", f"{deslocamento_total_calc} m", f"{variacao_deslocamento:.1f} m ({porcentagem_reducao_deslocamento:.0f}%) vs Inicial")
    c6.metric("Auditoria 5S", f"{nota_5s_calc} / 100", f"{variacao_5s} pts vs Linha de base")

    st.success("💡 **IMPACTO DA MELHORIA NESTA RODADA:** O Poka-Yoke trouxe uma economia de R$ 50.000,00 em custos por turno!")

    df_media_estacao = df_resultado.groupby("estacao", as_index=False)["tempo_processo"].mean()
    df_media_estacao["Cor"] = df_media_estacao["tempo_processo"].apply(
        lambda x: "Acima da Meta" if x > TAKT_TIME_META else "Dentro da Meta"
    )
    fig = px.bar(
        df_media_estacao,
        x="estacao",
        y="tempo_processo",
        color="Cor",
        color_discrete_map={"Dentro da Meta": "#1f77b4", "Acima da Meta": "#d62728"},
        title="📊 Gráfico de Balanceamento de Linha (Tempo Médio por Estação)"
    )
    fig.add_hline(y=TAKT_TIME_META, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("🗄️ Banco de Dados Local (Histórico Completo de Eventos da Linha)")
    aba_logs, aba_modelos = st.tabs(["📄 Registros Brutos do Banco", "🏍️ Produção por Modelo de Moto"])

    with aba_logs:
        st.caption("Abaixo estão os registros capturados em tempo real durante a simulação:")
        st.dataframe(df_resultado.iloc[::-1], use_container_width=True)

    with aba_modelos:
        df_saida = df_resultado[df_resultado["estacao"] == "E18"]
        resumo_modelos = df_saida.groupby("modelo", as_index=False)["moto_id"].count()
        resumo_modelos.columns = ["Modelo de Moto", "Quantidade Produzida"]
        st.dataframe(resumo_modelos, use_container_width=True)

