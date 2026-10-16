import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np

# Configuração da Página
st.set_page_config(page_title="Saúde dos Clientes", page_icon="🏥", layout="wide")

st.title("🏥 Saúde dos Clientes e Contratos")
st.markdown("Monitorização de consumos, previsão de gastos e alertas de desvio de contrato.")

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
    # 1. MOTOR DE CÁLCULO (IDEAL VS REAL)
    # ---------------------------------------------------
    # Previsão Real (Histórico)
    historico = df_cons.iloc[:, 2:12] # Ajustar consoante as colunas de meses reais
    ultimos_3_meses = historico.iloc[:, -3:]
    df_cons['Consumo_Previsto_Mensal'] = ultimos_3_meses.mean(axis=1)
    df_cons['Total_Ja_Gasto'] = historico.sum(axis=1, numeric_only=True)
    
    # Juntar Dados
    df_master = pd.merge(df_cont, df_cons[['Cliente', 'Nome_do_Servico', 'Total_Ja_Gasto', 'Consumo_Previsto_Mensal']], 
                         on=['Cliente', 'Nome_do_Servico'])
                         
    df_master['Saldo_Atual'] = df_master['Total_Dias_Contratados'] - df_master['Total_Ja_Gasto']
    
    # Converter Datas
    hoje = pd.to_datetime('today')
    df_master['Data_Fim_Calc'] = pd.to_datetime(df_master['Data_Fim'], errors='coerce')
    
    # Se existir coluna Data_Inicio, calcular Consumo Ideal "By the Book"
    if 'Data_Inicio' in df_master.columns:
        df_master['Data_Inicio_Calc'] = pd.to_datetime(df_master['Data_Inicio'], errors='coerce')
        df_master['Meses_Contrato_Total'] = ((df_master['Data_Fim_Calc'].dt.year - df_master['Data_Inicio_Calc'].dt.year) * 12 + 
                                             (df_master['Data_Fim_Calc'].dt.month - df_master['Data_Inicio_Calc'].dt.month))
        # Evitar divisão por zero se datas forem no mesmo mês
        df_master['Meses_Contrato_Total'] = df_master['Meses_Contrato_Total'].replace(0, 1)
    else:
        # Fallback de segurança se a coluna não existir (assume 12 meses)
        df_master['Meses_Contrato_Total'] = 12 
        
    df_master['Consumo_Ideal_Mensal'] = df_master['Total_Dias_Contratados'] / df_master['Meses_Contrato_Total']
    
    # Meses Restantes (Prazo vs Saldo)
    df_master['Meses_Para_Fim_Prazo'] = ((df_master['Data_Fim_Calc'].dt.year - hoje.year) * 12 + 
                                         (df_master['Data_Fim_Calc'].dt.month - hoje.month))
                                         
    df_master['Meses_Para_Fim_Saldo'] = df_master.apply(
        lambda x: x['Saldo_Atual'] / x['Consumo_Previsto_Mensal'] if x['Consumo_Previsto_Mensal'] > 0 else 999, axis=1
    )
    
    # ---------------------------------------------------
    # 2. INTERFACE VISUAL - KPIs DE TOPO
    # ---------------------------------------------------
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Contratos Ativos", len(df_master))
    with col2:
        st.metric("Consumo Previsto (Próx. Mês)", f"{df_master['Consumo_Previsto_Mensal'].sum():.1f} dias")
    with col3:
        st.metric("Dias em Saldo (Global)", f"{df_master['Saldo_Atual'].sum():.1f} dias")
        
    # ---------------------------------------------------
    # 3. MOTOR DE ALERTAS INTELIGENTES
    # ---------------------------------------------------
    st.markdown("### 🚨 Centro de Alertas")
    teve_alerta = False
    
    for idx, row in df_master.iterrows():
        if row['Meses_Para_Fim_Saldo'] < row['Meses_Para_Fim_Prazo'] and row['Meses_Para_Fim_Saldo'] > 0:
            st.error(f"**Risco Crítico - {row['Cliente']} ({row['Nome_do_Servico']}):** Consumo real ({row['Consumo_Previsto_Mensal']:.1f} dias/mês) acima do ideal ({row['Consumo_Ideal_Mensal']:.1f} dias/mês). O saldo esgotará **antes do fim do contrato**.")
            teve_alerta = True
        elif 0 < row['Meses_Para_Fim_Prazo'] <= 3:
            st.warning(f"**Aviso de Prazo - {row['Cliente']} ({row['Nome_do_Servico']}):** O contrato termina em **{int(row['Meses_Para_Fim_Prazo'])} meses**.")
            teve_alerta = True
        if row['Saldo_Atual'] <= 10:
            st.warning(f"**Saldo Baixo - {row['Cliente']} ({row['Nome_do_Servico']}):** Restam apenas **{row['Saldo_Atual']:.1f} dias**.")
            teve_alerta = True

    if not teve_alerta:
        st.success("✅ Todos os clientes apresentam saldo e ritmos de consumo saudáveis.")
        
    st.divider()

    # ---------------------------------------------------
    # 4. GRÁFICOS VISUAIS (IDEAL VS REAL)
    # ---------------------------------------------------
    st.markdown("#### Ritmo de Consumo: Ideal ('By the book') vs Previsão Real")
    
    fig_burn = go.Figure()
    fig_burn.add_trace(go.Bar(
        x=df_master['Cliente'] + " - " + df_master['Nome_do_Servico'], 
        y=df_master['Consumo_Ideal_Mensal'], 
        name='Ideal (Dias/Mês)', 
        marker_color='#1F4E78'
    ))
    fig_burn.add_trace(go.Bar(
        x=df_master['Cliente'] + " - " + df_master['Nome_do_Servico'], 
        y=df_master['Consumo_Previsto_Mensal'], 
        name='Previsão Baseada no Histórico (Dias/Mês)', 
        marker_color='#E24C4F'
    ))
    
    fig_burn.update_layout(barmode='group', xaxis_title="Serviço", yaxis_title="Dias por Mês", legend_title="Tipo de Consumo")
    st.plotly_chart(fig_burn, use_container_width=True)

    # ---------------------------------------------------
    # 5. TABELA DE DETALHE
    # ---------------------------------------------------
    st.markdown("### 📋 Visão Detalhada de Desvios")
    
    # Seleção de colunas para a tabela final
    cols_to_show = ['Cliente', 'Nome_do_Servico', 'Total_Dias_Contratados', 'Saldo_Atual', 'Consumo_Ideal_Mensal', 'Consumo_Previsto_Mensal', 'Meses_Para_Fim_Saldo']
    df_show = df_master[cols_to_show].copy()
    
    # Coluna de Desvio
    df_show['Desvio Mensal (Dias)'] = df_show['Consumo_Previsto_Mensal'] - df_show['Consumo_Ideal_Mensal']
    
    st.dataframe(df_show.style.format({
        'Saldo_Atual': "{:.1f}", 
        'Consumo_Ideal_Mensal': "{:.1f}", 
        'Consumo_Previsto_Mensal': "{:.1f}",
        'Meses_Para_Fim_Saldo': "{:.1f}",
        'Desvio Mensal (Dias)': "{:+.1f}"
    }).map(lambda x: 'color: red' if x > 0 else 'color: green', subset=['Desvio Mensal (Dias)']), 
    use_container_width=True)

else:
    st.info("Por favor, faça upload do ficheiro Excel na barra lateral.")


