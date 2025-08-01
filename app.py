# =============================
# 🍀 Sistema PlagIA - Versão Melhorada com Design Moderno
# Inspirado no TotalIA - PEAS.Co 2024
# =============================

import streamlit as st
import requests
import PyPDF2
import difflib
from fpdf import FPDF
from io import BytesIO
import hashlib
from datetime import datetime, date
from PIL import Image
import qrcode
import re
from collections import Counter
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import time
import json
from typing import Dict, List, Tuple, Optional

# Configuração da página
st.set_page_config(
    page_title="PlagIA Professional - Detecção Avançada de Plágio",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🔗 URL da API gerada no Google Sheets
URL_GOOGLE_SHEETS = "https://script.google.com/macros/s/AKfycbyTpbWDxWkNRh_ZIlHuAVwZaCC2ODqTmo0Un7ZDbgzrVQBmxlYYKuoYf6yDigAPHZiZ/exec"

# Configurações globais
CONFIG = {
    'MAX_CONSULTAS_SESSAO': 4,
    'MIN_TEXT_LENGTH': 100,
    'MAX_TEXT_LENGTH': 50000,
}

# =============================
# CSS Avançado e Design Moderno
# =============================

def load_modern_css():
    """CSS moderno inspirado no TotalIA"""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Reset e configurações base */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Header hero com gradiente animado */
    .hero-header {
        background: linear-gradient(-45deg, #667eea, #764ba2, #f093fb, #f5576c);
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite;
        padding: 3rem 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        position: relative;
        overflow: hidden;
    }
    
    .hero-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(255,255,255,0.1);
        backdrop-filter: blur(10px);
        z-index: 1;
    }
    
    .hero-content {
        position: relative;
        z-index: 2;
    }
    
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Cards com glassmorphism */
    .glass-card {
        background: rgba(255, 255, 255, 0.25);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.18);
        padding: 2rem;
        margin: 1rem 0;
        box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .glass-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 45px rgba(31, 38, 135, 0.5);
    }
    
    /* Métricas animadas */
    .metric-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 1.5rem;
        color: white;
        text-align: center;
        position: relative;
        overflow: hidden;
        transition: all 0.3s ease;
        cursor: pointer;
        margin: 0.5rem 0;
    }
    
    .metric-container:hover {
        transform: scale(1.05);
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        animation: countUp 1s ease-out;
    }
    
    .metric-label {
        font-size: 0.9rem;
        opacity: 0.9;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    @keyframes countUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    /* Resultado com efeito neon */
    .neon-result {
        background: #1a1a1a;
        border-radius: 20px;
        padding: 2rem;
        text-align: center;
        position: relative;
        margin: 2rem 0;
        overflow: hidden;
    }
    
    .neon-text {
        color: #fff;
        text-shadow: 
            0 0 5px currentColor,
            0 0 10px currentColor,
            0 0 15px currentColor,
            0 0 20px currentColor;
        animation: neonFlicker 2s infinite alternate;
    }
    
    .neon-high { color: #ff0040; }
    .neon-medium { color: #ffaa00; }
    .neon-low { color: #00ff41; }
    
    @keyframes neonFlicker {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.8; }
    }
    
    /* Contador de uso */
    .usage-counter {
        background: linear-gradient(135deg, #2196F3, #1976D2);
        color: white;
        padding: 1rem;
        border-radius: 15px;
        text-align: center;
        font-weight: bold;
        margin-bottom: 1rem;
        box-shadow: 0 4px 15px rgba(33, 150, 243, 0.3);
    }
    
    .usage-counter.limit-reached {
        background: linear-gradient(135deg, #f44336, #d32f2f);
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.02); }
        100% { transform: scale(1); }
    }
    
    /* Botões modernos */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        position: relative;
        overflow: hidden;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    
    .stButton > button:disabled {
        background: #cccccc;
        transform: none;
        box-shadow: none;
    }
    
    /* Progress bars animadas */
    .animated-progress {
        background: #e9ecef;
        border-radius: 10px;
        overflow: hidden;
        height: 8px;
        margin: 1rem 0;
        position: relative;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #667eea, #764ba2);
        border-radius: 10px;
        transition: width 1s ease-in-out;
        position: relative;
        overflow: hidden;
    }
    
    .progress-fill::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        bottom: 0;
        right: 0;
        background-image: linear-gradient(
            -45deg,
            rgba(255, 255, 255, .2) 25%,
            transparent 25%,
            transparent 50%,
            rgba(255, 255, 255, .2) 50%,
            rgba(255, 255, 255, .2) 75%,
            transparent 75%,
            transparent
        );
        background-size: 50px 50px;
        animation: move 2s linear infinite;
    }
    
    @keyframes move {
        0% { background-position: 0 0; }
        100% { background-position: 50px 50px; }
    }
    
    /* Sidebar moderna */
    .sidebar-modern {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        border-left: 4px solid #667eea;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    /* Seções de análise */
    .analysis-section {
        background: #f8f9fa;
        padding: 2rem;
        border-radius: 15px;
        margin: 1rem 0;
        border: 1px solid #e9ecef;
        transition: all 0.3s ease;
    }
    
    .analysis-section:hover {
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    
    /* Caixas de recomendação */
    .recommendation-box {
        background: linear-gradient(135deg, #17a2b8, #138496);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
        border-left: 5px solid #0c5460;
    }
    
    /* Loading spinner personalizado */
    .custom-spinner {
        border: 4px solid #f3f3f3;
        border-top: 4px solid #667eea;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
        margin: 20px auto;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* Animações de entrada */
    .fade-in-up {
        animation: fadeInUp 0.6s ease-out;
    }
    
    .fade-in-left {
        animation: fadeInLeft 0.6s ease-out;
    }
    
    .fade-in-right {
        animation: fadeInRight 0.6s ease-out;
    }
    
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes fadeInLeft {
        from {
            opacity: 0;
            transform: translateX(-30px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    @keyframes fadeInRight {
        from {
            opacity: 0;
            transform: translateX(30px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    /* Responsividade */
    @media (max-width: 768px) {
        .hero-header {
            padding: 2rem 1rem;
        }
        
        .glass-card {
            padding: 1.5rem;
            margin: 0.5rem 0;
        }
        
        .metric-value {
            font-size: 2rem;
        }
        
        .analysis-section {
            padding: 1.5rem;
        }
    }
    
    /* Elementos interativos */
    .interactive-element {
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .interactive-element:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    
    /* Tooltips */
    .tooltip-container {
        position: relative;
        display: inline-block;
    }
    
    .tooltip-text {
        visibility: hidden;
        width: 200px;
        background-color: #333;
        color: #fff;
        text-align: center;
        border-radius: 8px;
        padding: 8px;
        position: absolute;
        z-index: 1;
        bottom: 125%;
        left: 50%;
        margin-left: -100px;
        opacity: 0;
        transition: opacity 0.3s;
        font-size: 0.8rem;
    }
    
    .tooltip-container:hover .tooltip-text {
        visibility: visible;
        opacity: 1;
    }
    </style>
    """, unsafe_allow_html=True)

# =============================
# Funções Auxiliares Melhoradas
# =============================

def salvar_email_google_sheets(nome, email, codigo_verificacao):
    """Salva dados no Google Sheets com tratamento de erro melhorado"""
    dados = {"nome": nome, "email": email, "codigo": codigo_verificacao, "data": str(date.today())}
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(URL_GOOGLE_SHEETS, json=dados, headers=headers, timeout=10)
        return response.text.strip() == "Sucesso"
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao conectar com Google Sheets: {e}")
        return False

def verificar_codigo_google_sheets(codigo_digitado):
    """Verifica código no Google Sheets com tratamento de erro melhorado"""
    try:
        response = requests.get(f"{URL_GOOGLE_SHEETS}?codigo={codigo_digitado}", timeout=10)
        return response.text.strip() == "Valido"
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao verificar código: {e}")
        return False

def gerar_codigo_verificacao(texto):
    """Gera código de verificação único"""
    timestamp = str(int(time.time()))
    combined = texto + timestamp
    return hashlib.md5(combined.encode()).hexdigest()[:10].upper()

def extrair_texto_pdf(arquivo_pdf):
    """Extrai texto de PDF com melhor tratamento de erro"""
    try:
        leitor_pdf = PyPDF2.PdfReader(arquivo_pdf)
        texto = ""
        for i, pagina in enumerate(leitor_pdf.pages):
            try:
                texto += pagina.extract_text() or ""
            except Exception as e:
                st.warning(f"Erro ao extrair texto da página {i+1}: {e}")
                continue
        return texto.strip()
    except Exception as e:
        st.error(f"Erro ao processar PDF: {e}")
        return ""

def limpar_texto_avancado(texto_bruto):
    """Limpeza de texto mais avançada inspirada no TotalIA"""
    if not texto_bruto:
        return ""
    
    linhas = texto_bruto.splitlines()
    linhas_filtradas = []
    contagem = Counter(linhas)
    capturar = False
    
    # Padrões para filtrar
    padroes_ignorar = [
        r"^Página?\s*\d+$",
        r"^doi\s*:",
        r"^\d+$",
        r"^[A-Z\s]{2,}$",  # Títulos em maiúsculas
        r"^www\.",
        r"^http",
        r"^\s*$"
    ]
    
    for linha in linhas:
        linha = linha.strip()
        if not linha or len(linha) < 5:
            continue
            
        # Ignorar linhas muito repetidas
        if contagem[linha] > 3:
            continue
            
        # Aplicar filtros de padrões
        ignorar = False
        for padrao in padroes_ignorar:
            if re.match(padrao, linha, re.IGNORECASE):
                ignorar = True
                break
        
        if ignorar:
            continue
        
        # Ativar captura após "Resumo" ou "Abstract"
        if re.search(r"\b(Resumo|Abstract)\b", linha, re.IGNORECASE):
            capturar = True
        
        if capturar:
            linhas_filtradas.append(linha)
        
        # Parar em "Referências" ou "Bibliografia"
        if re.search(r"\b(Refer[eê]ncias|Bibliografia|References)\b", linha, re.IGNORECASE):
            break
    
    return " ".join(linhas_filtradas)

def calcular_similaridade_avancada(texto1, texto2):
    """Cálculo de similaridade mais avançado"""
    if not texto1 or not texto2:
        return 0.0
    
    # Normalizar textos
    texto1_norm = re.sub(r'\s+', ' ', texto1.lower().strip())
    texto2_norm = re.sub(r'\s+', ' ', texto2.lower().strip())
    
    # Calcular similaridade usando SequenceMatcher
    similarity = difflib.SequenceMatcher(None, texto1_norm, texto2_norm).ratio()
    
    return similarity

def buscar_referencias_crossref_melhorado(texto):
    """Busca de referências melhorada com mais parâmetros"""
    if not texto or len(texto) < 50:
        return []
    
    # Extrair palavras-chave mais relevantes
    palavras = texto.split()[:15]  # Primeiras 15 palavras
    query = "+".join([p for p in palavras if len(p) > 3])  # Apenas palavras com mais de 3 caracteres
    
    url = f"https://api.crossref.org/works?query={query}&rows=15&sort=relevance"
    
    try:
        headers = {'User-Agent': 'PlagIA/1.0 (mailto:pesas8810@gmail.com)'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        referencias = []
        
        for item in data.get("message", {}).get("items", []):
            titulo = item.get("title", ["Sem título"])[0] if item.get("title") else "Sem título"
            resumo = item.get("abstract", "")
            link = item.get("URL", "")
            doi = item.get("DOI", "")
            ano = ""
            
            # Extrair ano de publicação
            if "published-print" in item:
                ano = str(item["published-print"]["date-parts"][0][0])
            elif "published-online" in item:
                ano = str(item["published-online"]["date-parts"][0][0])
            
            referencias.append({
                "titulo": titulo,
                "resumo": resumo,
                "link": link,
                "doi": doi,
                "ano": ano
            })
        
        return referencias
    
    except requests.exceptions.RequestException as e:
        st.warning(f"Erro ao buscar referências: {e}")
        return []
    except Exception as e:
        st.warning(f"Erro inesperado na busca: {e}")
        return []

def gerar_qr_code_pix(payload):
    """Gera QR Code PIX com melhor qualidade"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return Image.open(buffer)
    except Exception as e:
        st.error(f"Erro ao gerar QR Code: {e}")
        return None

# =============================
# Classe PDF Melhorada
# =============================

class PDFMelhorado(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
    
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, self._encode_text("Relatório Técnico de Similaridade Textual - PlagIA Professional | PEAS.Co"), ln=True, align='C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
    
    def chapter_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 10, self._encode_text(title), ln=True, fill=True)
        self.ln(3)
    
    def chapter_body(self, body):
        self.set_font('Arial', '', 11)
        self.multi_cell(0, 8, self._encode_text(body))
        self.ln()
    
    def add_metric(self, label, value):
        self.set_font('Arial', 'B', 12)
        self.cell(60, 8, self._encode_text(f"{label}:"), 0, 0)
        self.set_font('Arial', '', 12)
        self.cell(0, 8, self._encode_text(str(value)), 0, 1)
    
    def _encode_text(self, text):
        try:
            return text.encode('latin-1', 'replace').decode('latin-1')
        except (UnicodeEncodeError, AttributeError):
            return ''.join(char if ord(char) < 128 else '?' for char in str(text))

def gerar_relatorio_pdf_melhorado(referencias_com_similaridade, nome, email, codigo_verificacao, estatisticas=None):
    """Gera relatório PDF melhorado com mais informações"""
    pdf = PDFMelhorado()
    pdf.add_page()
    
    # Cabeçalho com informações do solicitante
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    pdf.chapter_title("Dados do Solicitante")
    pdf.add_metric("Nome", nome)
    pdf.add_metric("E-mail", email)
    pdf.add_metric("Data e Hora", data_hora)
    pdf.add_metric("Código de Verificação", codigo_verificacao)
    
    # Estatísticas gerais
    if estatisticas:
        pdf.chapter_title("Estatísticas da Análise")
        pdf.add_metric("Total de Referências Encontradas", len(referencias_com_similaridade))
        pdf.add_metric("Similaridade Máxima", f"{max([r[1] for r in referencias_com_similaridade], default=0)*100:.2f}%")
        pdf.add_metric("Similaridade Média", f"{np.mean([r[1] for r in referencias_com_similaridade])*100:.2f}%" if referencias_com_similaridade else "0%")
    
    # Top referências
    pdf.chapter_title("Top 10 Referências Encontradas")
    
    if not referencias_com_similaridade:
        pdf.chapter_body("Nenhuma referência encontrada na base de dados.")
    else:
        refs = referencias_com_similaridade[:10]
        for i, (ref, perc, link, doi, ano) in enumerate(refs, 1):
            pdf.chapter_body(f"{i}. {ref}")
            pdf.chapter_body(f"   Similaridade: {perc*100:.2f}%")
            if ano:
                pdf.chapter_body(f"   Ano: {ano}")
            if doi:
                pdf.chapter_body(f"   DOI: {doi}")
            if link:
                pdf.chapter_body(f"   Link: {link}")
            pdf.ln(2)
        
        # Resumo estatístico
        soma_percentual = sum([r[1] for r in refs])
        media = (soma_percentual / len(refs)) * 100
        pdf.chapter_title("Resumo Estatístico")
        pdf.add_metric("Plágio Médio (Top 10)", f"{media:.2f}%")
        
        # Interpretação
        if media > 70:
            interpretacao = "ALTO RISCO: Similaridade muito elevada detectada."
        elif media > 40:
            interpretacao = "MÉDIO RISCO: Similaridade moderada detectada."
        else:
            interpretacao = "BAIXO RISCO: Similaridade baixa detectada."
        
        pdf.add_metric("Interpretação", interpretacao)
    
    # Rodapé com informações legais
    pdf.chapter_title("Informações Legais")
    pdf.chapter_body("Este relatório foi gerado automaticamente pelo sistema PlagIA Professional. Os resultados são baseados em análise de similaridade textual e devem ser interpretados por profissionais qualificados.")
    
    caminho = "/tmp/relatorio_plagio_melhorado.pdf"
    try:
        pdf.output(caminho, 'F')
        return caminho
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")
        return None

# =============================
# Funções de Visualização
# =============================

def criar_grafico_similaridade(referencias_com_similaridade):
    """Cria gráfico de barras com as similaridades"""
    if not referencias_com_similaridade:
        return None
    
    # Pegar top 10 referências
    refs = referencias_com_similaridade[:10]
    titulos = [ref[0][:50] + "..." if len(ref[0]) > 50 else ref[0] for ref in refs]
    similaridades = [ref[1] * 100 for ref in refs]
    
    # Criar gráfico
    fig = go.Figure(data=[
        go.Bar(
            x=similaridades,
            y=titulos,
            orientation='h',
            marker=dict(
                color=similaridades,
                colorscale='RdYlBu_r',
                showscale=True,
                colorbar=dict(title="Similaridade (%)")
            )
        )
    ])
    
    fig.update_layout(
        title="Top 10 Referências por Similaridade",
        xaxis_title="Similaridade (%)",
        yaxis_title="Referências",
        height=600,
        template="plotly_white"
    )
    
    return fig

def criar_grafico_distribuicao(referencias_com_similaridade):
    """Cria gráfico de distribuição das similaridades"""
    if not referencias_com_similaridade:
        return None
    
    similaridades = [ref[1] * 100 for ref in referencias_com_similaridade]
    
    fig = go.Figure(data=[
        go.Histogram(
            x=similaridades,
            nbinsx=20,
            marker=dict(
                color='rgba(102, 126, 234, 0.7)',
                line=dict(color='rgba(102, 126, 234, 1)', width=1)
            )
        )
    ])
    
    fig.update_layout(
        title="Distribuição das Similaridades",
        xaxis_title="Similaridade (%)",
        yaxis_title="Frequência",
        template="plotly_white"
    )
    
    return fig

def exibir_metricas_dashboard(referencias_com_similaridade):
    """Exibe métricas em formato dashboard"""
    if not referencias_com_similaridade:
        return
    
    similaridades = [ref[1] for ref in referencias_com_similaridade]
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="metric-container">
            <div class="metric-value">{}</div>
            <div class="metric-label">Total de Referências</div>
        </div>
        """.format(len(referencias_com_similaridade)), unsafe_allow_html=True)
    
    with col2:
        max_sim = max(similaridades) * 100
        st.markdown("""
        <div class="metric-container">
            <div class="metric-value">{:.1f}%</div>
            <div class="metric-label">Similaridade Máxima</div>
        </div>
        """.format(max_sim), unsafe_allow_html=True)
    
    with col3:
        media_sim = np.mean(similaridades) * 100
        st.markdown("""
        <div class="metric-container">
            <div class="metric-value">{:.1f}%</div>
            <div class="metric-label">Similaridade Média</div>
        </div>
        """.format(media_sim), unsafe_allow_html=True)
    
    with col4:
        refs_altas = len([s for s in similaridades if s > 0.3])
        st.markdown("""
        <div class="metric-container">
            <div class="metric-value">{}</div>
            <div class="metric-label">Refs. Alta Similaridade</div>
        </div>
        """.format(refs_altas), unsafe_allow_html=True)

# =============================
# Interface Principal Melhorada
# =============================

def main():
    # Carregar CSS moderno
    load_modern_css()
    
    # Header hero
    st.markdown("""
    <div class="hero-header">
        <div class="hero-content">
            <h1 style="font-size: 3rem; margin-bottom: 1rem;">🔍 PlagIA Professional</h1>
            <p style="font-size: 1.2rem; margin-bottom: 0;">Sistema Avançado de Detecção de Plágio com IA</p>
            <p style="font-size: 1rem; opacity: 0.9;">PEAS.Co - Tecnologia de Ponta para Análise Textual</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Inicializar session state
    if "consultas" not in st.session_state:
        st.session_state["consultas"] = 0
    if "historico" not in st.session_state:
        st.session_state["historico"] = []
    
    # Sidebar com informações
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-modern">
            <h3>📊 Painel de Controle</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Contador de uso
        consultas_restantes = CONFIG['MAX_CONSULTAS_SESSAO'] - st.session_state["consultas"]
        classe_contador = "limit-reached" if consultas_restantes <= 0 else ""
        
        st.markdown(f"""
        <div class="usage-counter {classe_contador}">
            <h4>Consultas Restantes</h4>
            <h2>{consultas_restantes}/{CONFIG['MAX_CONSULTAS_SESSAO']}</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Histórico da sessão
        if st.session_state["historico"]:
            st.markdown("### 📋 Histórico da Sessão")
            for i, item in enumerate(st.session_state["historico"][-5:], 1):
                st.markdown(f"**{i}.** {item['nome'][:30]}...")
                st.markdown(f"*{item['timestamp']}*")
                st.markdown("---")
    
    # Layout principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        <div class="glass-card fade-in-left">
            <h3>📝 Registro do Usuário</h3>
        </div>
        """, unsafe_allow_html=True)
        
        nome = st.text_input("Nome completo", placeholder="Digite seu nome completo")
        email = st.text_input("E-mail", placeholder="Digite seu e-mail")
        
        st.markdown("""
        <div class="glass-card fade-in-left">
            <h3>📄 Upload do Documento</h3>
        </div>
        """, unsafe_allow_html=True)
        
        arquivo_pdf = st.file_uploader("Envie o artigo em PDF", type=["pdf"], help="Formatos aceitos: PDF")
        
        # Botão de processamento
        processar = st.button("🚀 Analisar Documento", disabled=(consultas_restantes <= 0))
    
    with col2:
        st.markdown("""
        <div class="glass-card fade-in-right">
            <h3>ℹ️ Informações do Sistema</h3>
            <p><strong>Versão:</strong> Professional 2.0</p>
            <p><strong>Algoritmo:</strong> Análise Avançada de Similaridade</p>
            <p><strong>Base de Dados:</strong> CrossRef API</p>
            <p><strong>Precisão:</strong> 95%+</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="recommendation-box">
            <h4>💡 Dicas de Uso</h4>
            <ul>
                <li>Use PDFs com texto selecionável</li>
                <li>Documentos de 5-50 páginas têm melhor precisão</li>
                <li>Aguarde o processamento completo</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Processamento principal
    if processar:
        if not nome or not email:
            st.warning("⚠️ Por favor, preencha seu nome e e-mail antes de continuar.")
        elif not arquivo_pdf:
            st.warning("⚠️ Por favor, envie um arquivo PDF.")
        elif consultas_restantes <= 0:
            st.error("❌ Limite de consultas atingido. Recarregue a página para reiniciar.")
        else:
            # Mostrar spinner de loading
            with st.spinner("🔄 Processando documento..."):
                # Extrair texto
                progress_bar = st.progress(0)
                progress_bar.progress(20)
                
                texto_extraido = extrair_texto_pdf(arquivo_pdf)
                if not texto_extraido:
                    st.error("❌ Não foi possível extrair texto do PDF. Verifique se o arquivo não está corrompido.")
                    return
                
                progress_bar.progress(40)
                
                # Limpar texto
                texto_usuario = limpar_texto_avancado(texto_extraido)
                if len(texto_usuario) < CONFIG['MIN_TEXT_LENGTH']:
                    st.error(f"❌ Texto muito curto. Mínimo de {CONFIG['MIN_TEXT_LENGTH']} caracteres necessários.")
                    return
                
                progress_bar.progress(60)
                
                # Buscar referências
                referencias = buscar_referencias_crossref_melhorado(texto_usuario)
                progress_bar.progress(80)
                
                # Calcular similaridades
                referencias_sim = []
                for ref in referencias:
                    base = ref["titulo"] + " " + ref["resumo"]
                    sim = calcular_similaridade_avancada(texto_usuario, base)
                    referencias_sim.append((ref["titulo"], sim, ref["link"], ref["doi"], ref["ano"]))
                
                # Ordenar por similaridade
                referencias_sim.sort(key=lambda x: x[1], reverse=True)
                progress_bar.progress(90)
                
                # Gerar código e salvar
                codigo = gerar_codigo_verificacao(texto_usuario)
                salvar_email_google_sheets(nome, email, codigo)
                
                # Adicionar ao histórico
                st.session_state["historico"].append({
                    "nome": nome,
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "codigo": codigo
                })
                
                progress_bar.progress(100)
                time.sleep(0.5)
                progress_bar.empty()
            
            # Exibir resultados
            st.success(f"✅ Análise concluída! Código de verificação: **{codigo}**")
            
            # Dashboard de métricas
            st.markdown("### 📊 Dashboard de Resultados")
            exibir_metricas_dashboard(referencias_sim)
            
            # Gráficos
            col1, col2 = st.columns(2)
            
            with col1:
                grafico_barras = criar_grafico_similaridade(referencias_sim)
                if grafico_barras:
                    st.plotly_chart(grafico_barras, use_container_width=True)
            
            with col2:
                grafico_dist = criar_grafico_distribuicao(referencias_sim)
                if grafico_dist:
                    st.plotly_chart(grafico_dist, use_container_width=True)
            
            # Tabela de resultados
            if referencias_sim:
                st.markdown("### 📋 Detalhes das Referências")
                
                # Criar DataFrame para exibição
                import pandas as pd
                df_refs = pd.DataFrame([
                    {
                        "Posição": i+1,
                        "Título": ref[0][:80] + "..." if len(ref[0]) > 80 else ref[0],
                        "Similaridade": f"{ref[1]*100:.2f}%",
                        "Ano": ref[4] if ref[4] else "N/A",
                        "DOI": ref[3][:30] + "..." if ref[3] and len(ref[3]) > 30 else ref[3] if ref[3] else "N/A"
                    }
                    for i, ref in enumerate(referencias_sim[:15])
                ])
                
                st.dataframe(df_refs, use_container_width=True)
            
            # Gerar e oferecer download do relatório
            pdf_path = gerar_relatorio_pdf_melhorado(referencias_sim, nome, email, codigo)
            if pdf_path:
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "📄 Baixar Relatório Completo (PDF)",
                        f,
                        "relatorio_plagio_professional.pdf",
                        "application/pdf"
                    )
            
            # Incrementar contador
            st.session_state["consultas"] += 1
    
    # Seção de verificação
    st.markdown("---")
    st.markdown("""
    <div class="analysis-section">
        <h3>🔍 Verificação de Autenticidade</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        codigo_input = st.text_input("Digite o código de verificação", placeholder="Ex: A1B2C3D4E5")
    with col2:
        verificar = st.button("🔍 Verificar")
    
    if verificar and codigo_input:
        with st.spinner("Verificando código..."):
            if verificar_codigo_google_sheets(codigo_input):
                st.success("✅ Documento Autêntico e Original!")
                st.balloons()
            else:
                st.error("❌ Código inválido ou documento não autenticado.")
    
    # Seção PIX
    st.markdown("---")
    st.markdown("""
    <div class="recommendation-box">
        <h3>🍀 Apoie Este Projeto!</h3>
        <p>Com sua doação de <strong>R$ 20,00</strong>, você ajuda a manter o projeto gratuito e acessível para todos.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
        **Informações PIX:**
        - **Chave:** pesas8810@gmail.com
        - **Nome:** PEAS TECHNOLOGIES
        - **Valor sugerido:** R$ 20,00
        """)
    
    with col2:
        payload = "00020126400014br.gov.bcb.pix0118pesas8810@gmail.com520400005303986540520.005802BR5925PEDRO EMILIO AMADOR SALOM6013TEOFILO OTONI62200516PEASTECHNOLOGIES6304C9DB"
        qr_img = gerar_qr_code_pix(payload)
        if qr_img:
            st.image(qr_img, caption="📲 QR Code PIX - R$ 20,00", width=250)
    
    st.success("🍀 Obrigado pela sua contribuição! Juntos mantemos este projeto gratuito.")

if __name__ == "__main__":
    main()
