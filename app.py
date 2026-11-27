import os
import re
import json
import html
import uuid
import hashlib
import unicodedata
from io import BytesIO
from datetime import datetime, timezone
from difflib import SequenceMatcher

import requests
import streamlit as st
from pypdf import PdfReader
from fpdf import FPDF
import qrcode

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

APP_NAME = "PlagIA"
PRICE_BRL = 20.00
MAX_FILE_MB = 20
TIMEOUT = 20


def secret(name, default=None):
    try:
        return st.secrets[name] if name in st.secrets else os.getenv(name, default)
    except Exception:
        return os.getenv(name, default)


def clean_space(text):
    return re.sub(r"\s+", " ", text or "").strip()


def strip_accents(text):
    return "".join(
        c for c in unicodedata.normalize("NFKD", text or "")
        if not unicodedata.combining(c)
    )


def normalize(text):
    text = strip_accents(text).lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    return clean_space(text)


def valid_email(email):
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", (email or "").strip()))


def extract_pdf(uploaded):
    reader = PdfReader(uploaded)
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    return text.strip(), len(reader.pages)


def clean_document(text):
    text = text.replace("\x00", " ")
    ref = re.search(r"\n\s*(refer[eê]ncias|bibliografia|references)\s*\n", text, flags=re.I)
    if ref:
        text = text[:ref.start()]
    lines = []
    for line in text.splitlines():
        line = clean_space(line)
        if len(line) < 4:
            continue
        if re.fullmatch(r"p[aá]gina\s*\d+", line, flags=re.I):
            continue
        lines.append(line)
    return "\n".join(lines)


def make_chunks(text, min_chars=220, max_chars=700):
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9])", clean_space(text))
    chunks, current = [], ""
    for sentence in sentences:
        if len(sentence.strip()) < 35:
            continue
        candidate = clean_space(current + " " + sentence)
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if len(current) >= min_chars:
                chunks.append(current)
            current = sentence
    if len(current) >= min_chars:
        chunks.append(current)
    return chunks


def select_queries(chunks, limit=6):
    if len(chunks) <= limit:
        return chunks
    idxs = [round(i * (len(chunks) - 1) / (limit - 1)) for i in range(limit)]
    return [chunks[i] for i in sorted(set(idxs))]


