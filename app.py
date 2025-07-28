import streamlit as st
import requests
import PyPDF2
import difflib
from fpdf import FPDF
from io import BytesIO
import hashlib
from datetime import datetime  # Importação para registrar data e hora

# 🔗 URL da API gerada no Google Sheets
URL_GOOGLE_SHEETS = "https://script.google.com/macros/s/AKfycbyTpbWDxWkNRh_ZIlHuAVwZaCC2ODqTmo0Un7ZDbgzrVQBmxlYYKuoYf6yDigAPHZiZ/exec"

# =============================
# 📋 Função para Salvar E-mails e Código de Verificação no Google Sheets
# =============================
def salvar_email_google_sheets(nome, email, codigo_verificacao):
    dados = {
        "nome": nome,
        "email": email,
        "codigo": codigo_verificacao
    }
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(URL_GOOGLE_SHEETS, json=dados, headers=headers)

        if response.text.strip() == "Sucesso":
            st.success("✅ E-mail, nome e código registrados com sucesso!")
        else:
            st.error(f"❌ Erro ao salvar dados no Google Sheets: {response.text}")
    except Exception as e:
        st.error(f"❌ Erro na conexão com o Google Sheets: {e}")

# =============================
# 🔎 Função para Verificar Código de Verificação na Planilha
# =============================
def verificar_codigo_google_sheets(codigo_digitado):
    try:
        response = requests.get(f"{URL_GOOGLE_SHEETS}?codigo={codigo_digitado}")
        if response.text.strip() == "Valido":
            return True
        else:
            return False
    except Exception as e:
        st.error(f"❌ Erro na conexão com o Google Sheets: {e}")
        return False

# =============================
# 🔐 Função para Gerar Código de Verificação
# =============================
def gerar_codigo_verificacao(texto):
    return hashlib.md5(texto.encode()).hexdigest()[:10].upper()

# =============================
# 📝 Função para Extrair Texto do PDF
# =============================
def extrair_texto_pdf(arquivo_pdf):
    leitor_pdf = PyPDF2.PdfReader(arquivo_pdf)
    texto = ""
    for pagina in leitor_pdf.pages:
        texto += pagina.extract_text() or ""
    return texto.strip()

# =============================
# 📊 Função para Calcular Similaridade
# =============================
def calcular_similaridade(texto1, texto2):
    seq_matcher = difflib.SequenceMatcher(None, texto1, texto2)
    return seq_matcher.ratio()

# =============================
# 🔎 Função para Buscar Artigos na API CrossRef
# =============================
def buscar_referencias_crossref(texto):
    query = "+".join(texto.split()[:10])  
    url = f"https://api.crossref.org/works?query={query}&rows=10"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao acessar a API da CrossRef: {e}")
        return []

    referencias = []
    for item in data.get("message", {}).get("items", []):
        titulo = item.get("title", ["Título não disponível"])[0]
        resumo = item.get("abstract", "")
        link = item.get("URL", "Link não disponível")
        referencias.append({"titulo": titulo, "resumo": resumo, "link": link})

    return referencias

# =============================
# 📄 Classe para Gerar Relatório PDF Personalizado
# =============================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, "Relatório de Similaridade de Plágio - PlagIA - PEAS.Co", ln=True, align='C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, self._encode_text(title), ln=True)
        self.ln(3)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 8, self._encode_text(body))
        self.ln()

    # 🔎 Função para corrigir acentuação e caracteres especiais
    def _encode_text(self, text):
        try:
            return text.encode('latin-1', 'replace').decode('latin-1')
        except UnicodeEncodeError:
            return ''.join(char if ord(char) < 128 else '?' for char in text)

def gerar_relatorio_pdf(referencias_com_similaridade, nome, email, codigo_verificacao):
    pdf = PDF()
    pdf.add_page()

    # Adicionando os dados do usuário no PDF
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    pdf.chapter_title("Dados do Solicitante:")
    pdf.chapter_body(f"Nome: {nome}")
    pdf.chapter_body(f"E-mail: {email}")
    pdf.chapter_body(f"Data e Hora: {data_hora}")
    pdf.chapter_body(f"Código de Verificação (Link para inserir o código e conferir: https://iaplagio-wtwg4f3x2ejse4rspbqe2s.streamlit.app/): {codigo_verificacao}")
    pdf.chapter_body(f"Este relatório foi gerado com o apoio de um colaborador da PEAS.Co - (")
    
    # Referências encontradas
    pdf.chapter_title("Top Referências encontradas:")
    soma_percentual = 0
    # Considera no máximo 5 referências, mas se houver menos, divide pelo número real
    refs_selecionadas = referencias_com_similaridade[:5]
    num_refs = len(refs_selecionadas)
    if num_refs == 0:
        pdf.chapter_body("Nenhuma referência encontrada.")
    else:
        for i, (ref, perc, link) in enumerate(refs_selecionadas, 1):
            soma_percentual += perc
            pdf.chapter_body(f"{i}. {ref} - {perc*100:.2f}%\n{link}")
        plagio_medio = (soma_percentual / num_refs) * 100
        pdf.chapter_body(f"Plágio médio: {plagio_medio:.2f}%")

    pdf_file_path = "/tmp/relatorio_plagio.pdf"
    pdf.output(pdf_file_path, 'F')
      
    return pdf_file_path

