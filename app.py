# =============================
# 🍀 Sistema PlagIA - v10.0 - Layout Profissional
# Mantém a lógica original com uma interface completamente redesenhada.
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
import numpy as np # Adicionado para o cálculo da média no relatório

# 🔗 URL da API gerada no Google Sheets
URL_GOOGLE_SHEETS = "https://script.google.com/macros/s/AKfycbyTpbWDxWkNRh_ZIlHuAVwZaCC2ODqTmo0Un7ZDbgzrVQBmxlYYKuoYf6yDigAPHZiZ/exec"

# =============================
# 🎨 Novo CSS para o Layout Profissional
# =============================
@st.cache_data(ttl=3600 )
def load_professional_css() -> str:
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap' );
    
    /* Estilo geral */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    /* Cabeçalho de Destaque */
    .hero-header {
        background: linear-gradient(-45deg, #667eea, #764ba2, #89f7fe, #66a6ff);
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite;
        padding: 2.5rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
    }
    @keyframes gradientShift {
        0% {background-position: 0% 50%}
        50% {background-position: 100% 50%}
        100% {background-position: 0% 50%}
    }

    /* Cards com efeito de vidro */
    .glass-card {
        background: rgba(255, 255, 255, 0.25);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.18);
        padding: 2rem;
        margin-top: 1.5rem;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.15);
    }

    /* Botões */
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    .stButton>button:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    .stDownloadButton>button {
        background-color: #198754;
        color: white;
    }

    /* Estilo da Sidebar */
    .css-1d391kg { /* Seletor para o container da sidebar */
        background-color: #f0f2f6;
    }
    </style>
    """

# =============================
# 📋 Funções Auxiliares (Originais)
# =============================
def salvar_email_google_sheets(nome, email, codigo_verificacao):
    dados = {"nome": nome, "email": email, "codigo": codigo_verificacao, "data": str(date.today())}
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(URL_GOOGLE_SHEETS, json=dados, headers=headers)
        return response.text.strip() == "Sucesso"
    except:
        return False

def verificar_codigo_google_sheets(codigo_digitado):
    try:
        response = requests.get(f"{URL_GOOGLE_SHEETS}?codigo={codigo_digitado}")
        return response.text.strip() == "Valido"
    except:
        return False

def gerar_codigo_verificacao(texto):
    return hashlib.md5(texto.encode('utf-8', 'ignore')).hexdigest()[:10].upper()

def extrair_texto_pdf(arquivo_pdf):
    try:
        leitor_pdf = PyPDF2.PdfReader(arquivo_pdf)
        texto = ""
        for pagina in leitor_pdf.pages:
            texto += pagina.extract_text() or ""
        return texto.strip()
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
        if not linha or len(linha) < 5 or contagem[linha] > 3:
            continue
        if re.match(r"^Página?\s*\d+$", linha, re.IGNORECASE):
            continue
        if "doi" in linha.lower() and len(linha) < 50:
            continue
        if re.search(r"\bResumo\b", linha, re.IGNORECASE):
            capturar = True
        if capturar:
            linhas_filtradas.append(linha)
        if re.search(r"\bRefer[eê]ncias\b|\bBibliografia\b", linha, re.IGNORECASE):
            break
    return " ".join(linhas_filtradas)

def calcular_similaridade(texto1, texto2):
    return difflib.SequenceMatcher(None, texto1, texto2).ratio()

def buscar_referencias_crossref(texto):
    query = "+".join(texto.split()[:10])
    url = f"https://api.crossref.org/works?query={query}&rows=10"
    try:
        data = requests.get(url, timeout=15 ).json()
        referencias = []
        for item in data.get("message", {}).get("items", []):
            titulo = item.get("title", ["Sem título"])[0]
            resumo = item.get("abstract", "")
            link = item.get("URL", "")
            referencias.append({"titulo": titulo, "resumo": resumo, "link": link})
        return referencias
    except Exception as e:
        st.error(f"Erro ao contatar a base de dados: {e}")
        return []

def gerar_qr_code_pix(payload):
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer

# =============================
# 📄 Classe PDF (Original)
# =============================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, self._encode_text("Relatório Técnico de Similaridade Textual - PlagIA | PEAS.Co"), ln=True, align='C')
    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, self._encode_text(title), ln=True)
        self.ln(3)
    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 8, self._encode_text(body))
        self.ln()
    def _encode_text(self, text):
        try:
            return text.encode('latin-1', 'replace').decode('latin-1')
        except UnicodeEncodeError:
            return ''.join(char if ord(char) < 128 else '?' for char in text)

def gerar_relatorio_pdf(referencias_com_similaridade, nome, email, codigo_verificacao):
    pdf = PDF()
    pdf.add_page()
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    pdf.chapter_title("Dados do Solicitante:")
    pdf.chapter_body(f"Nome: {nome}\nE-mail: {email}\nData e Hora: {data_hora}\nCódigo de Verificação: {codigo_verificacao}")
    pdf.chapter_title("Top Referências encontradas:")
    soma_percentual = 0
    refs = referencias_com_similaridade[:5]
    if not refs:
        pdf.chapter_body("Nenhuma referência encontrada.")
    else:
        for i, (ref, perc, link) in enumerate(refs, 1):
            soma_percentual += perc
            pdf.chapter_body(f"{i}. {ref} - {perc*100:.2f}%\n{link}")
        media = (soma_percentual / len(refs)) * 100 if refs else 0
        pdf.chapter_body(f"Plágio médio: {media:.2f}%")
    
    # Retorna os bytes do PDF em vez de salvar em arquivo
    return pdf.output(dest='S').encode('latin-1')

# =============================
# 💻 Interface do Streamlit (Redesenhada)
# =============================
def main():
    st.markdown(load_professional_css(), unsafe_allow_html=True)

    if "consultas" not in st.session_state:
        st.session_state["consultas"] = 0

    # --- Barra Lateral (Sidebar) ---
    with st.sidebar:
        st.markdown("### 📊 Painel de Controle")
        st.info(f"**Consultas restantes:** {4 - st.session_state['consultas']}/4")
        
        st.markdown("---")
        st.markdown("### 🔍 Verificação de Autenticidade")
        codigo_input = st.text_input("Digite o código de verificação")
        if st.button("Verificar Código"):
            if codigo_input:
                if verificar_codigo_google_sheets(codigo_input):
                    st.success("✅ Documento Autêntico!")
                else:
                    st.error("❌ Código inválido.")
            else:
                st.warning("Por favor, insira um código.")
        
        st.markdown("---")
        st.markdown("### 💚 Apoie Este Projeto")
        payload = "00020126400014br.gov.bcb.pix0118pesas8810@gmail.com520400005303986540520.005802BR5925PEDRO EMILIO AMADOR SALOM6013TEOFILO OTONI62200516PEASTECHNOLOGIES6304C9DB"
        qr_buffer = gerar_qr_code_pix(payload)
        st.image(qr_buffer, caption="Pix para PEAS TECHNOLOGIES (R$ 20,00)", width=180)

    # --- Área Principal ---
    st.markdown('<div class="hero-header"><h1>🍀 PlagIA Professional</h1><p>Análise de Similaridade de Documentos com IA</p></div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("1. Informações do Usuário")
        nome = st.text_input("Nome completo")
        email = st.text_input("E-mail")
        
        st.subheader("2. Upload do Documento")
        arquivo_pdf = st.file_uploader("Envie o artigo em PDF", type=["pdf"], label_visibility="collapsed")
        
        if st.button("🚀 Analisar Documento"):
            if not nome or not email:
                st.warning("⚠️ Por favor, preencha seu nome e e-mail.")
            elif not arquivo_pdf:
                st.warning("⚠️ Por favor, envie um arquivo PDF.")
            elif st.session_state["consultas"] >= 4:
                st.error("❌ Limite de 4 consultas atingido. Recarregue a página para reiniciar.")
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
                            sim = calcular_similaridade(texto_usuario, base)
                            referencias_sim.append((ref["titulo"], sim, ref["link"]))
                        
                        referencias_sim.sort(key=lambda x: x[1], reverse=True)
                        codigo = gerar_codigo_verificacao(texto_usuario)
                        salvar_email_google_sheets(nome, email, codigo)
                        
                        st.success(f"✅ Análise concluída! Código de verificação: **{codigo}**")
                        
                        pdf_bytes = gerar_relatorio_pdf(referencias_sim, nome, email, codigo)
                        st.download_button(
                            label="📄 Baixar Relatório de Plágio",
                            data=pdf_bytes,
                            file_name="relatorio_plagio.pdf",
                            mime="application/pdf"
                        )
                        
                        st.session_state["consultas"] += 1
                        st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
