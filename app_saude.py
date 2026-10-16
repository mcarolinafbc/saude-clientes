import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Configuração da Página
st.set_page_config(page_title="Saúde dos Clientes", page_icon="🏥", layout="wide")

st.title("🏥 Saúde dos Clientes e Contratos")
st.markdown("Monitorização de consumos, previsão de gastos e alertas de esgotamento prematuro.")

# --- BARRA LATERAL ---
st.sidebar.header("📁 Base de Dados")
st.sidebar.markdown("Faça upload do Excel (Lê apenas as abas 1 e 2)")
uploaded_file = st.sidebar.file_uploader("Upload do ficheiro (Excel)", type=["xlsx"])

@st.cache_data
def load_data(file):
    xls = pd.ExcelFile(file)
    df_cont = pd.read_excel(xls, sheet_name='1_Contratos')
    df_cons = pd.read_excel(xls, sheet_name='2_Consumo_Mensal')
    return df_cont, df_cons

if uploaded_file is not None:
    df_cont, df_cons = load_data(uploaded_file)
    
    # ---------------------------------------------------
    # 1. MOTOR DE CÁLCULO E FORECAST
    # ---------------------------------------------------
    historico = df_cons.iloc[:, 2:12] # Ajustar consoante os meses preenchidos
    ultimos_3_meses = historico.iloc[:, -3:]
    df_cons['Forecast_Mensal_Dias'] = ultimos_3_meses.mean(axis=1)
    
    df_cons['Total_Ja_Gasto'] = historico.sum(axis=1, numeric_only=True)
    df_master = pd.merge(df_cont, df_cons[['Cliente', 'Nome_do_Servico', 'Total_Ja_Gasto', 'Forecast_Mensal_Dias']], 
                         on=['Cliente', 'Nome_do_Servico'])
                         
    df_master['Saldo_Atual'] = df_master['Total_Dias_Contratados'] - df_master['Total_Ja_Gasto']
    df_master['Saldo_Apos_Prox_Mes'] = df_master['Saldo_Atual'] - df_master['Forecast_Mensal_Dias']
    
    # Converter datas para calcular riscos
    hoje = pd.to_datetime('today')
    df_master['Data_Fim_Calc'] = pd.to_datetime(df_master['Data_Fim'], errors='coerce')
    
    # Cálculos de Esgotamento
    df_master['Meses_Para_Fim_Prazo'] = ((df_master['Data_Fim_Calc'].dt.year - hoje.year) * 12 + 
                                         (df_master['Data_Fim_Calc'].dt.month - hoje.month))
                                         
    # Se o forecast for 0, colocamos um valor alto seguro, senão calculamos quantos meses dura o saldo
    df_master['Meses_Para_Fim_Saldo'] = df_master.apply(
        lambda x: x['Saldo_Atual'] / x['Forecast_Mensal_Dias'] if x['Forecast_Mensal_Dias'] > 0 else 999, axis=1
    )
    
    # ---------------------------------------------------
    # 2. INTERFACE VISUAL - KPIs DE TOPO
    # ---------------------------------------------------
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Contratos Ativos", len(df_master))
    with col2:
        st.metric("Procura Esperada (Próx. Mês)", f"{df_master['Forecast_Mensal_Dias'].sum():.1f} dias")
    with col3:
        st.metric("Dias em Saldo (Global)", f"{df_master['Saldo_Atual'].sum():.1f} dias")
        
    # ---------------------------------------------------
    # 3. MOTOR DE ALERTAS INTELIGENTES
    # ---------------------------------------------------
    st.markdown("### 🚨 Centro de Alertas")
    teve_alerta = False
    
    for idx, row in df_master.iterrows():
        # Alerta 1: Vai esgotar o saldo antes do fim do contrato
        if row['Meses_Para_Fim_Saldo'] < row['Meses_Para_Fim_Prazo'] and row['Meses_Para_Fim_Saldo'] > 0:
            st.error(f"**Risco Crítico - {row['Cliente']} ({row['Nome_do_Servico']}):** O ritmo de consumo é muito alto! O contrato termina em **{int(row['Meses_Para_Fim_Prazo'])} meses**, mas os dias vão esgotar em apenas **{row['Meses_Para_Fim_Saldo']:.1f} meses**.")
            teve_alerta = True
            
        # Alerta 2: O contrato termina em breve (< 3 meses)
        elif 0 < row['Meses_Para_Fim_Prazo'] <= 3:
            st.warning(f"**Aviso de Prazo - {row['Cliente']} ({row['Nome_do_Servico']}):** O contrato aproxima-se do fim. Termina em **{int(row['Meses_Para_Fim_Prazo'])} meses**.")
            teve_alerta = True
            
        # Alerta 3: O saldo atual é muito baixo (< 10 dias)
        if row['Saldo_Atual'] <= 10:
            st.warning(f"**Saldo Baixo - {row['Cliente']} ({row['Nome_do_Servico']}):** Restam apenas **{row['Saldo_Atual']:.1f} dias** de saldo.")
            teve_alerta = True

    if not teve_alerta:
        st.success("✅ Todos os clientes apresentam saldo e prazos saudáveis.")
        
    st.divider()

    # ---------------------------------------------------
    # 4. GRÁFICOS VISUAIS
    # ---------------------------------------------------
    colA, colB = st.columns(2)
    
    with colA:
        st.markdown("#### Para onde vai o nosso esforço?")
        fig_donut = px.pie(df_master, values='Forecast_Mensal_Dias', names='Cliente', hole=0.4,
                           title="Expected Delivery por Cliente (Próximo Mês)")
        fig_donut.update_traces(textposition='inside', textinfo='percent+label')
        fig_donut.update_layout(showlegend=False)
        st.plotly_chart(fig_donut, use_container_width=True)
        
    with colB:
        st.markdown("#### Estado Financeiro dos Contratos (Dias)")
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(x=df_master['Nome_do_Servico'], y=df_master['Total_Ja_Gasto'], name='Gasto até agora', marker_color='#E24C4F'))
        fig_bar.add_trace(go.Bar(x=df_master['Nome_do_Servico'], y=df_master['Saldo_Atual'], name='Saldo Disponível', marker_color='#1F4E78'))
        fig_bar.update_layout(barmode='stack', title="Gasto vs Saldo (Por Serviço)", xaxis_title="Serviço", yaxis_title="Dias")
        st.plotly_chart(fig_bar, use_container_width=True)

    # ---------------------------------------------------
    # 5. TABELA DE DETALHE
    # ---------------------------------------------------
    st.markdown("### 📋 Visão Detalhada")
    cols_to_show = ['Cliente', 'Nome_do_Servico', 'Data_Fim', 'Total_Dias_Contratados', 'Total_Ja_Gasto', 'Saldo_Atual', 'Forecast_Mensal_Dias', 'Meses_Para_Fim_Saldo']
    
    # Formatação limpa para a tabela
    df_show = df_master[cols_to_show].copy()
    df_show = df_show.rename(columns={'Meses_Para_Fim_Saldo': 'Meses (Esperança de Vida)'})
    
    st.dataframe(df_show.style.format({
        'Total_Ja_Gasto': "{:.1f}", 
        'Saldo_Atual': "{:.1f}", 
        'Forecast_Mensal_Dias': "{:.1f}",
        'Meses (Esperança de Vida)': "{:.1f}"
    }), use_container_width=True)

else:
    st.info("Por favor, faça upload do ficheiro Excel na barra lateral.")
