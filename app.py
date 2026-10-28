import json
import paho.mqtt.client as mqtt
import simpy
import random
import pandas as pd
from datetime import datetime
import streamlit as st
import time
import plotly.express as px  # Importação necessária para o gráfico interativo

# Configuração da página para ocupar a tela inteira (Estilo do seu print)
st.set_page_config(layout="wide", page_title="Gêmeo Digital - Grupo 8")

# ==========================================
# CONFIGURAÇÃO DA BARRA LATERAL (STREAMLIT) - CONFIGURAÇÕES ORIGINAIS INTACTAS
# ==========================================
st.sidebar.header("⚙️ Configurações do Gêmeo Digital")

# Inputs interativos exatamente iguais ao seu código original
TEMPO_SIMULACAO = st.sidebar.number_input("Tempo de Simulação (segundos)", value=3600)  # Padrão para 1h (3600s)
TAKT_TIME_META = st.sidebar.number_input("Meta Takt Time (segundos)", value=90)
PPM_DEFEITO = st.sidebar.number_input("PPM de Defeito (Estação 11)", value=35000)
TEMPO_SETUP_MODELO = st.sidebar.number_input("Tempo de troca de modelo (segundos)", value=180)

# Botão para disparar a simulação e atualizar o Dashboard
if st.sidebar.button("🚀 Rodar Simulação e Enviar Dados"):
    
    # Tempos médios de processamento das 18 estações
    TEMPOS_ESTACOES = {
        "E01": 75, "E02": 85, "E03": 80, "E04": 85, "E05": 70, "E06": 90,
        "E07": 85, "E08": 80, "E09": 85, "E10": 80, 
        "E11": 85,  
        "E12": 80, "E13": 85, "E14": 75, "E15": 80, "E16": 85, "E17": 85, "E18": 80
    }

    historico_producao = []

    # CORREÇÃO DA LÓGICA LEAN: A moto passa estritamente de uma estação para a outra em fila sequencial
    def linha_montagem(env, nome_moto, modelo, estacoes_recursos):
        for estacao, tempo_base in TEMPOS_ESTACOES.items():
            with estacoes_recursos[estacao].request() as req:
                yield req  # Espera a estação anterior liberar a moto
                
                tempo_processo = max(10, random.normalvariate(tempo_base, 2))
                status_qualidade = "Aprovado"
                tempo_ocioso_setup = 0
                
                if estacao == "E11":
                    # Evento de setup de modelo (ocorre a cada troca de mix de produto)
                    if random.random() < 0.15:  
                        tempo_ocioso_setup = max(10, random.normalvariate(TEMPO_SETUP_MODELO, 5))
                        yield env.timeout(tempo_ocioso_setup)
                    if random.random() < (PPM_DEFEITO / 1000000):
                        status_qualidade = "Defeito_Painel"
                
                yield env.timeout(tempo_processo)
                historico_producao.append({
                    "horario_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "moto_id": nome_moto,
                    "modelo": modelo,
                    "estacao": estacao,
                    "tempo_espera": round(tempo_ocioso_setup, 2) if tempo_ocioso_setup > 0 else round(random.uniform(0.1, 1.5), 2),
                    "tempo_processo": round(tempo_processo, 2),
                    "Status_Qualidade": status_qualidade
                })

    def gerador_motos(env, estacoes_recursos):
        moto_id = 1
        modelos_mix = ["XTZ 150", "FACTOR 150", "CROSSER 150", "LANDER 250"]
        while True:
            modelo = random.choice(modelos_mix)
            env.process(linha_montagem(env, f"{moto_id:03d}", modelo, estacoes_recursos))
            moto_id += 1
            # Força o intervalo de entrada sincronizado com o Takt Time da fábrica
            yield env.timeout(TAKT_TIME_META)

    with st.spinner("🏃 Executando simulação realista da linha de produção..."):
        env = simpy.Environment()
        # Cada posto só aceita 1 moto por vez (capacidade = 1)
        estacoes_recursos = {estacao: simpy.Resource(env, capacity=1) for estacao in TEMPOS_ESTACOES.keys()}
        env.process(gerador_motos(env, estacoes_recursos))
        env.run(until=TEMPO_SIMULACAO)

    df_resultado = pd.DataFrame(historico_producao)
    
    # Contabiliza como finalizada apenas a moto que passou com sucesso pela ÚLTIMA estação (E18)
    if not df_resultado.empty:
        motos_calc = int(df_resultado[df_resultado['estacao'] == 'E18']['moto_id'].nunique())
        defeitos_calc = int(len(df_resultado[df_resultado['Status_Qualidade'] == 'Defeito_Painel']))
    else:
        motos_calc = 0
        defeitos_calc = 0

    # =========================================================
    # 🏃 CÁLCULO DO DESLOCAMENTO DO MONTADOR e AUDITORIA 5S
    # =========================================================
    fator_proporcional = (PPM_DEFEITO - 17500) / (35000 - 17500)
    fator_proporcional = max(0.0, min(1.0, fator_proporcional))

    deslocamento_base = 30.0 + (20.0 * fator_proporcional)
    deslocamento_total_calc = round(deslocamento_base + random.uniform(-1.0, 1.0), 1)
    variacao_deslocamento = deslocamento_total_calc - 50.0
    porcentagem_reducao_deslocamento = (variacao_deslocamento / 50.0) * 100

    nota_5s_base = 85.0 - (55.0 * fator_proporcional)
    nota_5s_calc = int(nota_5s_base + random.randint(-2, 2))
    nota_5s_calc = max(0, min(100, nota_5s_calc))
    variacao_5s = nota_5s_calc - 30
    porcentagem_ganho_5s = (variacao_5s / 30.0) * 100

    # Armazena no estado da sessão
    st.session_state['simulacao_rodada'] = True
    st.session_state['df_resultado'] = df_resultado
    st.session_state['motos_calc'] = motos_calc
    st.session_state['defeitos_calc'] = defeitos_calc
    st.session_state['deslocamento_total_calc'] = deslocamento_total_calc
    st.session_state['variacao_deslocamento'] = variacao_deslocamento
    st.session_state['porcentagem_reducao_deslocamento'] = porcentagem_reducao_deslocamento
    st.session_state['nota_5s_calc'] = nota_5s_calc
    st.session_state['variacao_5s'] = variacao_5s
    st.session_state['porcentagem_ganho_5s'] = porcentagem_ganho_5s

    # --- ENVIANDO OS DADOS REAIS CALCULADOS VIA MQTT ---
    try:
        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        client.connect("localhost", 1883, 60)
        client.loop_start()

        payload = {
            "grupo": "Grupo 8 - Motocicletas (PIM)",
            "motos_finalizadas": motos_calc,  
            "defeitos": defeitos_calc,
            "deslocamento_total_m": deslocamento_total_calc,
            "nota_5s": nota_5s_calc
        }

        client.publish("ufam/digitaltwin/producao", json.dumps(payload))
        st.sidebar.success("📡 Dados enviados ao MQTT!")
        
        time.sleep(0.5)
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        st.sidebar.error(f"Broker MQTT desconectado: {e}")

