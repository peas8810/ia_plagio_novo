# ============================================================================
# 🍀 Sistema PlagIA Professional - Versão Final com Busca Robusta
# Mantém o design original com um novo motor de busca (CrossRef + Semantic Scholar)
# e processamento de texto aprimorado para máxima eficiência.
# PEAS.Co 2024
# ============================================================================

import streamlit as st
import requests
import PyPDF2
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
    'MAX_CONSULTAS_SESSAO': 4,
    'MIN_TEXT_LENGTH': 700,
    'MAX_TEXT_LENGTH': 60000,
    'MIN_WORDS': 500,
    'TIMEOUT_API': 25,  # Aumentado para maior tolerância
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
# NOVAS FUNÇÕES DE BUSCA ROBUSTA E PROCESSAMENTO
# =================================================

def extrair_palavras_chave(texto: str, estrategia: int) -> str:
    """Extrai palavras-chave de um texto usando diferentes estratégias."""
    texto_lower = texto.lower()
    if estrategia == 1:
        return " ".join(re.findall(r'\b\w{6,15}\b', texto_lower[:2000])[:15])
    elif estrategia == 2:
        tokens = re.findall(r'\b\w+\b', texto_lower[:2500])
        bigramas = [" ".join(tokens[i:i+2]) for i in range(len(tokens)-1)]
        return " ".join(bigramas[:10])
    elif estrategia == 3:
        palavras = re.findall(r'\b\w{5,}\b', texto_lower)
        if not palavras: return ""
        contagem = Counter(p for p in palavras if p not in ['artigo', 'estudo', 'trabalho', 'neste', 'nesta'])
        return " ".join([p[0] for p in contagem.most_common(12)])
    return ""

@st.cache_data(ttl=CONFIG['CACHE_TTL'])
def buscar_crossref(query: str) -> List[Dict]:
    """Busca na API da CrossRef."""
    if not query: return []
    url = f"https://api.crossref.org/works?query.bibliographic={requests.utils.quote(query )}&rows={CONFIG['MAX_REFS_API']}&sort=relevance"
    headers = {'User-Agent': 'PlagIA/5.0 (mailto:contato@peas.co)'}
    try:
        r = requests.get(url, headers=headers, timeout=CONFIG['TIMEOUT_API'])
        r.raise_for_status()
        items = r.json().get('message', {}).get('items', [])
        
        referencias = []
        for item in items:
            title = item.get('title', [''])[0]
            if not title: continue
            
            ano = ""
            if 'published-print' in item and 'date-parts' in item['published-print']:
                ano = item['published-print']['date-parts'][0][0]
            
            referencias.append({
                'titulo': title,
                'resumo': item.get('abstract', ''),
                'link': item.get('URL', ''),
                'doi': item.get('DOI', ''),
                'ano': str(ano)
            })
        return referencias
    except requests.RequestException as e:
        logger.warning(f"API CrossRef falhou: {e}")
        return []

@st.cache_data(ttl=CONFIG['CACHE_TTL'])
def buscar_semantic_scholar(query: str) -> List[Dict]:
    """Busca na API do Semantic Scholar."""
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

def buscar_referencias_robusto(texto: str, status_placeholder) -> List[Dict]:
    """Executa uma busca em cascata, usando múltiplas estratégias e fontes."""
    fontes = [
        ("CrossRef", buscar_crossref),
        ("Semantic Scholar", buscar_semantic_scholar)
    ]
    
    for nome_fonte, funcao_busca in fontes:
        for estrategia in range(1, 4):
            status_placeholder.text(f"🔎 Buscando em '{nome_fonte}' (Estratégia #{estrategia})...")
            query = extrair_palavras_chave(texto, estrategia=estrategia)
            
            if not query: continue

            referencias = funcao_busca(query)
            
            if referencias:
                logger.info(f"Sucesso! {len(referencias)} refs em '{nome_fonte}' com estratégia #{estrategia}.")
                return referencias
    
    logger.warning("Nenhuma referência encontrada em nenhuma fonte/estratégia.")
    return []

@lru_cache(maxsize=64)
def limpar_texto_otimizado(texto_bruto: str) -> str:
    """Limpeza de texto aprimorada para focar no conteúdo principal."""
    if not texto_bruto: return ""
    
    # Remove tudo após as referências bibliográficas
    texto_sem_refs = re.split(r'\n\s*(Refer[eê]ncias|Bibliografia|References)\s*\n', texto_bruto, flags=re.IGNORECASE)[0]
    
    # Remove URLs e normaliza espaços
    texto_limpo = re.sub(r'http\S+', '', texto_sem_refs )
    texto_limpo = re.sub(r'[^a-zA-Z0-9\s.,-]', ' ', texto_limpo)
    texto_limpo = re.sub(r'\s+', ' ', texto_limpo)
    
    return texto_limpo.strip()

