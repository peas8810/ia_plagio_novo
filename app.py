import os
import re
import json
import html
import uuid
import hashlib
from hmac import compare_digest
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
EVIDENCE_THRESHOLD = 0.18


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

    queries = select_queries(chunks)
    candidates, errors = crossref_search(queries)
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
        if any(compare_chunk(chunk, clean_space(f"{s['title']}. {s['abstract']}")) >= EVIDENCE_THRESHOLD for s in sources[:10]):
            covered += 1
    coverage = covered / len(chunks) if chunks else 0.0
    evidence = len([s for s in sources if s["score"] >= EVIDENCE_THRESHOLD])

    if not sources:
        risk = "Inconclusivo"
    elif top >= 0.42 or coverage >= 0.30:
        risk = "Elevado"
    elif top >= 0.24 or coverage >= 0.12:
        risk = "Moderado"
    else:
        risk = "Baixo"

    return {
        "sources": sources[:20],
        "queries_attempted": len(queries),
        "queries_failed": len(errors),
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


def ai_opinion(result, page_count):
    key = secret("OPENAI_API_KEY")
    model = secret("OPENAI_MODEL", "gpt-6.2-sol")
    if not key or OpenAI is None or not result["metrics"]["evidence_count"]:
        return deterministic_opinion(result), False

    payload = {
        "pages": page_count,
        "metrics": result["metrics"],
        "sources": [
            {
                "title": s["title"],
                "doi": s.get("doi"),
                "url": s.get("url"),
                "score_percent": round(s["score"] * 100, 1),
                "evidence_excerpt": s.get("snippet", "")[:350],
            }
            for s in result["sources"][:8] if s["score"] >= EVIDENCE_THRESHOLD
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
    merchant_name = clean_space(strip_accents(merchant_name).encode("ascii", "ignore").decode()).upper()[:25]
    merchant_city = clean_space(strip_accents(merchant_city).encode("ascii", "ignore").decode()).upper()[:15]
    if not merchant_name or not merchant_city:
        return ""
    txid = re.sub(r"[^A-Za-z0-9]", "", txid)[:25] or "PLAGIA"
    account = emv("26", emv("00", "br.gov.bcb.pix") + emv("01", key))
    body = (
        emv("00", "01") + account + emv("52", "0000") + emv("53", "986") +
        emv("54", f"{amount:.2f}") + emv("58", "BR") + emv("59", merchant_name) +
        emv("60", merchant_city) + emv("62", emv("05", txid)) + "6304"
    )
    return body + crc16(body)


def qr_png(payload):
    qr = qrcode.QRCode(box_size=8, border=4)
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


def db(method, table, params=None, payload=None, prefer="return=representation"):
    url = f"{secret('SUPABASE_URL').rstrip('/')}/rest/v1/{table}"
    headers = sb_headers({"Content-Type": "application/json", "Prefer": prefer})
    r = requests.request(method, url, headers=headers, params=params, json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json() if r.text else []


def create_order(report_id, name, email, report_hash):
    return db("POST", "plagia_orders", params={"on_conflict": "report_id"}, payload={
        "report_id": report_id,
        "name": name,
        "email": email,
        "amount": PRICE_BRL,
        "status": "pending",
        "report_hash": report_hash,
    }, prefer="return=representation,resolution=ignore-duplicates")


def get_order(report_id, email):
    params = {"report_id": f"eq.{report_id}", "email": f"eq.{email}", "select": "*", "limit": "1"}
    rows = db("GET", "plagia_orders", params=params)
    return rows[0] if rows else None


def update_order(order, expected_status, changes):
    params = {
        "report_id": f"eq.{order['report_id']}",
        "email": f"eq.{order['email']}",
        "status": f"eq.{expected_status}",
    }
    if expected_status == "review":
        params["payment_reference"] = f"eq.{order['payment_reference']}"
    return db("PATCH", "plagia_orders", params=params, payload=changes)


def upload_report(report_id, pdf_bytes):
    base = secret("SUPABASE_URL").rstrip("/")
    bucket = secret("SUPABASE_REPORT_BUCKET", "plagia-reports")
    url = f"{base}/storage/v1/object/{bucket}/{report_id}.pdf"
    headers = sb_headers({"Content-Type": "application/pdf", "x-upsert": "true"})
    r = requests.post(url, headers=headers, data=pdf_bytes, timeout=TIMEOUT)
    r.raise_for_status()


def download_report(order):
    if order["status"] != "paid":
        raise ValueError("O pedido precisa estar pago para baixar o relatório.")
    report_id = order["report_id"]
    base = secret("SUPABASE_URL").rstrip("/")
    bucket = secret("SUPABASE_REPORT_BUCKET", "plagia-reports")
    url = f"{base}/storage/v1/object/{bucket}/{report_id}.pdf"
    r = requests.get(url, headers=sb_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    pdf_bytes = r.content
    report_hash = order.get("report_hash")
    if report_hash and not compare_digest(hashlib.sha256(pdf_bytes).hexdigest(), report_hash):
        raise ValueError("Falha na verificação de integridade do relatório.")
    return pdf_bytes


def save_report(report_id, name, email, pdf_bytes):
    report_hash = hashlib.sha256(pdf_bytes).hexdigest()
    upload_report(report_id, pdf_bytes)
    create_order(report_id, name, email, report_hash)


class ReportPDF(FPDF):
    def safe(self, text):
        return str(text or "").encode("latin-1", "replace").decode("latin-1")

    def header(self):
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 8, self.safe("PlagIA | Relatório Técnico de Similaridade e Integridade Textual"),
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.cell(0, 5, self.safe("Triagem técnica — não constitui prova isolada de plágio"),
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def section(self, title):
        self.set_font("Helvetica", "B", 11)
        self.multi_cell(0, 6, self.safe(title), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body(self, text):
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 5, self.safe(text), new_x="LMARGIN", new_y="NEXT")
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
        f"Evidências acima do limiar: {m['evidence_count']}\n"
        f"Consultas bibliográficas concluídas: {analysis['queries_attempted'] - analysis['queries_failed']}"
        f"/{analysis['queries_attempted']}"
    )

    pdf.section("3. Parecer técnico")
    pdf.body(opinion)
    pdf.body("Parecer ampliado com agente de IA." if ai_used else "Parecer automatizado por regras; agente de IA não configurado.")

    pdf.section("4. Fontes e evidências principais")
    evidence = [source for source in analysis["sources"] if source["score"] >= EVIDENCE_THRESHOLD]
    if not evidence:
        pdf.body("Nenhuma fonte atingiu o limiar de evidência nesta triagem.")
    for i, s in enumerate(evidence[:10], 1):
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

    out = pdf.output()
    return bytes(out) if isinstance(out, (bytes, bytearray)) else out.encode("latin-1")


def admin_panel():
    password = secret("ADMIN_PASSWORD")
    if not password or not supabase_ready():
        return
    with st.sidebar.expander("Administração"):
        supplied = st.text_input("Senha administrativa", type="password", key="admin_pw")
        if not compare_digest(supplied.encode(), password.encode()):
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
            st.caption(f"Valor esperado: R$ {float(row['amount']):.2f}. Confira valor, recebedor e E2E no extrato.")
            approve = st.button("Confirmar recebimento no extrato", key=f"approve_{row['report_id']}")
            return_pending = st.button("Solicitar correção do E2E", key=f"correct_{row['report_id']}")
            if approve or return_pending:
                changes = (
                    {"status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}
                    if approve else {"status": "pending", "payment_reference": None}
                )
                try:
                    updated = update_order(row, "review", changes)
                    if updated:
                        st.rerun()
                    else:
                        st.info("O pedido mudou. Atualize a página para consultar o estado atual.")
                except requests.RequestException:
                    st.error("Não foi possível atualizar o pedido. Tente novamente.")


def payment_panel(order, widget_prefix):
    report_id = order["report_id"]
    status = order["status"]
    if status == "paid":
        st.success("Pagamento confirmado. Você pode baixar o relatório novamente sem cobrança.")
        if st.button("Preparar download", key=f"{widget_prefix}_prepare_{report_id}"):
            try:
                pdf_bytes = download_report(order)
            except (requests.RequestException, ValueError):
                st.error("Não foi possível carregar o PDF. Tente novamente.")
                return
            st.download_button(
                "Baixar relatório completo em PDF",
                data=pdf_bytes,
                file_name=f"PlagIA_{report_id}.pdf",
                mime="application/pdf",
                type="primary",
                key=f"{widget_prefix}_download_{report_id}",
            )
        return
    if status == "review":
        st.info("Pagamento informado e aguardando conferência administrativa.")
        return
    if status != "pending":
        st.warning("Este pedido foi encerrado.")
        return

    pix_key = secret("PIX_KEY", "")
    payload = pix_payload(
        pix_key, secret("PIX_MERCHANT_NAME", ""), secret("PIX_MERCHANT_CITY", ""),
        float(order["amount"]), report_id,
    )
    if not payload or not secret("ADMIN_PASSWORD"):
        st.info("O pagamento está indisponível no momento. Tente consultar este relatório mais tarde.")
        return

    st.write(f"**Valor para baixar o relatório: R$ {float(order['amount']):.2f}**".replace(".", ","))
    qr_column, code_column = st.columns([1, 2])
    with qr_column:
        st.image(qr_png(payload), caption="QR Code Pix", width=260)
    with code_column:
        st.write("**Pix Copia e Cola**")
        st.code(payload, language=None)
        st.caption("Se já pagou, informe o identificador EndToEnd que consta no comprovante.")
        payment_ref = st.text_input(
            "Identificador EndToEnd (E2E)", key=f"{widget_prefix}_reference_{report_id}",
        ).strip()
        if st.button("Solicitar conferência", key=f"{widget_prefix}_submit_{report_id}"):
            if not re.fullmatch(r"[Ee][0-9]{20}[A-Za-z0-9]{11}", payment_ref):
                st.error("Informe o identificador EndToEnd de 32 caracteres do comprovante Pix.")
                return
            try:
                updated = update_order(order, "pending", {
                    "status": "review",
                    "payment_reference": payment_ref,
                })
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 409:
                    st.error("Este identificador Pix já está vinculado a um pedido.")
                else:
                    st.error("Não foi possível registrar o pagamento. Tente novamente.")
            except requests.RequestException:
                st.error("Não foi possível registrar o pagamento. Tente novamente.")
            else:
                if updated:
                    st.rerun()
                st.info("O pedido mudou. Consulte novamente para ver o estado atual.")


st.set_page_config(
    page_title="PlagIA — Similaridade e Integridade Textual",
    page_icon="🍀",
    layout="wide",
)

st.markdown("""
<style>
.block-container {max-width: 1120px; padding-top: 2rem;}
[data-testid="stMetric"] {border: 1px solid #e8e8e8; border-radius: 14px; padding: 14px;}
</style>
""", unsafe_allow_html=True)

for key, default in {
    "analysis": None,
    "report_id": None,
    "pdf_bytes": None,
    "opinion": None,
    "ai_used": False,
    "report_name": None,
    "report_email": None,
    "report_saved": False,
    "lookup": None,
}.items():
    st.session_state.setdefault(key, default)

admin_panel()

st.title("🍀 PlagIA")
st.caption("Análise e consulta do resultado na página gratuitas. Download do relatório em PDF por R$ 20,00.")

with st.container(border=True):
    st.subheader("Analisar manuscrito")
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Nome completo")
    with c2:
        email = st.text_input("E-mail")
    uploaded = st.file_uploader(f"Arquivo PDF (até {MAX_FILE_MB} MB)", type=["pdf"])
    consent = st.checkbox(
        "Autorizo o uso de trechos do PDF nas consultas ao Crossref e, quando disponível, na elaboração do parecer por IA."
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
                opinion, ai_used = ai_opinion(result, pages)
                pdf_bytes = generate_pdf(
                    name, email, report_id, result, opinion, ai_used, uploaded.name
                )

                st.session_state.analysis = result
                st.session_state.report_id = report_id
                st.session_state.pdf_bytes = pdf_bytes
                st.session_state.opinion = opinion
                st.session_state.ai_used = ai_used
                st.session_state.report_name = name.strip()
                st.session_state.report_email = email.strip().lower()
                st.session_state.report_saved = False
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

    st.info("Os percentuais representam escores internos de similaridade e cobertura da triagem.")
    if result["queries_failed"]:
        st.warning(
            f"Crossref: {result['queries_failed']} de {result['queries_attempted']} consultas falharam. "
            "O resultado reflete apenas as consultas concluídas."
        )

    st.markdown("### Parecer técnico")
    st.write(st.session_state.opinion)
    st.caption(
        "Parecer ampliado por agente de IA."
        if st.session_state.ai_used
        else "Parecer automatizado por regras; a camada de IA pode ser ativada por configuração."
    )

    st.markdown("### Evidências e fontes principais")
    evidence = [source for source in result["sources"] if source["score"] >= EVIDENCE_THRESHOLD]
    if not evidence:
        st.info("Nenhuma fonte atingiu o limiar de evidência nesta triagem.")
    for i, s in enumerate(evidence[:10], 1):
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
    report_id = st.session_state.report_id
    report_email = st.session_state.report_email
    st.caption(f"ID do relatório: {report_id}")

    if not supabase_ready():
        st.info("A análise está disponível na página. A compra do PDF está temporariamente indisponível.")
    else:
        try:
            if not st.session_state.report_saved:
                save_report(
                    report_id, st.session_state.report_name, report_email, st.session_state.pdf_bytes,
                )
                st.session_state.report_saved = True
            order = get_order(report_id, report_email)
        except requests.RequestException:
            st.warning("Não foi possível preparar o pedido. Tente novamente antes de pagar.")
            st.button("Tentar novamente", key="retry_order")
        else:
            if order:
                payment_panel(order, "current")
            else:
                st.session_state.report_saved = False
                st.warning("Pedido indisponível. Tente novamente antes de pagar.")
                st.button("Tentar novamente", key="retry_missing_order")

st.divider()
with st.expander("Já tenho um relatório"):
    st.caption("Informe o ID e o e-mail usados na análise para acompanhar o pagamento ou baixar o PDF.")
    with st.form("lookup_form"):
        rc1, rc2 = st.columns(2)
        with rc1:
            lookup_id = st.text_input("ID do relatório").strip().upper()
        with rc2:
            lookup_email = st.text_input("E-mail usado na análise").strip().lower()
        if st.form_submit_button("Consultar ou atualizar"):
            st.session_state.lookup = None
            if not re.fullmatch(r"[0-9A-F]{16}", lookup_id) or not valid_email(lookup_email):
                st.error("Informe um ID de relatório válido e o e-mail usado na análise.")
            else:
                st.session_state.lookup = (lookup_id, lookup_email)

    if st.session_state.lookup:
        if not supabase_ready():
            st.info("A consulta está temporariamente indisponível.")
        else:
            try:
                lookup_order = get_order(*st.session_state.lookup)
            except requests.RequestException:
                st.error("Não foi possível consultar o relatório. Tente novamente.")
            else:
                if lookup_order:
                    payment_panel(lookup_order, "lookup")
                else:
                    st.error("Relatório não localizado com esses dados.")

st.divider()
st.caption(
    "PlagIA é uma ferramenta de triagem. Similaridade textual não é sinônimo de plágio. "
    "A conclusão editorial deve considerar citações, referências, contexto e avaliação humana."
)