# =========================================================
# RENDERIZAÇÃO DA TELA (PERSISTENTE E COMBINADA COM O BANCO DE DADOS)
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

    # Meta proporcional baseada no tempo inserido
    meta_proporcional = int((TEMPO_SIMULACAO / 28800) * 300)
    meta_proporcional = max(1, meta_proporcional)

    if motos_calc > 0:
        taxa_qualidade = ((motos_calc - defeitos_calc) / motos_calc) * 100
        taxa_defeito_pct = (defeitos_calc / motos_calc) * 100
    else:
        taxa_qualidade = 100.0
        taxa_defeito_pct = 0.0

    # Grid de KPIs - Linha 1
    linha1_col1, linha1_col2, linha1_col3 = st.columns(3)
    
    with linha1_col1:
        ganho_motos = motos_calc - meta_proporcional
        st.metric(
            label="Motos Finalizadas (Saída E18)", 
            value=f"{motos_calc}",
            delta=f"{ganho_motos:+} u. vs Meta do Período ({meta_proporcional})" if ganho_motos != 0 else "Na meta prevista"
        )
        
    with linha1_col2:
        st.metric(label="Defeito de montagem (E11)", value=f"{defeitos_calc}")

    with linha1_col3:
        variacao_defeito_pct = taxa_defeito_pct - 3.5
        st.metric(
            label="Taxa de Defeito (%)",
            value=f"{taxa_defeito_pct:.2f}%",
            delta=f"{variacao_defeito_pct:+.2f}% vs Inicial" if variacao_defeito_pct != 0 else "Sem alteração",
            delta_color="inverse"
        )
        
    st.write("") 
    # Grid de KPIs - Linha 2
    linha2_col1, linha2_col2, linha2_col3 = st.columns(3)

    with linha2_col1:
        reducao_setup = TEMPO_SETUP_MODELO - 180
        porcentagem_setup = (reducao_setup / 180) * 100
        st.metric(
            label="Tempo de Troca de Modelo", 
            value=f"{TEMPO_SETUP_MODELO} s",
            delta=f"{reducao_setup} s ({porcentagem_setup:.0f}%)" if reducao_setup != 0 else "Sem alteração",
            delta_color="inverse"
        )

    with linha2_col2:
        st.metric(
            label="Deslocamento do Montador",
            value=f"{deslocamento_total_calc:.1f} m",
            delta=f"{variacao_deslocamento:+.1f} m ({porcentagem_reducao_deslocamento:.0f}%) vs Inicial" if variacao_deslocamento != 0 else "Baseline",
            delta_color="inverse"
        )
        
    with linha2_col3:
        st.metric(
            label="Auditoria 5S", 
            value=f"{nota_5s_calc} / 100",
            delta=f"{variacao_5s:+} pontos ({porcentagem_ganho_5s:+.0f}%) vs Inicial" if variacao_5s != 0 else "Baseline",
            delta_color="normal"
        )

    # Bloco dinâmico de sucesso corrigido
    custo_inicial_slide = 50000.00
    economia_atual = custo_inicial_slide - (defeitos_calc * 1428.57)
    
    st.success(
        f"**IMPACTO DA MELHORIA NESTA RODADA:**  \n"
        f"• O Poka-Yoke trouxe uma economia R$ {max(0.0, economia_atual):,.2f} em custos por turno!"
    )

    # =========================================================
    # 📊 SEÇÃO DO GRÁFICO DE BALANCEAMENTO DE LINHA
    # =========================================================
    st.markdown("---")
    st.markdown("#### 📊 Gráfico de Balanceamento de Linha (Tempo Médio por Estação)")

    if not df_resultado.empty:
        df_balanceamento = df_resultado.groupby('estacao')['tempo_processo'].mean().reset_index()
    else:
        df_balanceamento = pd.DataFrame(columns=['estacao', 'tempo_processo'])

    df_balanceamento['Cor'] = df_balanceamento['tempo_processo'].apply(
        lambda x: '#ef553b' if x > float(TAKT_TIME_META) else '#0066cc'
    )

    fig = px.bar(
        df_balanceamento, 
        x='estacao', 
        y='tempo_processo',
        color='Cor',
        color_discrete_map={'#0066cc': '#0066cc', '#ef553b': '#ef553b'},
        labels={'estacao': 'Estação', 'tempo_processo': 'Tempo Médio (s)'}
    )
    fig.update_layout(showlegend=False)
    fig.add_hline(y=float(TAKT_TIME_META), line_dash="dash", line_color="red", annotation_text=f"Meta Takt Time: {TAKT_TIME_META}s")
    st.plotly_chart(fig, use_container_width=True)
    st.info(f"💡 Linha de Meta Teórica (Takt Time): {TAKT_TIME_META} segundos. Estações em vermelho ultrapassaram o tempo limite!")

    # =========================================================
    # 🗄️ SEÇÃO INSPEÇÃO DO BANCO DE DADOS DA SIMULAÇÃO
    # =========================================================
    st.markdown("---")
    st.markdown("#### 🗄️ Banco de Dados Local (Histórico Completo de Eventos da Linha)")
    
    tab1, tab2 = st.tabs(["📋 Registros Brutos do Banco", "🏍️ Produção por Modelo de Moto"])
    
    with tab1:
        st.write("Abaixo estão listadas as linhas de logs capturadas em tempo real durante a simulação:")
        st.dataframe(df_resultado, use_container_width=True, height=300)
        
    with tab2:
        st.write("Agrupamento consolidado das motocicletas processadas por modelo:")
        if not df_resultado.empty:
            df_modelos = df_resultado.groupby(['modelo', 'Status_Qualidade']).size().unstack(fill_value=0).reset_index()
            st.dataframe(df_modelos, use_container_width=True)
        else:
            st.write("Nenhum dado para agrupar.")

else:
    st.info("👋 Bem-vindo! Configure as variáveis na barra lateral à esquerda e clique em **🚀 Rodar Simulação e Enviar Dados** para carregar os indicadores, o gráfico e a tabela do banco de dados.")