# =================================================
# FUNÇÕES AUXILIARES (Mantidas do original com pequenas adaptações)
# =================================================

@st.cache_data(ttl=CONFIG['CACHE_TTL'])
def gerar_codigo_verificacao(texto: str) -> str:
    timestamp = str(int(time.time()))
    combined = texto[:1000] + timestamp
    return hashlib.md5(combined.encode('utf-8', 'ignore')).hexdigest()[:10].upper()

@lru_cache(maxsize=128)
def validar_texto_robusto(texto: str) -> Tuple[bool, str]:
    if not texto or not isinstance(texto, str):
        return False, "Texto inválido ou vazio"
    texto_limpo = texto.strip()
    if len(texto_limpo) < CONFIG['MIN_TEXT_LENGTH']:
        return False, f"Texto muito curto. Mínimo de {CONFIG['MIN_TEXT_LENGTH']} caracteres. Atual: {len(texto_limpo)}"
    if len(texto_limpo) > CONFIG['MAX_TEXT_LENGTH']:
        return False, f"Texto muito longo. Máximo de {CONFIG['MAX_TEXT_LENGTH']} caracteres permitidos"
    palavras = len(texto_limpo.split())
    if palavras < CONFIG['MIN_WORDS']:
        return False, f"Texto com poucas palavras. Mínimo de {CONFIG['MIN_WORDS']} palavras. Atual: {palavras}"
    return True, "Texto válido"

@st.cache_data(show_spinner=False)
def extrair_texto_pdf_otimizado(arquivo_pdf) -> str:
    try:
        leitor = PyPDF2.PdfReader(arquivo_pdf)
        texto_completo = "".join(page.extract_text() or "" for page in leitor.pages)
        return texto_completo
    except Exception as e:
        logger.error(f"Erro ao extrair PDF: {e}")
        return ""

def salvar_email_google_sheets_otimizado(nome: str, email: str, codigo: str) -> bool:
    dados = {"nome": nome[:100], "email": email[:100], "codigo": codigo, "data": str(date.today())}
    try:
        res = requests.post(URL_GOOGLE_SHEETS, json=dados, headers={'Content-Type': 'application/json'}, timeout=CONFIG['TIMEOUT_API'])
        return res.text.strip() == "Sucesso"
    except Exception as e:
        logger.error(f"Erro Sheets: {e}")
        return False

def verificar_codigo_google_sheets_otimizado(codigo: str) -> bool:
    try:
        res = requests.get(f"{URL_GOOGLE_SHEETS}?codigo={codigo}", timeout=CONFIG['TIMEOUT_API'])
        return res.text.strip() == "Valido"
    except Exception as e:
        logger.error(f"Erro verificar código: {e}")
        return False

@lru_cache(maxsize=256)
def calcular_similaridade_otimizada(texto1: str, texto2: str) -> float:
    if not texto1 or not texto2: return 0.0
    # Limita o tamanho dos textos para evitar sobrecarga no difflib
    t1 = texto1.lower()[:5000]
    t2 = texto2.lower()[:5000]
    return difflib.SequenceMatcher(None, t1, t2).ratio()

# =============================
# Classe PDF (Mantida do original)
# =============================
class PDFOtimizado(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, self._encode_text("Relatório PlagIA Professional - PEAS.Co"), ln=True, align='C')
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    def add_section(self, title: str, content: str):
        if title:
            self.set_font('Arial', 'B', 12)
            self.cell(0, 8, self._encode_text(title), ln=True)
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 6, self._encode_text(content))
        self.ln(3)

    def _encode_text(self, text: str) -> str:
        return str(text).encode('latin-1', 'replace').decode('latin-1')

def gerar_relatorio_otimizado(referencias_sim: List, nome: str, email: str, codigo: str) -> Optional[bytes]:
    try:
        pdf = PDFOtimizado()
        pdf.add_page()
        dt = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        pdf.add_section("Dados do Solicitante", f"Nome: {nome}\nE-mail: {email}\nData: {dt}\nCódigo: {codigo}")
        
        if referencias_sim:
            total = len(referencias_sim)
            max_s = max(r[1] for r in referencias_sim) * 100
            avg_s = np.mean([r[1] for r in referencias_sim]) * 100
            stats = f"Total de Referências Encontradas: {total}\nSimilaridade Máxima: {max_s:.2f}%\nSimilaridade Média: {avg_s:.2f}%"
            pdf.add_section("Estatísticas da Análise", stats)
            
            pdf.add_section("Top 10 Referências com Maior Similaridade", "")
            for i, (t, s, link, doi, ano) in enumerate(referencias_sim[:10], 1):
                link_final = f"https://doi.org/{doi}" if doi else link
                txt = (f"{i}. {t}\nAno: {ano or 'N/A'}\nSimilaridade: {s*100:.2f}%\nLink: {link_final or 'N/A'}" )
                pdf.add_section("", txt)
        else:
            pdf.add_section("Resultado", "Nenhuma referência com similaridade significativa foi encontrada.")
        
        return pdf.output(dest='S').encode('latin-1')
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}")
        return None

