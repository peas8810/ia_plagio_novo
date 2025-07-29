# =============================
# 🍀 Sistema PlagIA - Limite Local com Filtro de Texto Inteligente
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

# 🔗 URL da API gerada no Google Sheets
URL_GOOGLE_SHEETS = "https://script.google.com/macros/s/AKfycbyTpbWDxWkNRh_ZIlHuAVwZaCC2ODqTmo0Un7ZDbgzrVQBmxlYYKuoYf6yDigAPHZiZ/exec"

# =============================
# 📋 Funções Auxiliares
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
    return hashlib.md5(texto.encode()).hexdigest()[:10].upper()

def extrair_texto_pdf(arquivo_pdf):
    leitor_pdf = PyPDF2.PdfReader(arquivo_pdf)
    texto = ""
    for pagina in leitor_pdf.pages:
        texto += pagina.extract_text() or ""
    return texto.strip()

def limpar_texto(texto_bruto):
    linhas = texto_bruto.splitlines()
    linhas_filtradas = []
    contagem = Counter(linhas)
    capturar = False
    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
        if len(linha) < 5:
            continue
        if contagem[linha] > 3:
            continue
        if re.match(r"^Página?\s*\d+$", linha, re.IGNORECASE):
            continue
        if "doi" in linha.lower() and len(linha) < 50:
            continue

        # Ativar captura somente após o início do corpo (após "Resumo")
        if re.search(r"\bResumo\b", linha, re.IGNORECASE):
            capturar = True

        if capturar:
            linhas_filtradas.append(linha)

        # Opcional: interromper ao detectar "Referências" ou similar
        if re.search(r"\bRefer[eê]ncias\b|\bBibliografia\b", linha, re.IGNORECASE):
            break

    return " ".join(linhas_filtradas)

def calcular_similaridade(texto1, texto2):
    return difflib.SequenceMatcher(None, texto1, texto2).ratio()

def buscar_referencias_crossref(texto):
    query = "+".join(texto.split()[:10])
    url = f"https://api.crossref.org/works?query={query}&rows=10"
    try:
        data = requests.get(url).json()
        referencias = []
        for item in data.get("message", {}).get("items", []):
            titulo = item.get("title", ["Sem título"])[0]
            resumo = item.get("abstract", "")
            link = item.get("URL", "")
            referencias.append({"titulo": titulo, "resumo": resumo, "link": link})
        return referencias
    except:
        return []

def gerar_qr_code_pix(payload):
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return Image.open(buffer)

# =============================
# 📄 Classe PDF com encode seguro
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
    pdf.chapter_body(f"Nome: {nome}")
    pdf.chapter_body(f"E-mail: {email}")
    pdf.chapter_body(f"Data e Hora: {data_hora}")
    pdf.chapter_body(f"Código de Verificação: {codigo_verificacao}")
    pdf.chapter_title("Top Referências encontradas:")
    soma_percentual = 0
    refs = referencias_com_similaridade[:5]
    if not refs:
        pdf.chapter_body("Nenhuma referência encontrada.")
    else:
        for i, (ref, perc, link) in enumerate(refs, 1):
            soma_percentual += perc
            pdf.chapter_body(f"{i}. {ref} - {perc*100:.2f}%\n{link}")
        media = (soma_percentual / len(refs)) * 100
        pdf.chapter_body(f"Plágio médio: {media:.2f}%")
    caminho = "/tmp/relatorio_plagio.pdf"
    pdf.output(caminho, 'F')
    return caminho

# =============================
# 💻 Interface do Streamlit
# =============================

st.markdown("""
    <style>
    .stButton>button { background-color: #198754; color: white; font-weight: bold; border-radius: 8px; }
    .stTextInput>div>div>input { border: 1px solid #198754; border-radius: 5px; }
    .stDownloadButton button { background-color: #198754; color: white; border-radius: 6px; }
    </style>
""", unsafe_allow_html=True)

st.title("🍀 PlagIA - PEAS.Co")

if "consultas" not in st.session_state:
    st.session_state["consultas"] = 0

st.markdown(f"**Consultas restantes nesta sessão: {4 - st.session_state['consultas']}**")

st.subheader("Registro Obrigatório do Usuário")
nome = st.text_input("Nome completo")
email = st.text_input("E-mail")

arquivo_pdf = st.file_uploader("📄 Envie o artigo em PDF", type=["pdf"])

if st.button("🍀 Processar PDF"):
    if not nome or not email:
        st.warning("⚠️ Por favor, preencha seu nome e e-mail antes de continuar.")
    elif not arquivo_pdf:
        st.warning("⚠️ Por favor, envie um arquivo PDF.")
    elif st.session_state["consultas"] >= 4:
        st.error("❌ Limite de 4 consultas nesta sessão atingido. Recarregue a página para reiniciar ou adquira acesso premium.")
    else:
        texto_extraido = extrair_texto_pdf(arquivo_pdf)
        texto_usuario = limpar_texto(texto_extraido)
        referencias = buscar_referencias_crossref(texto_usuario)
        referencias_sim = []
        for ref in referencias:
            base = ref["titulo"] + " " + ref["resumo"]
            sim = calcular_similaridade(texto_usuario, base)
            referencias_sim.append((ref["titulo"], sim, ref["link"]))
        referencias_sim.sort(key=lambda x: x[1], reverse=True)
        codigo = gerar_codigo_verificacao(texto_usuario)
        salvar_email_google_sheets(nome, email, codigo)
        st.success(f"🍀 Código de verificação gerado: **{codigo}**")
        pdf_path = gerar_relatorio_pdf(referencias_sim, nome, email, codigo)
        with open(pdf_path, "rb") as f:
            st.download_button("📄 Baixar Relatório de Plágio", f, "relatorio_plagio.pdf")
        st.session_state["consultas"] += 1

st.markdown("---")
st.subheader("Verificação de Autenticidade")
codigo_input = st.text_input("Digite o código de verificação")
if st.button("🔍 Verificar Código"):
    if verificar_codigo_google_sheets(codigo_input):
        st.success("✅ Documento Autêntico e Original!")
    else:
        st.error("❌ Código inválido ou documento não autenticado.")

st.markdown("---")

payload = "00020126400014br.gov.bcb.pix0118pesas8810@gmail.com520400005303986540520.005802BR5925PEDRO EMILIO AMADOR SALOM6013TEOFILO OTONI62200516PEASTECHNOLOGIES6304C9DB"

st.markdown(f"""
<h3 style='color: green;'>🍀 Apoie Este Projeto com um Pix!</h3>
<p>Com sua doação de <strong>R$ 20,00</strong>, você ajuda a manter o projeto gratuito e acessível.</p>
<p><strong>Chave Pix:</strong> <span style='color: blue;'>pesas8810@gmail.com</span></p>
<p><strong>Nome do recebedor:</strong> PEAS TECHNOLOGIES</p>
""", unsafe_allow_html=True)

qr_img = gerar_qr_code_pix(payload)
st.image(qr_img, caption="📲 Escaneie o QR Code para doar via Pix (R$ 20,00)", width=300)
st.success("🍀 Obrigado pela sua contribuição! Juntos mantemos este projeto gratuito.")
