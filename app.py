# ============================================================================
# 🍀 Sistema PlagIA Professional - v6.1 - Completo e Pronto para Uso
# Foco em extração de texto superior (pdfplumber), limpeza agressiva e
# busca focada no conteúdo principal (resumo/introdução).
# PEAS.Co 2024
# ============================================================================

import streamlit as st
import requests
import PyPDF2
import pdfplumber # Nova biblioteca, mais robusta
import difflib
from fpdf import FPDF
from io import BytesIO
import hashlib
from datetime import datetime, date
import qrcode
import re
from collections import Counter
import numpy as np
import plotly.graph_objects as go
import time
from typing import Dict, List, Tuple, Optional
import logging
from functools import lru_cache
import gc

# --- Configuração da Página e Logging ---
st.set_page_config(
    page_title="PlagIA Professional - Detecção Avançada de Plágio",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constantes e Configurações Globais ---
URL_GOOGLE_SHEETS = "https://script.google.com/macros/s/AKfycbyTpbWDxWkNRh_ZIlHuAVwZaCC2ODqTmo0Un7ZDbgzrVQBmxlYYKuoYf6yDigAPHZiZ/exec"

CONFIG = {
    'MAX_CONSULTAS_SESSAO': 10,
    'MIN_TEXT_LENGTH': 500,
    'MAX_TEXT_LENGTH': 80000,
    'MIN_WORDS': 100,
    'TIMEOUT_API': 30,
    'MAX_REFS_API': 20,
    'MAX_REFS_ANALISE': 15,
    'CACHE_TTL': 3600,
    'SIMILARITY_THRESHOLD_HIGH': 0.3,
}

# =============================
# CSS (Mantido do original )
# =============================
@st.cache_data(ttl=CONFIG['CACHE_TTL'])
def load_optimized_css() -> str:
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap' );
    .main .block-container{padding-top:1rem;padding-bottom:2rem;max-width:1200px}
    html,body,[class*="css"]{font-family:'Inter',sans-serif}
    .hero-header{background:linear-gradient(-45deg,#667eea,#764ba2,#f093fb,#f5576c);background-size:400% 400%;animation:gradientShift 15s ease infinite;padding:2rem;border-radius:20px;margin-bottom:2rem;text-align:center;color:white;box-shadow:0 20px 40px rgba(0,0,0,0.1);position:relative;overflow:hidden}
    @keyframes gradientShift{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
    .glass-card{background:rgba(255,255,255,0.25);backdrop-filter:blur(10px);border-radius:20px;border:1px solid rgba(255,255,255,0.18);padding:2rem;margin:1rem 0;box-shadow:0 8px 32px rgba(31,38,135,0.37);transition:all 0.3s ease}
    .metric-container{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border-radius:15px;padding:1.5rem;color:white;text-align:center;transition:all 0.3s ease;cursor:pointer;margin:0.5rem 0}
    .metric-container:hover{transform:scale(1.05)}
    .metric-value{font-size:2.5rem;font-weight:700;margin-bottom:0.5rem}
    .metric-label{font-size:0.9rem;opacity:0.9;text-transform:uppercase}
    .usage-counter{background:linear-gradient(135deg,#2196F3,#1976D2);color:white;padding:1rem;border-radius:15px;text-align:center;font-weight:bold;margin-bottom:1rem}
    .usage-counter.limit-reached{background:linear-gradient(135deg,#f44336,#d32f2f);animation:pulse 2s infinite}
    @keyframes pulse{0%{transform:scale(1)}50%{transform:scale(1.02)}100%{transform:scale(1)}}
    .stButton>button{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;border:none;border-radius:25px;padding:0.75rem 2rem;font-weight:600;transition:all 0.3s ease;box-shadow:0 4px 15px rgba(102,126,234,0.3)}
    .stButton>button:hover{transform:translateY(-2px)}
    .stButton>button:disabled{background:#cccccc;transform:none}
    .sidebar-modern{background:linear-gradient(180deg,#f8f9fa 0%,#e9ecef 100%);border-radius:15px;padding:1.5rem;margin:1rem 0;border-left:4px solid #667eea;box-shadow:0 4px 15px rgba(0,0,0,0.1)}
    .recommendation-box{background:linear-gradient(135deg,#17a2b8,#138496);color:white;padding:1.5rem;border-radius:12px;margin:1rem 0;border-left:5px solid #0c5460}
    </style>
    """

# =================================================
# NOVAS FUNÇÕES DE EXTRAÇÃO, LIMPEZA E BUSCA
# =================================================

@st.cache_data(show_spinner=False, ttl=CONFIG['CACHE_TTL'])
def extrair_texto_pdf_robusto(arquivo_bytes: bytes) -> str:
    """Tenta extrair texto usando pdfplumber (preferencial) e PyPDF2 como fallback."""
    texto = ""
    try:
        with pdfplumber.open(BytesIO(arquivo_bytes)) as pdf:
            texto = "\n".join(page.extract_text(x_tolerance=1, y_tolerance=3) or "" for page in pdf.pages)
        logger.info("Texto extraído com sucesso usando pdfplumber.")
    except Exception as e:
        logger.warning(f"Falha ao usar pdfplumber: {e}. Tentando com PyPDF2.")
        try:
            leitor = PyPDF2.PdfReader(BytesIO(arquivo_bytes))
            texto = "\n".join(page.extract_text() or "" for page in leitor.pages)
            logger.info("Texto extraído com sucesso usando PyPDF2 (fallback).")
        except Exception as e2:
            logger.error(f"Falha em ambos os extratores: {e2}")
            return ""
    return texto

@lru_cache(maxsize=32)
def limpar_texto_agressivo(texto_bruto: str) -> str:
    """Limpeza de texto agressiva para isolar o conteúdo principal."""
    if not texto_bruto: return ""

    texto_lower = texto_bruto.lower()
    
    # Tenta encontrar o texto entre "resumo" e "introdução" ou "palavras-chave"
    match_resumo = re.search(r'(resumo|abstract)(.*?)(\n.*?){0,10}(palavras-chave|keywords|introdução|introduction)', texto_lower, re.DOTALL)
    if match_resumo:
        coracao_texto = match_resumo.group(2)
        logger.info("Seção 'Resumo/Abstract' encontrada para extração de palavras-chave.")
    else:
        # Se não encontrar, pega o início do texto, mas remove lixo antes
        linhas = texto_lower.splitlines()
        primeira_linha_longa = 0
        for i, linha in enumerate(linhas):
            if len(linha.strip()) > 50: # Encontra a primeira linha com conteúdo real
                primeira_linha_longa = i
                break
        coracao_texto = " ".join(linhas[primeira_linha_longa:primeira_linha_longa+50])[:4000]
        logger.info("Seção 'Resumo/Abstract' não encontrada, usando o início do texto.")

    # Limpeza final do trecho selecionado
    texto_limpo = re.sub(r'http\S+', '', coracao_texto )
    texto_limpo = re.sub(r'[^a-zA-Z\s]', ' ', texto_limpo) # Remove tudo que não for letra ou espaço
    texto_limpo = re.sub(r'\s+', ' ', texto_limpo).strip()
    
    return texto_limpo

def gerar_query_de_busca(texto_limpo: str) -> str:
    """Gera a query de busca a partir do texto limpo, removendo stopwords."""
    stopwords = ['a', 'o', 'e', 'ou', 'de', 'do', 'da', 'em', 'para', 'com', 'um', 'uma', 'que', 'se', 'foi', 'ser', 'ter', 'como', 'pelo', 'pela', 'este', 'esta', 'neste', 'nesta', 'artigo', 'trabalho', 'estudo', 'pesquisa', 'autor', 'autores']
    palavras = [p for p in texto_limpo.split() if p not in stopwords and len(p) > 3]
    return " ".join(palavras[:20])

@st.cache_data(ttl=CONFIG['CACHE_TTL'])
def buscar_crossref(query: str) -> List[Dict]:
    if not query: return []
    url = f"https://api.crossref.org/works?query.bibliographic={requests.utils.quote(query )}&rows={CONFIG['MAX_REFS_API']}&sort=relevance"
    headers = {'User-Agent': 'PlagIA/6.1 (mailto:contato@peas.co)'}
    try:
        r = requests.get(url, headers=headers, timeout=CONFIG['TIMEOUT_API'])
        r.raise_for_status()
        items = r.json().get('message', {}).get('items', [])
        return [{
            'titulo': item.get('title', [''])[0],
            'resumo': item.get('abstract', ''),
            'link': item.get('URL', ''),
            'doi': item.get('DOI', ''),
            'ano': str(item.get('published-print', {}).get('date-parts', [['']])[0][0])
        } for item in items if item.get('title')]
    except requests.RequestException as e:
        logger.warning(f"API CrossRef falhou: {e}")
        return []

@st.cache_data(ttl=CONFIG['CACHE_TTL'])
def buscar_semantic_scholar(query: str) -> List[Dict]:
    if not query: return []
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={requests.utils.quote(query )}&limit={CONFIG['MAX_REFS_API']}&fields=title,abstract,year,url,externalIds"
    try:
        r = requests.get(url, timeout=CONFIG['TIMEOUT_API'])
        r.raise_for_status()
        results = r.json().get('data', [])
        return [{
            'titulo': item.get('title', ''),
            'resumo': item.get('abstract', ''),
            'link': item.get('url', ''),
            'doi': item.get('externalIds', {}).get('DOI', ''),
            'ano': str(item.get('year', ''))
        } for item in results]
    except requests.RequestException as e:
        logger.warning(f"API Semantic Scholar falhou: {e}")
        return []

def buscar_referencias_robusto(texto_limpo: str, status_placeholder) -> List[Dict]:
    query = gerar_query_de_busca(texto_limpo)
    if not query:
        logger.error("Não foi possível gerar uma query de busca a partir do texto limpo.")
        return []

    fontes = [("CrossRef", buscar_crossref), ("Semantic Scholar", buscar_semantic_scholar)]
    for nome_fonte, funcao_busca in fontes:
        status_placeholder.text(f"🔎 Buscando em '{nome_fonte}'...")
        referencias = funcao_busca(query)
        if referencias:
            logger.info(f"Sucesso! {len(referencias)} refs em '{nome_fonte}'.")
            return referencias
    
    logger.warning("Nenhuma referência encontrada em nenhuma fonte.")
    return []

# =================================================
# FUNÇÕES AUXILIARES E DE UI (Mantidas e adaptadas)
# =================================================

@st.cache_data(ttl=CONFIG['CACHE_TTL'])
def gerar_codigo_verificacao(texto: str) -> str:
    timestamp = str(int(time.time()))
    combined = texto[:1000] + timestamp
    return hashlib.md5(combined.encode('utf-8', 'ignore')).hexdigest()[:10].upper()

@lru_cache(maxsize=128)
def validar_texto_robusto(texto: str) -> Tuple[bool, str]:
    if not texto or not isinstance(texto, str): return False, "Texto inválido ou vazio"
    texto_limpo = texto.strip()
    if len(texto_limpo) < CONFIG['MIN_TEXT_LENGTH']: return False, f"Texto muito curto. Mínimo de {CONFIG['MIN_TEXT_LENGTH']} caracteres. Atual: {len(texto_limpo)}"
    if len(texto_limpo) > CONFIG['MAX_TEXT_LENGTH']: return False, f