# =============================
# Visualizações (Mantidas do original)
# =============================
@st.cache_data(ttl=CONFIG['CACHE_TTL'])
def criar_grafico_barras_otimizado(referencias_sim: List) -> Optional[go.Figure]:
    if not referencias_sim: return None
    refs = referencias_sim[:10]
    nomes = [r[0][:40] + ("..." if len(r[0]) > 40 else "") for r in refs]
    sims = [r[1] * 100 for r in refs]
    fig = go.Figure(data=[go.Bar(x=sims, y=nomes, orientation='h', marker=dict(color=sims, colorscale='RdYlBu_r', showscale=True))])
    fig.update_layout(title="Top 10 Referências por Similaridade", xaxis_title="Similaridade (%)", height=400, template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))
    return fig

def exibir_metricas_otimizadas(referencias_sim: List):
    if not referencias_sim:
        st.warning("Nenhuma referência encontrada para análise.")
        return
    sims = [r[1] for r in referencias_sim]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-container"><div class="metric-value">{len(sims)}</div><div class="metric-label">Total Referências</div></div>', unsafe_allow_html=True)
    with c2:
        mval = max(sims) * 100 if sims else 0
        st.markdown(f'<div class="metric-container"><div class="metric-value">{mval:.1f}%</div><div class="metric-label">Máxima</div></div>', unsafe_allow_html=True)
    with c3:
        aval = np.mean(sims) * 100 if sims else 0
        st.markdown(f'<div class="metric-container"><div class="metric-value">{aval:.1f}%</div><div class="metric-label">Média</div></div>', unsafe_allow_html=True)
    with c4:
        high_count = len([x for x in sims if x > CONFIG['SIMILARITY_THRESHOLD_HIGH']])
        st.markdown(f'<div class="metric-container"><div class="metric-value">{high_count}</div><div class="metric-label">Alta Similaridade</div></div>', unsafe_allow_html=True)

