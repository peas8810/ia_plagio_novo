# =============================
# 🍀 Sistema PlagIA - v9.1 - Final e Corrigido
# Layout profissional, similaridade robusta com fuzzywuzzy e relatório com 10 referências.
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
from fuzzywuzzy import fuzz # Biblioteca para similaridade robusta

# 🔗 URL da API gerada no Google Sheets
URL_GOOGLE_SHEETS = "https://script.google.com/macros/s/AKfycbyTpbWDxWkNRh_ZIlHuAVwZaCC2ODqTmo0Un7ZDbgzrVQBmxlYYKuoYf6yDigAPHZiZ/exec"

# =============================
# 🎨 CSS e Layout
# =============================
@st.cache_data(ttl=3600 )
def load_professional_css() -> str:
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap' );
    .main .block-container{padding-top:1rem;padding-bottom:2rem;max-width:1200px}
    html,body,[class*="css"]{font-family:'Inter',sans-serif}
    .hero-header{background:linear-gradient(-45deg,#667eea,#764ba2,#f093fb,#f5576c);background-size:400% 400%;animation:gradientShift 15s ease infinite;padding:2rem;border-radius:20px;margin-bottom:2rem;text-align:center;color:white;box-shadow:0 20px 40px rgba(0,0,0,0.1);}
    @keyframes gradientShift{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
    .glass-card{background:rgba(255,255,255,0.25);backdrop-filter:blur(10px);border-radius:20px;border:1px solid rgba(255,255,255,0.18);padding:2rem;margin:1rem 0;box-shadow:0 8px 32px rgba(31,38,135,0.37);}
    .metric-container{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border-radius:15px;padding:1.5rem;color:white;text-align:center;transition:all 0.3s ease;cursor:pointer;margin:0.5rem 0}
    .metric-container:hover{transform:scale(1.05)}
    .metric-value{font-size:2.5rem;font-weight:700;margin-bottom:0.5rem}
    .metric-label{font-size:0.9rem;opacity:0.9;text-transform:uppercase}
    .stButton>button{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;border:none;border-radius:25px;padding:0.75rem 2rem;font-weight:600;transition:all 0.3s ease;box-shadow:0 4px 15px rgba(102,126,234,0.3)}
    .stButton>button:hover{transform:translateY(-2px)}
    .sidebar-modern{background:linear-gradient(180deg,#f8f9fa 0%,#e9ecef 100%);border-radius:15px;padding:1.5rem;margin:1rem 0;border-left:4px solid #667eea;box-shadow:0 4px 15px rgba(0,0,0,0.1)}
    </style>
    """

# =============================
# 📋 Funções Auxiliares (com melhorias)
# =============================
def salvar_email_google_sheets(nome, email, codigo_verificacao):
    dados = {"nome": nome, "email": email, "codigo": codigo_verificacao, "data": str(date.today())}
    try:
        response = requests.post(URL_GOOGLE_SHEETS, json=dados, headers={'Content-Type': 'application/json'})
        return response.text.strip() == "Sucesso"
    except: return False

def verificar_codigo_google_sheets(codigo_digitado):
    try:
        response = requests.get(f"{URL_GOOGLE_SHEETS}?codigo={codigo_digitado}")
        return response.text.strip() == "Valido"
    except: return False

def gerar_codigo_verificacao(texto):
    return hashlib.md5(texto.encode('utf-8', 'ignore')).hexdigest()[:10].upper()

def extrair_texto_pdf(arquivo_pdf):
    try:
        leitor_pdf = PyPDF2.PdfReader(arquivo_pdf)
        return "".join(pagina.extract_text() or "" for pagina in leitor_pdf.pages).strip()
    except Exception as e:
        st.error(f"Erro ao ler o PDF: {e}")
        return ""

def limpar_texto(texto_bruto):
    linhas = texto_bruto.splitlines()
    linhas_filtradas = []
    contagem = Counter(linhas)
    capturar = False
    for linha in linhas:
        linha = linha.strip()
        if not linha or len(linha) < 10 or contagem[linha] > 3: continue
        if re.match(r"^Página?\s*\d+$", linha, re.IGNORECASE): continue
        if "doi" in linha.lower() and len(linha) < 50: continue
        if re.search(r"\b(Resumo|Abstract|Introdução|Introduction)\b", linha, re.IGNORECASE): capturar = True
        if capturar: linhas_filtradas.append(linha)
        if re.search(r"\b(Refer[eê]ncias|Bibliografia|References)\b", linha, re.IGNORECASE): break
    return " ".join(linhas_filtradas)

def calcular_similaridade_robusta(texto1, texto2):
    """Usa fuzzywuzzy para um cálculo de similaridade mais inteligente."""
    return fuzz.token_sort_ratio(texto1, texto2) / 100.0

def buscar_referencias_crossref(texto):
    stopwords = ['a', 'o', 'e', 'de', 'do', 'da', 'para', 'com']
    palavras_query = [p for p in texto.split() if p.lower() not in stopwords][:15]
    query = "+".join(palavras_query)
    url = f"https://api.crossref.org/works?query.bibliographic={query}&rows=15"
    try:
        data = requests.get(url, timeout=15 ).json()
        referencias = []
        for item in data.get("message", {}).get("items", []):
            referencias.append({
                "titulo": item.get("title", ["Sem título"])[0],
                "resumo": item.get("abstract", ""),
                "link": item.get("URL", ""),
                "doi": item.get("DOI", ""),
                "ano": str(item.get('published-print', {}).get('date-parts', [['']])[0][0])
            })
        return referencias
    except Exception as e:
        st.error(f"Erro ao contatar a base de dados: {e}")
        return []

# =============================
# 📄 Classe PDF e Relatório Aprimorado
# =============================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, self._encode_text("Relatório de Análise de Similaridade - PlagIA | PEAS.Co"), ln=True, align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 8, self._encode_text(title), ln=True, align='L')
        self.ln(2)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 6, self._encode_text(body))
        self.ln()

    def _encode_text(self, text):
        return str(text).encode('latin-1', 'replace').decode('latin-1')

def gerar_relatorio_pdf(referencias_com_similaridade, nome, email, codigo_verificacao):
    pdf = PDF()
    pdf.add_page()
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    pdf.chapter_title("1. Dados da Análise")
    pdf.chapter_body(f"Nome do Solicitante: {nome}\nE-mail: {email}\nData e Hora: {data_hora}\nCódigo de Verificação: {codigo_verificacao}")

    if not referencias_com_similaridade:
        pdf.chapter_title("2. Resultados")
        pdf.chapter_body("Nenhuma referência com similaridade significativa foi encontrada.")
    else:
        top_refs = referencias_com_similaridade[:10]
        percentuais = [p for _, p, _, _, _ in top_refs]
        
        pdf.chapter_title("2. Resumo Estatístico")
        stats = (f"Total de Referências Analisadas: {len(top_refs)}\n"
                 f"Similaridade Máxima Encontrada: {max(percentuais)*100:.2f}%\n"
                 f"Similaridade Média (Top 10): {np.mean(percentuais)*100:.2f}%")
        pdf.chapter_body(stats)

        pdf.chapter_title("3. Detalhamento das Top 10 Referências")
        for i, (titulo, perc, link, doi, ano) in enumerate(top_refs, 1):
            link_final = f"https://doi.org/{doi}" if doi else link
            ref_body = (f"#{i}. {titulo}\n"
                        f"Ano: {ano or 'N/A'} | Similaridade: {perc*100:.2f}%\n"
                        f"Link: {link_final or 'N/A'}" )
            pdf.chapter_body(ref_body)

    return pdf.output(dest='S').encode('latin-1')

# =============================
# 💻 Interface Principal do Streamlit
# =============================
def main():
    st.markdown(load_professional_css(), unsafe_allow_html=True)
    st.markdown('<div class="hero-header"><h1>🍀 PlagIA Professional</h1><p>Análise de Similaridade de Documentos com IA</p></div>', unsafe_allow_html=True)

    if "consultas" not in st.session_state:
        st.session_state["consultas"] = 0

    # --- Layout com Sidebar ---
    with st.sidebar:
        st.markdown('<div class="sidebar-modern"><h3>📊 Painel de Controle</h3></div>', unsafe_allow_html=True)
        st.info(f"**Consultas restantes:** {4 - st.session_state['consultas']}/4")
        
        st.markdown("---")
        st.subheader("Verificação de Autenticidade")
        codigo_input = st.text_input("Digite o código de verificação")
        if st.button("🔍 Verificar Código"):
            if codigo_input:
                if verificar_codigo_google_sheets(codigo_input):
                    st.success("✅ Documento Autêntico!")
                else:
                    st.error("❌ Código inválido.")
            else:
                st.warning("Por favor, insira um código.")
                
        st.markdown("---")
        st.subheader("💚 Apoie o Projeto")
        payload = "00020126400014br.gov.bcb.pix0118pesas8810@gmail.com520400005303986540520.005802BR5925PEDRO EMILIO AMADOR SALOM6013TEOFILO OTONI62200516PEASTECHNOLOGIES6304C9DB"
        qr_img = qrcode.make(payload)
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        st.image(buf.getvalue(), caption="Pix para PEAS TECHNOLOGIES (R$ 20,00)", width=150)

    # --- Área Principal ---
    st.markdown('<div class="glass-card"><h3>1. Preencha seus dados e envie o documento</h3></div>', unsafe_allow_html=True)
    nome = st.text_input("Nome completo")
    email = st.text_input("E-mail")
    arquivo_pdf = st.file_uploader("📄 Envie o artigo em PDF", type=["pdf"])

    if st.button("🚀 Analisar Documento"):
        if not nome or not email:
            st.warning("⚠️ Por favor, preencha seu nome e e-mail.")
        elif not arquivo_pdf:
            st.warning("⚠️ Por favor, envie um arquivo PDF.")
        elif st.session_state["consultas"] >= 4:
            st.error("❌ Limite de consultas atingido. Recarregue a página para reiniciar.")
        else:
            with st.spinner("Analisando seu documento... Isso pode levar alguns instantes."):
                texto_extraido = extrair_texto_pdf(arquivo_pdf)
                texto_usuario = limpar_texto(texto_extraido)
                
                if not texto_usuario:
                    st.error("❌ Não foi possível extrair conteúdo válido do PDF. Verifique se o texto é selecionável.")
                else:
                    referencias = buscar_referencias_crossref(texto_usuario)
                    referencias_sim = []
                    for ref in referencias:
                        base = ref["titulo"] + " " + ref["resumo"]
                        sim = calcular_similaridade_robusta(texto_usuario, base)
                        referencias_sim.append((ref["titulo"], sim, ref["link"], ref["doi"], ref["ano"]))
                    
                    referencias_sim.sort(key=lambda x: x[1], reverse=True)
                    codigo = gerar_codigo_verificacao(texto_usuario)
                    salvar_email_google_sheets(nome, email, codigo)
                    
                    st.success(f"✅ Análise concluída! Código de verificação: **{codigo}**")
                    
                    # Exibir Dashboard de Métricas
                    st.markdown("### 📊 Dashboard de Resultados")
                    if referencias_sim:
                        sims = [r[1] for r in referencias_sim]
                        c1, c2, c3, c4 = st.columns(4)
                        c1.markdown(f'<div class="metric-container"><div class="metric-value">{len(sims)}</div><div class="metric-label">Referências</div></div>', unsafe_allow_html=True)
                        c2.markdown(f'<div class="metric-container"><div class="metric-value">{max(sims)*100:.1f}%</div><div class="metric-label">Máxima</div></div>', unsafe_allow_html=True)
                        c3.markdown(f'<div class="metric-container"><div class="metric-value">{np.mean(sims)*100:.1f}%</div><div class="metric-label">Média</div></div>', unsafe_allow_html=True)
                        c4.markdown(f'<div class="metric-container"><div class="metric-value">{len([s for s in sims if s > 0.5])}</div><div class="metric-label">Alta Similaridade</div></div>', unsafe_allow_html=True)

                    pdf_bytes = gerar_relatorio_pdf(referencias_sim, nome, email, codigo)
                    st.download_button("📄 Baixar Relatório Completo em PDF", data=pdf_bytes, file_name="relatorio_plagia.pdf", mime="application/pdf")
                    
                    st.session_state["consultas"] += 1
                    # Usar st.experimental_rerun() ou st.rerun() pode causar problemas se não for a última linha.
                    # O Streamlit geralmente atualiza a tela automaticamente após o download.
                    # Se for necessário, descomente a linha abaixo.
                    # st.rerun()

if __name__ == "__main__":
    main()