# =============================
# 💻 Interface do Streamlit
# =============================
if __name__ == "__main__":
    st.title("PlagIA - PEAS.Co")
    
    # --- Registro de Usuário ---
    st.subheader("📋 Registro de Usuário - Apenas para validação")
    nome = st.text_input("Nome completo")
    email = st.text_input("E-mail")

    if st.button("Salvar Dados"):
        if nome and email:
            salvar_email_google_sheets(nome, email, "N/A")
        else:
            st.warning("⚠️ Por favor, preencha todos os campos.")

    # --- Upload e Processamento do PDF ---
    arquivo_pdf = st.file_uploader("Faça o upload de um artigo em PDF (sem nomes de autores ou informações da revista), garantindo uma avaliação imparcial baseada apenas no conteúdo textual", type=["pdf"])

    if st.button("Processar PDF"):
        if arquivo_pdf is not None:
            texto_usuario = extrair_texto_pdf(arquivo_pdf)
            referencias = buscar_referencias_crossref(texto_usuario)

            referencias_com_similaridade = []
            for ref in referencias:
                texto_base = ref["titulo"] + " " + ref["resumo"]
                link = ref["link"]
                similaridade = calcular_similaridade(texto_usuario, texto_base)
                referencias_com_similaridade.append((ref["titulo"], similaridade, link))

            referencias_com_similaridade.sort(key=lambda x: x[1], reverse=True)

            if referencias_com_similaridade:
                codigo_verificacao = gerar_codigo_verificacao(texto_usuario)
                salvar_email_google_sheets(nome, email, codigo_verificacao)
                st.success(f"Código de verificação gerado: **{codigo_verificacao}**")

                # Gerar e exibir link para download do relatório
                pdf_file = gerar_relatorio_pdf(referencias_com_similaridade, nome, email, codigo_verificacao)
                with open(pdf_file, "rb") as f:
                    st.download_button("📄 Baixar Relatório de Plágio", f, "relatorio_plagio.pdf")
            else:
                st.warning("Nenhuma referência encontrada.")
        else:
            st.error("Por favor, carregue um arquivo PDF.")

    # --- Texto Justificado ---
    st.markdown(
        """
        <div style="text-align: justify;">
        Powered By - PEAS.Co
        </div>
        """, 
        unsafe_allow_html=True
    )

    # --- Verificação de Código ---
    st.header("Verificar Autenticidade")
    codigo_digitado = st.text_input("Digite o código de verificação:")

    if st.button("Verificar Código"):
        if verificar_codigo_google_sheets(codigo_digitado):
            st.success("✅ Documento Autêntico e Original!")
        else:
            st.error("❌ Código inválido ou documento falsificado.")

def gerar_qr_code_pix(payload):
    import qrcode
    from io import BytesIO
    from PIL import Image

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
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

# --- Payload Pix Oficial ---
payload = "00020126400014br.gov.bcb.pix0118peas8810@gmail.com520400005303986540520.005802BR5925PEDRO EMILIO AMADOR SALOM6013TEOFILO OTONI62200516PEASTECHNOLOGIES6304C9DB"

# --- Seção de Doação via Pix ---
st.markdown("---")
st.markdown(
    """
    <h3 style='color: green;'>💚 Apoie Este Projeto com um Pix!</h3>
    <p>🎁 Você pode manter este projeto gratuito para milhares de estudantes e pesquisadores. Com apenas R$ 20,00, você ajuda a manter os servidores, APIs e evolução da ferramenta.
É como pagar um café para quem te ajudou com horas de leitura. 💚 <strong>R$ 20,00</strong>.</p>
    <p><strong>Chave Pix:</strong> <span style='color: blue;'>pesas8810@gmail.com</span></p>
    <p><strong>Nome do recebedor:</strong> PEAS TECHNOLOGIES</p>
    """,
    unsafe_allow_html=True
)

qr_img = gerar_qr_code_pix(payload)
st.image(qr_img, caption="📲 Escaneie o QR Code para doar via Pix (R$ 20,00)", width=300)

st.success("🙏 Obrigado a todos que já contribuíram! Sua ajuda mantém este projeto vivo!")