# =============================
# Interface Principal (Adaptada para o novo fluxo)
# =============================
def main():
    st.markdown(load_optimized_css(), unsafe_allow_html=True)
    st.markdown("""<div class="hero-header"><h1 style="font-size:2.5rem;margin-bottom:0.5rem;">🔍 PlagIA Professional</h1><p style="font-size:1rem;margin:0;">Sistema Otimizado de Detecção de Plágio</p></div>""", unsafe_allow_html=True)

    if "consultas" not in st.session_state: st.session_state["consultas"] = 0
    if "historico" not in st.session_state: st.session_state["historico"] = []

    with st.sidebar:
        st.markdown("""<div class="sidebar-modern"><h3>📊 Painel de Controle</h3></div>""", unsafe_allow_html=True)
        rest = CONFIG['MAX_CONSULTAS_SESSAO'] - st.session_state["consultas"]
        cls = "limit-reached" if rest <= 0 else ""
        st.markdown(f"""<div class="usage-counter {cls}"><h4>Consultas Restantes</h4><h2>{rest}/{CONFIG['MAX_CONSULTAS_SESSAO']}</h2></div>""", unsafe_allow_html=True)
        if st.session_state["historico"]:
            st.markdown("### 📋 Histórico")
            for item in st.session_state["historico"][-3:]:
                st.markdown(f"**{item['nome'][:20]}...** - {item['timestamp']}")
        
        pix_key = "pesas8810@gmail.com"
        img_qr = qrcode.make(f"pix:{pix_key}")
        buf = BytesIO()
        img_qr.save(buf, format="PNG")
        st.image(buf.getvalue(), caption="💚 Apoie o Projeto via Pix", width=120)
        st.markdown(f"**Chave Pix:** {pix_key}")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("""<div class="glass-card"><h3>📝 Registro do Usuário</h3></div>""", unsafe_allow_html=True)
        nome = st.text_input("Nome completo", placeholder="Digite seu nome completo")
        email = st.text_input("E-mail", placeholder="Digite seu e-mail")
        st.markdown("""<div class="glass-card"><h3>📄 Upload do Documento</h3></div>""", unsafe_allow_html=True)
        arquivo_pdf = st.file_uploader("Envie o artigo em PDF", type=["pdf"])
        processar = st.button("🚀 Analisar Documento", disabled=(rest <= 0))

    with col2:
        st.markdown("""<div class="glass-card"><h3>ℹ️ Sistema</h3><p><strong>Versão:</strong> Robusta 5.0</p><p><strong>Fontes:</strong> CrossRef, Semantic Scholar</p></div>""", unsafe_allow_html=True)
        st.markdown(f"""<div class="recommendation-box"><h4>📋 Requisitos</h4><ul><li>Mínimo {CONFIG['MIN_TEXT_LENGTH']} caracteres</li><li>Mínimo {CONFIG['MIN_WORDS']} palavras</li><li>PDF com texto selecionável</li></ul></div>""", unsafe_allow_html=True)

    if processar:
        if not nome or not email: st.error("⚠️ Por favor, preencha nome e e-mail."); return
        if not arquivo_pdf: st.error("⚠️ Por favor, envie um arquivo PDF."); return
        if rest <= 0: st.error("❌ Limite de consultas atingido."); return
        
        container = st.container()
        with container:
            bar = st.progress(0, text="Iniciando análise...")
            status = st.empty()
            try:
                status.text("🔄 Extraindo texto do PDF..."); bar.progress(10)
                texto_bruto = extrair_texto_pdf_otimizado(arquivo_pdf)
                if not texto_bruto: st.error("❌ Não foi possível extrair texto do PDF."); return

                status.text("🧹 Processando e limpando o texto..."); bar.progress(25)
                texto_limpo = limpar_texto_otimizado(texto_bruto)
                ok, msg = validar_texto_robusto(texto_limpo)
                if not ok: st.error(f"❌ Texto inválido após limpeza: {msg}"); return

                bar.progress(40)
                referencias = buscar_referencias_robusto(texto_limpo, status)
                
                if not referencias:
                    st.warning("⚠️ Nenhuma referência encontrada, mesmo após busca extensiva. O documento pode ser original ou o tópico não está indexado.")
                    st.session_state['consultas'] += 1
                    container.empty(); return

                status.text("📊 Calculando similaridades..."); bar.progress(75)
                resultados = []
                for r in referencias[:CONFIG['MAX_REFS_ANALISE']]:
                    base = f"{r['titulo']} {r['resumo']}"
                    sim = calcular_similaridade_otimizada(texto_limpo, base)
                    if sim > 0.05: # Filtro de similaridade mínima
                        resultados.append((r['titulo'], sim, r['link'], r['doi'], r['ano']))
                
                resultados.sort(key=lambda x: x[1], reverse=True)
                
                status.text("✅ Gerando resultados finais..."); bar.progress(90)
                codigo = gerar_codigo_verificacao(texto_limpo)
                salvar_email_google_sheets_otimizado(nome, email, codigo)
                st.session_state['historico'].append({'nome': nome, 'timestamp': datetime.now().strftime('%H:%M'), 'codigo': codigo})
                
                pdf_bytes = gerar_relatorio_otimizado(resultados, nome, email, codigo)
                
                bar.progress(100); time.sleep(0.5)
                container.empty()
                
                st.success(f"✅ Análise concluída! Código de verificação: **{codigo}**")
                st.markdown("### 📊 Resultados da Análise")
                exibir_metricas_otimizadas(resultados)
                
                if resultados:
                    with st.expander("📈 Visualização Detalhada dos Resultados", expanded=True):
                        fig = criar_grafico_barras_otimizado(resultados)
                        if fig: st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("### 📋 Top 10 Referências Encontradas")
                    import pandas as pd
                    df_data = [{
                        '#': i+1,
                        'Título': ref[0][:60] + ('...' if len(ref[0])>60 else ''),
                        'Similaridade': f"{ref[1]*100:.1f}%",
                        'Ano': ref[4] or 'N/A'
                    } for i, ref in enumerate(resultados[:10])]
                    st.dataframe(pd.DataFrame(df_data), use_container_width=True, hide_index=True)
                
                if pdf_bytes:
                    st.download_button("📄 Baixar Relatório Completo em PDF", pdf_bytes, "relatorio_plagia.pdf", "application/pdf")
                
                st.session_state['consultas'] += 1
                gc.collect()

            except Exception as e:
                logger.error(f"Erro fatal no processamento: {e}", exc_info=True)
                st.error(f"❌ Ocorreu um erro inesperado durante o processamento. Tente novamente.")
                container.empty()

    st.markdown("---")
    st.markdown("### 🔍 Verificar Autenticidade de Relatório")
    c1, c2 = st.columns([3, 1])
    with c1:
        codigo_input = st.text_input("Código de verificação", placeholder="Ex: A1B2C3D4E5", label_visibility="collapsed")
    with c2:
        if st.button("Verificar Código"):
            if codigo_input:
                with st.spinner("Verificando..."):
                    if verificar_codigo_google_sheets_otimizado(codigo_input):
                        st.success("✅ Documento autêntico!")
                    else:
                        st.error("❌ Código inválido ou não encontrado.")
            else:
                st.warning("Por favor, insira um código.")

if __name__ == "__main__":
    main()
