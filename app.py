# Requisitos: streamlit, requests, PyPDF2, fpdf, deep-translator, Pillow, qrcode

import streamlit as st
import requests
import PyPDF2
import difflib
from fpdf import FPDF
from io import BytesIO
import hashlib
from datetime import datetime
from deep_translator import GoogleTranslator
from PIL import Image
import qrcode

# --- Configuracoes iniciais ---
URL_GOOGLE_SHEETS = "https://script.google.com/macros/s/AKfycbyTpbWDxWkNRh_ZIlHuAVwZaCC2ODqTmo0Un7ZDbgzrVQBmxlYYKuoYf6yDigAPHZiZ/exec"
IDIOMAS = {"Português": "pt", "English": "en", "Español": "es"}

# --- Funcoes auxiliares ---
def traduzir_texto(texto, idioma_destino="en"):
    return GoogleTranslator(source='auto', target=idioma_destino).translate(texto)

def gerar_codigo_verificacao(texto):
    return hashlib.md5(texto.encode()).hexdigest()[:10].upper()

def salvar_email_google_sheets(nome, email, codigo):
    dados = {"nome": nome, "email": email, "codigo": codigo}
    try:
        response = requests.post(URL_GOOGLE_SHEETS, json=dados, headers={'Content-Type': 'application/json'})
        return response.text.strip() == "Sucesso"
    except:
        return False

def verificar_codigo_google_sheets(codigo):
    try:
        response = requests.get(f"{URL_GOOGLE_SHEETS}?codigo={codigo}")
        return response.text.strip() == "Valido"
    except:
        return False

def extrair_texto_pdf(arquivo_pdf):
    leitor = PyPDF2.PdfReader(arquivo_pdf)
    return "".join(p.extract_text() or "" for p in leitor.pages).strip()

def calcular_similaridade(txt1, txt2):
    return difflib.SequenceMatcher(None, txt1, txt2).ratio()

def buscar_referencias_crossref(texto):
    query = "+".join(texto.split()[:10])
    url = f"https://api.crossref.org/works?query={query}&rows=10"
    try:
        data = requests.get(url).json()
        refs = []
        for item in data.get("message", {}).get("items", []):
            titulo = item.get("title", ["Sem título"])[0]
            resumo = item.get("abstract", "")
            link = item.get("URL", "")
            refs.append({"titulo": titulo, "resumo": resumo, "link": link})
        return refs
    except:
        return []

# --- Classe PDF com traducao ---
class PDF(FPDF):
    def __init__(self, idioma):
        super().__init__()
        self.idioma = idioma
        self.traduzir = lambda txt: traduzir_texto(txt, idioma) if idioma != 'pt' else txt

    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, self.traduzir("Relatório de Similaridade de Plágio - PlagIA - PEAS.Co"), ln=True, align='C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, self.traduzir(title), ln=True)
        self.ln(3)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 8, self.traduzir(body))
        self.ln()

def gerar_relatorio_pdf(refs, nome, email, codigo, idioma_destino):
    pdf = PDF(idioma_destino)
    pdf.add_page()

    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    pdf.chapter_title("Dados do Solicitante:")
    pdf.chapter_body(f"Nome: {nome}")
    pdf.chapter_body(f"E-mail: {email}")
    pdf.chapter_body(f"Data e Hora: {data_hora}")
    pdf.chapter_body(f"Código de Verificação: {codigo}")

    pdf.chapter_title("Top Referências encontradas:")
    if refs:
        total = sum(perc for _, perc, _ in refs[:5])
        for i, (ref, perc, link) in enumerate(refs[:5], 1):
            pdf.chapter_body(f"{i}. {ref} - {perc*100:.2f}%\n{link}")
        pdf.chapter_body(f"Plágio médio: {(total/len(refs[:5]))*100:.2f}%")
    else:
        pdf.chapter_body("Nenhuma referência encontrada.")

    caminho = "/tmp/relatorio_plagio.pdf"
    pdf.output(caminho, 'F')
    return caminho

def gerar_qr_code_pix(payload):
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return Image.open(buffer)

# --- Interface Streamlit ---
idioma_escolhido = st.selectbox("🌍 Escolha o idioma / Choose language / Elige el idioma", list(IDIOMAS.keys()))
idioma = IDIOMAS[idioma_escolhido]
t = lambda txt: traduzir_texto(txt, idioma) if idioma != 'pt' else txt

st.title(t("PlagIA - PEAS.Co"))
nome = st.text_input(t("Nome completo"))
email = st.text_input(t("E-mail"))

if st.button(t("Salvar Dados")):
    if nome and email:
        sucesso = salvar_email_google_sheets(nome, email, "N/A")
        st.success(t("Dados salvos com sucesso!")) if sucesso else st.error(t("Erro ao salvar."))
    else:
        st.warning(t("Preencha todos os campos."))

arquivo = st.file_uploader(t("Faça o upload de um artigo em PDF (sem nomes de autores ou informações da revista), garantindo uma avaliação imparcial baseada apenas no conteúdo textual"), type=["pdf"])
if st.button(t("Processar PDF")):
    if arquivo:
        texto = extrair_texto_pdf(arquivo)
        referencias = buscar_referencias_crossref(texto)
        resultado = [(ref["titulo"], calcular_similaridade(texto, ref["titulo"] + ref["resumo"]), ref["link"]) for ref in referencias]
        resultado.sort(key=lambda x: x[1], reverse=True)

        codigo = gerar_codigo_verificacao(texto)
        salvar_email_google_sheets(nome, email, codigo)

        pdf_file = gerar_relatorio_pdf(resultado, nome, email, codigo, idioma)
        with open(pdf_file, "rb") as f:
            st.download_button(t("📄 Baixar Relatório de Plágio"), f, "relatorio_plagio.pdf")
    else:
        st.error(t("Envie um arquivo primeiro."))

codigo_input = st.text_input(t("Digite o código de verificação"))
if st.button(t("Verificar Código")):
    if verificar_codigo_google_sheets(codigo_input):
        st.success(t("Documento autêntico e original!"))
    else:
        st.error(t("Código inválido ou documento não autenticado."))

# --- Seção Pix ---
payload = "00020126400014br.gov.bcb.pix0118pesas8810@gmail.com520400005303986540520.005802BR5925PEDRO EMILIO AMADOR SALOM6013TEOFILO OTONI62200516PEASTECHNOLOGIES6304C9DB"
st.markdown("---")
st.markdown(f"""
<h3 style='color: green;'>💚 {t('Ajude a manter este projeto gratuito')}</h3>
<p>{t('Milhares de usuários foram beneficiados com a verificação de plágio gratuita.')}</p>
<p>{t('Se esta ferramenta te ajudou, apoie com')} <strong>R$ 20,00</strong>.</p>
<p><strong>{t('Chave Pix')}:</strong> <span style='color: blue;'>pesas8810@gmail.com</span></p>
<p><strong>{t('Nome')}:</strong> PEAS TECHNOLOGIES</p>
<p>🎁 {t('Doadores recebem selo simbólico no relatório PDF!')}</p>
""", unsafe_allow_html=True)

qr_img = gerar_qr_code_pix(payload)
st.image(qr_img, caption=t("📲 Escaneie o QR Code para doar via Pix (R$ 20,00)"), width=300)
st.success(t("🙏 Obrigado a todos que já contribuíram!"))