def clean_abstract(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return clean_space(value)


def crossref_search(query_chunks):
    endpoint = "https://api.crossref.org/works"
    mailto = secret("CROSSREF_MAILTO", "")
    headers = {"User-Agent": f"{APP_NAME}/2.0" + (f" (mailto:{mailto})" if mailto else "")}
    found, errors = {}, []

    for chunk in query_chunks:
        params = {
            "query.bibliographic": clean_space(chunk)[:650],
            "rows": 5,
            "select": "DOI,title,abstract,URL,author"
        }
        try:
            r = requests.get(endpoint, params=params, headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
            for item in r.json().get("message", {}).get("items", []):
                key = (item.get("DOI") or item.get("URL") or str(uuid.uuid4())).lower()
                authors = []
                for a in item.get("author") or []:
                    name = clean_space(f"{a.get('given', '')} {a.get('family', '')}")
                    if name:
                        authors.append(name)
                found[key] = {
                    "doi": item.get("DOI", ""),
                    "title": " ".join(item.get("title") or ["Sem título"]),
                    "abstract": clean_abstract(item.get("abstract", "")),
                    "url": item.get("URL", ""),
                    "authors": authors[:6],
                }
        except Exception as exc:
            errors.append(str(exc))
    return list(found.values()), errors


def token_jaccard(a, b):
    aa = {x for x in normalize(a).split() if len(x) >= 4}
    bb = {x for x in normalize(b).split() if len(x) >= 4}
    return len(aa & bb) / len(aa | bb) if aa and bb else 0.0


def longest_ratio(a, b):
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return 0.0
    match = SequenceMatcher(None, a, b, autojunk=True).find_longest_match(0, len(a), 0, len(b))
    return match.size / max(1, min(len(a), len(b)))


def compare_chunk(chunk, source_text):
    seq = SequenceMatcher(None, normalize(chunk), normalize(source_text), autojunk=True).ratio()
    jac = token_jaccard(chunk, source_text)
    lng = longest_ratio(chunk, source_text)
    return min(1.0, 0.48 * seq + 0.32 * jac + 0.20 * lng)


def analyze(text):
    chunks = make_chunks(text)
    if not chunks:
        raise ValueError("Texto insuficiente para uma análise segmentada.")

    candidates, errors = crossref_search(select_queries(chunks))
    sources = []
    for src in candidates:
        source_text = clean_space(f"{src['title']}. {src['abstract']}")
        if len(source_text) < 25:
            continue
        best_score, best_snippet = 0.0, ""
        for chunk in chunks:
            score = compare_chunk(chunk, source_text)
            if score > best_score:
                best_score, best_snippet = score, chunk[:520]
        sources.append({**src, "score": best_score, "snippet": best_snippet})

    sources.sort(key=lambda x: x["score"], reverse=True)
    top = sources[0]["score"] if sources else 0.0

    covered = 0
    for chunk in chunks:
        if any(compare_chunk(chunk, clean_space(f"{s['title']}. {s['abstract']}")) >= 0.18 for s in sources[:10]):
            covered += 1
    coverage = covered / len(chunks) if chunks else 0.0
    evidence = len([s for s in sources if s["score"] >= 0.18])

    if top >= 0.42 or coverage >= 0.30:
        risk = "Elevado"
    elif top >= 0.24 or coverage >= 0.12:
        risk = "Moderado"
    else:
        risk = "Baixo"

    return {
        "sources": sources[:20],
        "errors": errors,
        "metrics": {
            "risk": risk,
            "top_similarity": round(top * 100, 1),
            "coverage": round(coverage * 100, 1),
            "sources_checked": len(sources),
            "evidence_count": evidence,
            "chunks": len(chunks),
        }
    }


def deterministic_opinion(result):
    m = result["metrics"]
    if not result["sources"]:
        return (
            "A triagem não recuperou fontes bibliográficas suficientes para uma comparação robusta. "
            "Isso não comprova originalidade; apenas indica baixa evidência nas fontes consultadas."
        )
    return (
        f"A triagem classificou os indícios de similaridade como {m['risk'].lower()}. "
        f"A maior proximidade encontrada foi de {m['top_similarity']:.1f}% no escore interno e "
        f"{m['coverage']:.1f}% dos trechos apresentaram evidência acima do limiar. "
        "Esses valores não equivalem a percentual de plágio. A interpretação final deve conferir "
        "contexto, citações, paráfrases e referências do manuscrito."
    )


def ai_opinion(result, metadata):
    key = secret("OPENAI_API_KEY")
    model = secret("OPENAI_MODEL", "gpt-6.2-sol")
    if not key or OpenAI is None:
        return deterministic_opinion(result), False

    payload = {
        "document": metadata,
        "metrics": result["metrics"],
        "sources": [
            {
                "title": s["title"],
                "doi": s.get("doi"),
                "url": s.get("url"),
                "score_percent": round(s["score"] * 100, 1),
                "evidence_excerpt": s.get("snippet", "")[:350],
            }
            for s in result["sources"][:8]
        ],
    }
    instructions = (
        "Você é o agente técnico do PlagIA. Gere um parecer em português do Brasil com quatro parágrafos curtos: "
        "síntese do risco, evidências relevantes, alertas sobre citação/paráfrase e recomendação editorial. "
        "Nunca declare que houve plágio, não converta o escore em percentual de plágio, não invente fontes e use apenas os dados fornecidos. "
        "Diferencie similaridade textual, coincidência temática e plágio."
    )
    try:
        client = OpenAI(api_key=key)
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=json.dumps(payload, ensure_ascii=False),
        )
        return clean_space(response.output_text) or deterministic_opinion(result), True
    except Exception:
        return deterministic_opinion(result), False


def crc16(payload):
    crc = 0xFFFF
    for byte in payload.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def emv(tag, value):
    return f"{tag}{len(value):02d}{value}"


def pix_payload(key, merchant_name, merchant_city, amount, txid):
    key = clean_space(key)
    if not key:
        return ""
    merchant_name = strip_accents(merchant_name).upper()[:25] or "PLAGIA"
    merchant_city = strip_accents(merchant_city).upper()[:15] or "BRASIL"
    txid = re.sub(r"[^A-Za-z0-9]", "", txid)[:25] or "PLAGIA"
    account = emv("26", emv("00", "br.gov.bcb.pix") + emv("01", key))
    body = (
        emv("00", "01") + account + emv("52", "0000") + emv("53", "986") +
        emv("54", f"{amount:.2f}") + emv("58", "BR") + emv("59", merchant_name) +
        emv("60", merchant_city) + emv("62", emv("05", txid)) + "6304"
    )
    return body + crc16(body)


def qr_png(payload):
    qr = qrcode.QRCode(box_size=8, border=3)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def supabase_ready():
    return bool(secret("SUPABASE_URL") and secret("SUPABASE_SERVICE_ROLE_KEY"))


def sb_headers(extra=None):
    key = secret("SUPABASE_SERVICE_ROLE_KEY")
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    h.update(extra or {})
    return h


def db(method, table, params=None, payload=None):
    url = f"{secret('SUPABASE_URL').rstrip('/')}/rest/v1/{table}"
    headers = sb_headers({"Content-Type": "application/json", "Prefer": "return=representation"})
    r = requests.request(method, url, headers=headers, params=params, json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json() if r.text else []


def create_order(report_id, name, email, report_hash):
    return db("POST", "plagia_orders", payload={
        "report_id": report_id,
        "name": name,
        "email": email,
        "amount": PRICE_BRL,
        "status": "pending",
        "report_hash": report_hash,
    })


def get_order(report_id, email=None):
    params = {"report_id": f"eq.{report_id}", "select": "*", "limit": "1"}
    if email:
        params["email"] = f"eq.{email}"
    rows = db("GET", "plagia_orders", params=params)
    return rows[0] if rows else None


def update_order(report_id, changes):
    return db("PATCH", "plagia_orders", params={"report_id": f"eq.{report_id}"}, payload=changes)


def upload_report(report_id, pdf_bytes):
    base = secret("SUPABASE_URL").rstrip("/")
    bucket = secret("SUPABASE_REPORT_BUCKET", "plagia-reports")
    url = f"{base}/storage/v1/object/{bucket}/{report_id}.pdf"
    headers = sb_headers({"Content-Type": "application/pdf", "x-upsert": "true"})
    r = requests.post(url, headers=headers, data=pdf_bytes, timeout=TIMEOUT)
    r.raise_for_status()


def download_report(report_id):
    base = secret("SUPABASE_URL").rstrip("/")
    bucket = secret("SUPABASE_REPORT_BUCKET", "plagia-reports")
    url = f"{base}/storage/v1/object/{bucket}/{report_id}.pdf"
    r = requests.get(url, headers=sb_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.content


class ReportPDF(FPDF):
    def safe(self, text):
        return str(text or "").encode("latin-1", "replace").decode("latin-1")

    def header(self):
        self.set_font("Arial", "B", 15)
        self.cell(0, 8, self.safe("PlagIA | Relatório Técnico de Similaridade e Integridade Textual"), 0, 1, "C")
        self.set_font("Arial", "", 8)
        self.cell(0, 5, self.safe("Triagem técnica — não constitui prova isolada de plágio"), 0, 1, "C")
        self.ln(3)

    def section(self, title):
        self.set_font("Arial", "B", 11)
        self.multi_cell(0, 6, self.safe(title))
        self.ln(1)

    def body(self, text):
        self.set_font("Arial", "", 9)
        self.multi_cell(0, 5, self.safe(text))
        self.ln(1)


def generate_pdf(name, email, report_id, analysis, opinion, ai_used, filename):
    pdf = ReportPDF()
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    m = analysis["metrics"]

    pdf.section("1. Identificação")
    pdf.body(
        f"Solicitante: {name}\nE-mail: {email}\nArquivo: {filename}\n"
        f"Relatório: {report_id}\nData: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )

    pdf.section("2. Resumo executivo")
    pdf.body(
        f"Classificação dos indícios: {m['risk']}\n"
        f"Maior escore interno: {m['top_similarity']:.1f}%\n"
        f"Cobertura de trechos com evidência: {m['coverage']:.1f}%\n"
        f"Fontes comparadas: {m['sources_checked']}\n"
        f"Evidências acima do limiar: {m['evidence_count']}"
    )

    pdf.section("3. Parecer técnico")
    pdf.body(opinion)
    pdf.body("Parecer ampliado com agente de IA." if ai_used else "Parecer automatizado por regras; agente de IA não configurado.")

    pdf.section("4. Fontes e evidências principais")
    if not analysis["sources"]:
        pdf.body("Nenhuma fonte bibliográfica com dados suficientes foi recuperada.")
    for i, s in enumerate(analysis["sources"][:10], 1):
        pdf.body(
            f"{i}. {s['title']}\nDOI: {s.get('doi') or 'não informado'}\n"
            f"Escore interno: {s['score']*100:.1f}%\nFonte: {s.get('url') or 'não informado'}\n"
            f"Trecho relacionado: {s.get('snippet', '')[:420]}"
        )

    pdf.section("5. Metodologia e limitações")
    pdf.body(
        "O PlagIA segmenta o texto, consulta metadados bibliográficos e compara trechos com títulos e resumos recuperados. "
        "O escore combina similaridade sequencial, interseção lexical e maior correspondência contínua. "
        "A cobertura consultada não representa toda a internet nem todas as bases de texto completo. "
        "Os escores não equivalem a percentual de plágio e devem ser avaliados juntamente com citações, referências e contexto."
    )

    pdf.section("6. Validação")
    digest = hashlib.sha256((report_id + email).encode()).hexdigest()[:16].upper()
    pdf.body(f"Código de integridade: {digest}\nID do relatório: {report_id}")

    out = pdf.output(dest="S")
    return bytes(out) if isinstance(out, (bytes, bytearray)) else out.encode("latin-1")


def admin_panel():
    password = secret("ADMIN_PASSWORD")
    if not password or not supabase_ready():
        return
    with st.sidebar.expander("Administração"):
        supplied = st.text_input("Senha administrativa", type="password", key="admin_pw")
        if supplied != password:
            return
        try:
            rows = db("GET", "plagia_orders", params={
                "status": "eq.review",
                "select": "*",
                "order": "created_at.asc",
                "limit": "30",
            })
        except Exception as exc:
            st.error(f"Falha ao consultar pedidos: {exc}")
            return

        if not rows:
            st.caption("Nenhum pagamento aguardando revisão.")
        for row in rows:
            st.write(f"**{row.get('name')}** — {row.get('email')}")
            st.caption(
                f"Relatório {row.get('report_id')} | "
                f"E2E/ID: {row.get('payment_reference') or 'não informado'}"
            )
            if st.button("Marcar como pago", key=f"approve_{row.get('report_id')}"):
                update_order(row["report_id"], {
                    "status": "paid",
                    "paid_at": datetime.now(timezone.utc).isoformat(),
                })
                st.rerun()


st.set_page_config(
    page_title="PlagIA — Similaridade e Integridade Textual",
    page_icon="🍀",
    layout="wide",
)

st.markdown("""
<style>
.block-container {max-width: 1120px; padding-top: 2rem;}
[data-testid="stMetric"] {border: 1px solid #e8e8e8; border-radius: 14px; padding: 14px;}
.paywall {border: 1px solid #d8e7dc; border-radius: 16px; padding: 18px; background: #fbfffc;}
</style>
""", unsafe_allow_html=True)

for key, default in {
    "analysis": None,
    "report_id": None,
    "pdf_bytes": None,
    "opinion": None,
    "ai_used": False,
}.items():
    st.session_state.setdefault(key, default)

admin_panel()

st.title("🍀 PlagIA")
st.caption("Triagem técnica de similaridade e integridade textual com relatório profissional e rastreável.")

with st.container(border=True):
    st.subheader("Analisar manuscrito")
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Nome completo")
    with c2:
        email = st.text_input("E-mail")
    uploaded = st.file_uploader(f"Arquivo PDF (até {MAX_FILE_MB} MB)", type=["pdf"])
    consent = st.checkbox(
        "Autorizo o processamento do texto para realizar consultas bibliográficas necessárias à análise."
    )
    process = st.button("Analisar documento", type="primary", use_container_width=True)

if process:
    st.session_state.analysis = None
    if not name.strip():
        st.error("Informe o nome completo.")
    elif not valid_email(email):
        st.error("Informe um e-mail válido.")
    elif uploaded is None:
        st.error("Envie um arquivo PDF.")
    elif uploaded.size > MAX_FILE_MB * 1024 * 1024:
        st.error(f"O arquivo excede {MAX_FILE_MB} MB.")
    elif not consent:
        st.error("É necessário autorizar o processamento para iniciar a análise.")
    else:
        with st.spinner("Extraindo texto, consultando fontes e preparando o parecer..."):
            try:
                raw_text, pages = extract_pdf(uploaded)
                text = clean_document(raw_text)
                if len(text) < 1200:
                    raise ValueError(
                        "O PDF contém pouco texto extraível. PDFs escaneados precisam de OCR antes da análise."
                    )

                result = analyze(text)
                report_id = uuid.uuid4().hex[:16].upper()
                opinion, ai_used = ai_opinion(result, {
                    "name": name,
                    "email": email,
                    "pages": pages,
                    "filename": uploaded.name,
                })
                pdf_bytes = generate_pdf(
                    name, email, report_id, result, opinion, ai_used, uploaded.name
                )

                st.session_state.analysis = result
                st.session_state.report_id = report_id
                st.session_state.pdf_bytes = pdf_bytes
                st.session_state.opinion = opinion
                st.session_state.ai_used = ai_used

                if supabase_ready():
                    create_order(
                        report_id,
                        name.strip(),
                        email.strip().lower(),
                        hashlib.sha256(pdf_bytes).hexdigest(),
                    )
                    upload_report(report_id, pdf_bytes)
            except Exception as exc:
                st.error(f"Não foi possível concluir a análise: {exc}")

if st.session_state.analysis:
    result = st.session_state.analysis
    m = result["metrics"]

    st.divider()
    st.subheader("Resultado na página")
    a, b, c, d = st.columns(4)
    a.metric("Indício geral", m["risk"])
    b.metric("Maior escore", f"{m['top_similarity']:.1f}%")
    c.metric("Cobertura", f"{m['coverage']:.1f}%")
    d.metric("Fontes comparadas", m["sources_checked"])

    st.info("Os percentuais são escores internos de similaridade, não percentual de plágio.")

    st.markdown("### Parecer técnico")
    st.write(st.session_state.opinion)
    st.caption(
        "Parecer ampliado por agente de IA."
        if st.session_state.ai_used
        else "Parecer automatizado por regras; a camada de IA pode ser ativada por configuração."
    )

    st.markdown("### Evidências e fontes principais")
    if not result["sources"]:
        st.warning("Nenhuma fonte com dados suficientes foi recuperada nesta triagem.")
    for i, s in enumerate(result["sources"][:8], 1):
        with st.expander(f"{i}. {s['title'][:110]} — {s['score']*100:.1f}%"):
            st.write(f"**DOI:** {s.get('doi') or 'Não informado'}")
            if s.get("authors"):
                st.write("**Autores:** " + ", ".join(s["authors"]))
            if s.get("url"):
                st.markdown(f"**Fonte:** {s['url']}")
            st.write("**Trecho relacionado do manuscrito:**")
            st.caption(s.get("snippet", ""))

    st.markdown("### Metodologia")
    st.write(
        "O documento é segmentado em trechos distribuídos ao longo do manuscrito. "
        "O sistema consulta registros bibliográficos, deduplica fontes e calcula um escore composto de proximidade textual. "
        "O relatório apresenta evidências, fontes e limitações para revisão humana."
    )

    st.markdown("### Relatório profissional em PDF")
    st.markdown('<div class="paywall">', unsafe_allow_html=True)
    st.write("**Valor para baixar o relatório completo: R$ 20,00**")
    st.caption(f"ID do relatório: {st.session_state.report_id}")

    pix_key = secret("PIX_KEY", "")
    merchant_name = secret("PIX_MERCHANT_NAME", "PLAGIA")
    merchant_city = secret("PIX_MERCHANT_CITY", "TEOFILO OTONI")

    if not pix_key:
        st.warning(
            "O PIX ainda não foi configurado pelo administrador. "
            "O relatório permanece bloqueado para download."
        )
    elif not supabase_ready():
        st.warning(
            "O armazenamento de pagamentos ainda não foi configurado. "
            "Para não liberar relatórios sem confirmação, o download permanece bloqueado."
        )
    else:
        payload = pix_payload(
            pix_key,
            merchant_name,
            merchant_city,
            PRICE_BRL,
            st.session_state.report_id,
        )
        p1, p2 = st.columns([1, 2])
        with p1:
            st.image(qr_png(payload), caption="PIX — R$ 20,00", width=260)
        with p2:
            st.write("**PIX copia e cola**")
            st.code(payload, language=None)
            st.write(f"**Chave PIX:** {pix_key}")
            payment_ref = st.text_input(
                "Identificador da transação (E2E/ID do comprovante)",
                key="payment_ref",
            )

            if st.button("Enviei o PIX — solicitar liberação", use_container_width=True):
                if len(clean_space(payment_ref)) < 6:
                    st.error("Informe o identificador da transação para permitir a conferência.")
                else:
                    update_order(st.session_state.report_id, {
                        "status": "review",
                        "payment_reference": clean_space(payment_ref)[:120],
                    })
                    st.success("Pagamento enviado para conferência administrativa.")

            if st.button("Verificar pagamento e liberar PDF", use_container_width=True):
                order = get_order(st.session_state.report_id, email.strip().lower())
                if order and order.get("status") == "paid":
                    st.session_state.pdf_bytes = download_report(st.session_state.report_id)
                    st.success("Pagamento confirmado. Relatório liberado.")
                elif order and order.get("status") == "review":
                    st.info("Pagamento aguardando conferência.")
                else:
                    st.warning("Pagamento ainda não confirmado.")

            try:
                order = get_order(st.session_state.report_id, email.strip().lower())
            except Exception:
                order = None

            if order and order.get("status") == "paid":
                st.download_button(
                    "Baixar relatório completo em PDF",
                    data=st.session_state.pdf_bytes or download_report(st.session_state.report_id),
                    file_name=f"PlagIA_{st.session_state.report_id}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()
st.caption(
    "PlagIA é uma ferramenta de triagem. Similaridade textual não é sinônimo de plágio. "
    "A conclusão editorial deve considerar citações, referências, contexto e avaliação humana."
)
