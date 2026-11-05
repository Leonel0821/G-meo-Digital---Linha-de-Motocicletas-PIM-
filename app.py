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
TEMPO_SIMULACAO = st.sidebar.number_input("Tempo de Simulação (segundos)", value=28800)
TAKT_TIME_META = st.sidebar.number_input("Meta Takt Time (segundos)", value=90)
PPM_DEFEITO = st.sidebar.number_input("PPM de Defeito (Estação 11)", value=35000)
TEMPO_SETUP_MODELO = st.sidebar.number_input("Tempo de troca de modelo (segundos)", value=180)

# Botão para disparar a simulação e atualizar o Dashboard
if st.sidebar.button("🚀 Rodar Simulação e Enviar Dados"):
    
    # Tempos médios de processamento das 18 estações
    TEMPOS_ESTACOES = {
        "E01": 75, "E02": 85, "E03": 80, "E04": 85, "E05": 70, "E06": 90,
        "E07": 85, "E08": 80, "E09": 85, "E10": 80, 
        "E11": 85,  # Ajustado para ficar igual ao nome do gráfico 'E11'
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
                
                if estacao == "E11":
                    if random.random() < 0.20:  
                        tempo_ocioso_setup = max(10, random.normalvariate(TEMPO_SETUP_MODELO, 10))
                        yield env.timeout(tempo_ocioso_setup)
                    if random.random() < (PPM_DEFEITO / 1000000):
                        status_qualidade = "Defeito_Painel"
                
                yield env.timeout(tempo_processo)
                historico_producao.append({
                    "horario_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "moto_id": nome_moto,
                    "modelo": modelo,
                    "estacao": estacao,
                    "tempo_espera": round(tempo_ocioso_setup, 2) if tempo_ocioso_setup > 0 else round(random.uniform(0.1, 2.0), 2),
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
            yield env.timeout(TAKT_TIME_META)

    st.write("🏃 Executando simulação...")
    env = simpy.Environment()
    estacoes_recursos = {estacao: simpy.Resource(env, capacity=1) for estacao in TEMPOS_ESTACOES.keys()}
    env.process(gerador_motos(env, estacoes_recursos))
    env.run(until=TEMPO_SIMULACAO)

    df_resultado = pd.DataFrame(historico_producao)
    
    motos_calc = int(df_resultado['moto_id'].nunique())
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

    # =========================================================
    # 📊 EXIBIÇÃO DOS RESULTADOS COM OS INDICADORES DE MELHORIA (DELTAS)
    # =========================================================
    st.markdown("---")
    st.markdown("## Gêmeo Digital - Grupo 8 - Cenário 09 - Linha de Motocicletas (PIM)")
    st.markdown("#### Monitoramento em Tempo Real - Linha de Montagem de Motocicletas")
    st.markdown("---")

    # Cálculo da Taxa de Qualidade Global
    if motos_calc > 0:
        taxa_qualidade = ((motos_calc - defeitos_calc) / motos_calc) * 100
    else:
        taxa_qualidade = 100.0

    # Layout de 4 colunas para mostrar os resultados e os deltas de melhoria comparados ao passado (Baseline)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Compara a produção final com a capacidade teórica de 300 motos do slide
        ganho_motos = motos_calc - 300
        st.metric(
            label="Motos Finalizadas", 
            value=f"{motos_calc}",
            delta=f"{ganho_motos:+} u. vs Meta" if ganho_motos != 0 else "No ritmo previsto"
        )
        
    with col2:
        # Mostra o resultado atual dos defeitos calculados na simulação
        st.metric(label="Defeito de montagem (E11)", value=f"{defeitos_calc}")
        
    with col3:
        # Compara o tempo de troca de modelo inserido com o cenário inicial antigo de 180 segundos
        reducao_setup = TEMPO_SETUP_MODELO - 180
        porcentagem_setup = (reducao_setup / 180) * 100
        st.metric(
            label="Tempo de Troca de Modelo", 
            value=f"{TEMPO_SETUP_MODELO} ",
            delta=f"{reducao_setup} s ({porcentagem_setup:.0f}%)" if reducao_setup != 0 else "Sem alteração",
            delta_color="inverse" # Fica verde se o tempo de troca diminuir
        )
        
    with col4:
        # Mostra o ganho de qualidade em relação ao cenário inicial histórico (que era de 96.5% devido aos defeitos antigos)
        melhoria_qualidade = taxa_qualidade - 96.5
        st.metric(
            label="Taxa de Qualidade Global", 
            value=f"{taxa_qualidade:.1f}%",
            delta=f"{melhoria_qualidade:+.1f}% de Ganho" if melhoria_qualidade != 0 else None
        )

    # Bloco dinâmico de sucesso corrigido com cálculo baseado nos dados de custos reais do slide de vocês
    custo_inicial_slide = 50000.00
    economia_atual = custo_inicial_slide - (defeitos_calc * 1428.57)
    
    if economia_atual > 0:
        st.success(
            f"**IMPACTO DA MELHORIA NESTA RODADA:**  \n"
            f"• O Poka-Yoke trouxe uma econômia R$ {max(0.0, economia_atual):,.2f}** em custos por turno!"
        )

    st.markdown("---")
    st.markdown("#### 📊 Gráfico de Balanceamento de Linha (Tempo Médio por Estação)")

    # Agrupar os dados por estação para tirar a média de processamento
    df_balanceamento = df_resultado.groupby('estacao')['tempo_processo'].mean().reset_index()

    # Criação do gráfico de barras verticais azuis
    fig = px.bar(
        df_balanceamento, 
        x='estacao', 
        y='tempo_processo',
        labels={'estacao': 'estacao', 'tempo_processo': 'tempo_processo'},
        color_discrete_sequence=['#0066cc']  # Azul real igual ao do slide
    )
    
    # Linha Vermelha tracejada da Meta Teórica (Takt Time configurado)
    fig.add_hline(y=float(TAKT_TIME_META), line_dash="dash", line_color="red", annotation_text=f"Meta: {TAKT_TIME_META}s")
    st.plotly_chart(fig, use_container_width=True)

    st.info(f"💡 Linha de Meta Teórica (Takt Time): {TAKT_TIME_META} segundos. Estações que ultrapassarem geram gargalo na linha!")

    # Histórico temporal completo do banco estruturado igualzinho ao seu print
    st.markdown("---")
    with st.expander("🔍 Visualizar Histórico Temporal Completo (Banco de Dados)"):
        # Filtrar as colunas e ordenar para ficar na ordem exata do banco do print
        df_visualizacao = df_resultado[['horario_registro', 'moto_id', 'modelo', 'estacao', 'tempo_espera', 'tempo_processo']]
        st.dataframe(df_visualizacao.tail(100), use_container_width=True)
import streamlit as st
import time

# =========================================================
# INICIALIZAÇÃO DO ESTADO DA ESTAÇÃO 11 (POKA-YOKE CONTROLE MANUAL)
# =========================================================
if 'etapa_poka' not in st.session_state:
    st.session_state['etapa_poka'] = 0  # 0: Vazio, 1: Moto Escolhida, 2: Painel Coletado/Comparado
    st.session_state['modelo_selecionado'] = ""
    st.session_state['qr_moto_lido'] = ""
    st.session_state['caixa_iluminada'] = "⚪ Nenhuma"
    st.session_state['qr_painel_lido'] = ""
    st.session_state['status_esteira_11'] = "⚪ Aguardando Inicialização"
    st.session_state['lampada_vermelha'] = "⚫ Apagada"

st.markdown("---")
st.markdown("### 🔍 Protótipo Prático da Estação 11 - Controle do Poka-Yoke (Apresentação)")
st.markdown("*Use os botões abaixo para simular exatamente o fluxo operacional do chão de fábrica diante da banca.*")

# =========================================================
# PASSO 1: BOTÕES DE SELEÇÃO DO MODELO DE MOTO
# =========================================================
st.markdown("#### **Passo 1: Selecione o modelo de moto que está entrando na Estação 11**")
col_b1, col_b2, col_b3, col_reset = st.columns(4)

with col_b1:
    if st.button("🏍️ Injetar XTZ 150", use_container_width=True):
        st.session_state['modelo_selecionado'] = "XTZ 150"
        st.session_state['qr_moto_lido'] = "MOTO_QR_XTZ150_SN542"
        st.session_state['caixa_iluminada'] = "🟡 CAIXA 1 (Etiqueta Cinza - XTZ 150)"
        st.session_state['etapa_poka'] = 1
        st.session_state['status_esteira_11'] = "🟡 Moto posicionada. Aguardando leitura do painel..."
        st.session_state['lampada_vermelha'] = "⚫ Apagada"

with col_b2:
    if st.button("🏍️ Injetar FACTOR 150", use_container_width=True):
        st.session_state['modelo_selecionado'] = "FACTOR 150"
        st.session_state['qr_moto_lido'] = "MOTO_QR_FACTOR150_SN911"
        st.session_state['caixa_iluminada'] = "🟡 CAIXA 2 (Etiqueta Cinza - FACTOR 150)"
        st.session_state['etapa_poka'] = 1
        st.session_state['status_esteira_11'] = "🟡 Moto posicionada. Aguardando leitura do painel..."
        st.session_state['lampada_vermelha'] = "⚫ Apagada"

with col_b3:
    if st.button("🏍️ Injetar LANDER 250", use_container_width=True):
        st.session_state['modelo_selecionado'] = "LANDER 250"
        st.session_state['qr_moto_lido'] = "MOTO_QR_LANDER250_SN314"
        st.session_state['caixa_iluminada'] = "🟡 CAIXA 3 (Etiqueta Cinza - LANDER 250)"
        st.session_state['etapa_poka'] = 1
        st.session_state['status_esteira_11'] = "🟡 Moto posicionada. Aguardando leitura do painel..."
        st.session_state['lampada_vermelha'] = "⚫ Apagada"

with col_reset:
    if st.button("🔄 Resetar Posto 11", type="secondary", use_container_width=True):
        st.session_state['etapa_poka'] = 0
        st.session_state['modelo_selecionado'] = ""
        st.session_state['qr_moto_lido'] = ""
        st.session_state['caixa_iluminada'] = "⚪ Nenhuma"
        st.session_state['qr_painel_lido'] = ""
        st.session_state['status_esteira_11'] = "⚪ Aguardando Inicialização"
        st.session_state['lampada_vermelha'] = "⚫ Apagada"

# =========================================================
# PASSO 2: SIMULAÇÃO DA RETIRADA DO PAINEL (ERRO OU ACERTO)
# =========================================================
if st.session_state['etapa_poka'] >= 1:
    st.markdown("---")
    st.markdown("#### **Passo 2: Simular a coleta e montagem do Kit de Painel**")
    st.write(f"ℹ️ *O sistema acendeu a luz indicativa na:* **{st.session_state['caixa_iluminada']}**")
    
    col_ok, col_erro = st.columns(2)
    
    with col_ok:
        if st.button("✅ Operador pegou o Painel CORRETO", type="primary", use_container_width=True):
            mod = st.session_state['modelo_selecionado'].replace(" ", "")
            st.session_state['qr_painel_lido'] = f"PAINEL_QR_{mod}_LOTE32"
            st.session_state['etapa_poka'] = 2
            
    with col_erro:
        if st.button("❌ Operador pegou um Painel INCORRETO (Simular Defeito)", type="secondary", use_container_width=True):
            # Força um modelo errado para gerar o travamento e a lâmpada vermelha
            errado = "LANDER250" if st.session_state['modelo_selecionado'] != "LANDER 250" else "XTZ150"
            st.session_state['qr_painel_lido'] = f"PAINEL_QR_{errado}_LOTE88"
            st.session_state['etapa_poka'] = 2

# =========================================================
# PASSO 3: SINALIZADORES VISUAIS EM TEMPO REAL
# =========================================================
if st.session_state['etapa_poka'] == 2:
    st.markdown("---")
    st.markdown("#### **🖥️ Monitoramento dos Sinalizadores da Estação 11**")
    
    # Processamento lógico da única câmera comparando os dados lidos
    moto_val = st.session_state['qr_moto_lido'].split("_")[2]
    painel_val = st.session_state['qr_painel_lido'].split("_")[2]
    
    sucesso_poka_yoke = (moto_val == painel_val)
    
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.metric(
            label="📷 Sinalizador: Leitura da Moto", 
            value="🟢 LEITURA OK" if st.session_state['qr_moto_lido'] else "⚪ Vazio",
            help="Indica se a câmera única escaneou com sucesso o QR Code fixado no chassi."
        )
        st.caption(f"`{st.session_state['qr_moto_lido']}`")
        
    with c2:
        # Seletor dinâmico simulando a lâmpada física da caixa acesa
        st.metric(
            label="💡 Lâmpada do Painel Exato", 
            value="🟢 ACESA" if st.session_state['etapa_poka'] >= 1 else "⚫ APAGADA",
            delta="Apoio Visual" if st.session_state['etapa_poka'] >= 1 else None
        )
        st.caption(f"Alvo: {st.session_state['caixa_iluminada']}")
        
    with c3:
        st.metric(
            label="📷 Sinalizador: Leitura do Kit", 
            value="🟢 LEITURA OK" if st.session_state['qr_painel_lido'] else "⚪ Vazio",
            help="Indica se a câmera única escaneou com sucesso o QR Code do componente instalado."
        )
        st.caption(f"`{st.session_state['qr_painel_lido']}`")
        
    with c4:
        if sucesso_poka_yoke:
            st.session_state['status_esteira_11'] = "🟢 EM MOVIMENTO (Ciclo de 90s Liberado)"
            st.session_state['lampada_vermelha'] = "⚫ Apagada"
            st.metric(label="🧠 Validação das Leituras", value="✅ COMPATÍVEL")
            
            # Soma dinamicamente ao painel geral do Streamlit se as variáveis existirem
            if 'motos_calc' in st.session_state and st.button("⏩ Confirmar Saída da Moto"):
                st.session_state['motos_calc'] += 1
                st.rerun()
        else:
            st.session_state['status_esteira_11'] = "🚨 PARADA DE EMERGÊNCIA (Bloqueada)"
            st.session_state['lampada_vermelha'] = "🔴 ALERTA: KIT INCORRETO!"
            st.metric(label="🧠 Validação das Leituras", value="❌ INCOMPATÍVEL", delta="- Erro de Mix", delta_color="inverse")
            
            if 'defeitos_calc' in st.session_state and st.button("🚨 Registrar Defeito e Retrabalhar"):
                st.session_state['defeitos_calc'] += 1
                st.rerun()

    # Exibição final dos alarmes e atuadores físicos (Lâmpada vermelha e Esteira)
    st.markdown("##### **Atuadores Físicos da Linha**")
    col_est, col_l_vermelha = st.columns(2)
    
    with col_est:
        if "🟢" in st.session_state['status_esteira_11']:
            st.success(f"⚙️ **Status da Esteira:**\n### {st.session_state['status_esteira_11']}")
        else:
            st.error(f"⚙️ **Status da Esteira:**\n### {st.session_state['status_esteira_11']}")
            
    with col_l_vermelha:
        if "🔴" in st.session_state['lampada_vermelha']:
            st.error(f"🚨 **Torre de Sinalização (Luz Vermelha):**\n## {st.session_state['lampada_vermelha']}")
        else:
            st.info(f"🚨 **Torre de Sinalização (Luz Vermelha):**\n### {st.session_state['lampada_vermelha']}")

