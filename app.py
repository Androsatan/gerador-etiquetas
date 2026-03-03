import streamlit as st
import re
import pandas as pd
from pypdf import PdfReader, PdfWriter, PageObject
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import mm
from io import BytesIO

# Configuração da Interface
st.set_page_config(page_title="Editor de Etiquetas", page_icon="📝", layout="wide")
st.title("📝 Gerador de Etiquetas e Rota Profissional")

# --- 1) FUNÇÕES DE CORREÇÃO E EXTRAÇÃO (LÓGICA PC) ---

def corrigir_espacamento_linha(linha: str) -> str:
    tokens = linha.split(" ")
    out = []
    i = 0
    PREPS = {"de", "da", "do", "das", "dos", "e", "em", "na", "no", "nas", "nos", "para", "pra", "por", "pelo", "pela", "pelos", "pelas"}
    while i < len(tokens):
        t = tokens[i]
        if i + 1 < len(tokens):
            u = tokens[i + 1]
            if t == "" or u == "":
                out.append(t)
                i += 1
                continue
            if len(t) == 1 and re.match(r"^[A-ZÀ-Ý]$", t) and re.match(r"^[a-zà-ÿ.,;:!?)]+$", u):
                out.append(t + u)
                i += 2
                continue
            if re.match(r"^[A-Za-zÀ-ÿ]{2,}$", t) and re.match(r"^[a-zà-ÿ]{1,4}[.,;:!?)]?$", u) and t.lower() not in PREPS and u.lower() not in PREPS:
                out.append(t + u)
                i += 2
                continue
        out.append(t)
        i += 1
    return " ".join(out)

def normalizar_ceps(texto: str) -> str:
    CEP_TOLERANTE = re.compile(r"(\d{5})\s*-\s*(?:(\d{3})|(\d{2})\s*(\d))")
    def _sub(m: re.Match) -> str:
        base = m.group(1)
        sufixo = m.group(2) if m.group(2) else m.group(3) + m.group(4)
        return f"{base}-{sufixo}"
    return CEP_TOLERANTE.sub(_sub, texto)

def ultimo_cep_span(texto: str):
    last = None
    for m in re.finditer(r"\d{5}-\d{3}", texto):
        last = (m.start(), m.end())
    return last

def extrair_dados_completos(pdf_file):
    reader = PdfReader(pdf_file)
    texto_total = ""
    for pg in reader.pages:
        t = pg.extract_text() or ""
        t = "\n".join(corrigir_espacamento_linha(l) for l in t.splitlines())
        t = "\n".join(corrigir_espacamento_linha(l) for l in t.splitlines())
        texto_total += t + "\n"
    
    blocos = []
    bloco_atual = []
    for ln in texto_total.splitlines():
        if re.match(r"^\s*([1-9]\d*)(?:\s+|$)", ln):
            if bloco_atual: blocos.append(" ".join(bloco_atual))
            bloco_atual = [ln]
        else:
            if bloco_atual: bloco_atual.append(ln)
    if bloco_atual: blocos.append(" ".join(bloco_atual))

    dados = []
    for b in blocos:
        unico = " ".join([x.strip() for x in b.splitlines() if x.strip()])
        m_ord = re.match(r"^\s*([1-9]\d*)(?:\s+|$)(.*)$", unico)
        if not m_ord: continue
        
        resto = m_ord.group(2).strip()
        resto = re.sub(r"\b(\d{1,2}:\d{2})\b", "", resto)
        resto = normalizar_ceps(resto)
        
        span = ultimo_cep_span(resto)
        if span:
            end_cep = span[1]
            endereco_original = resto[:end_cep].strip().rstrip(",")
            nome_original = resto[end_cep:].strip()
            
            # Limpeza para Etiqueta: Remove [] e mantém ()
            nome_etiqueta = re.sub(r'\[.*?\]', '', nome_original).strip()
            # Limpeza para Etiqueta: Remove número da residência antes do ' - '
            endereco_etiqueta = re.sub(r'^(.*?),\s*\d+\s*-', r'\1 -', endereco_original)
            
            if nome_original and nome_original.lower() != "none":
                dados.append({
                    "Nome Original": nome_original, 
                    "Endereco Original": endereco_original,
                    "Nome Etiqueta": nome_etiqueta.upper(),
                    "Endereco Etiqueta": endereco_etiqueta
                })
    return dados

# --- 2) GERAÇÃO DO PDF ---

def gerar_pdf_etiquetas(df, pdf_modelo_file):
    largura, altura = 100 * mm, 150 * mm
    modelo_reader = PdfReader(pdf_modelo_file)
    modelo_pagina = modelo_reader.pages[0]
    pdf_final_writer = PdfWriter()

    for _, row in df.iterrows():
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=portrait((largura, altura)))
        
        can.setFont("Helvetica-Bold", 9)
        can.drawString(38 * mm, 200, str(row['Nome Etiqueta']))

        can.setFont("Helvetica", 8)
        end = str(row['Endereco Etiqueta'])
        if "MG," in end:
            partes = end.split("MG,", 1)
            can.drawString(9 * mm, 184, partes[0].strip() + " MG")
            can.drawString(9 * mm, 175, partes[1].strip())
        else:
            can.drawString(9 * mm, 182, end)
        
        can.save()
        packet.seek(0)
        
        overlay = PdfReader(packet).pages[0]
        saida_pag = PageObject.create_blank_page(width=largura, height=altura)
        saida_pag.merge_page(modelo_pagina)
        saida_pag.merge_page(overlay)
        pdf_final_writer.add_page(saida_pag)

    pdf_saida = BytesIO()
    pdf_final_writer.write(pdf_saida)
    return pdf_saida.getvalue()

# --- 3) INTERFACE ---

if 'clientes_df' not in st.session_state:
    st.session_state.clientes_df = None

c1, c2 = st.columns(2)
with c1:
    arq_circuit = st.file_uploader("📁 PDF do Circuit", type="pdf")
with c2:
    arq_modelo = st.file_uploader("🖼️ Modelo Etiqueta.pdf", type="pdf")

if arq_circuit and arq_modelo:
    if st.button("🔍 Extrair Dados do PDF", use_container_width=True):
        res = extrair_dados_completos(arq_circuit)
        if res:
            st.session_state.clientes_df = pd.DataFrame(res)
            st.success(f"Sucesso! {len(res)} paradas extraídas.")

if st.session_state.clientes_df is not None:
    # --- FUNÇÃO COPIAR ROTA ---
    st.markdown("---")
    rota_texto = ""
    for _, row in st.session_state.clientes_df.iterrows():
        rota_texto += f"{row['Endereco Original']}\n{row['Nome Original']}\n\n"
    
    st.subheader("📋 Rota para o Entregador")
    st.caption("O texto abaixo contém tudo (inclusive [] e ()). Use o botão no canto superior direito do bloco para copiar.")
    st.code(rota_texto, language="text")

    st.markdown("---")
    st.subheader("🏷️ Edição para Etiquetas")
    st.caption("Aqui os [] já foram removidos. O que você editar aqui será o que sairá impresso no PDF.")
    
    # Editor da tabela (apenas campos da etiqueta)
    df_para_editar = st.session_state.clientes_df[["Nome Etiqueta", "Endereco Etiqueta"]]
    df_editado = st.data_editor(df_para_editar, num_rows="dynamic", use_container_width=True)

    if st.button("🚀 Gerar PDF de Etiquetas (Sem [])", type="primary", use_container_width=True):
        with st.spinner("Gerando PDF..."):
            pdf_pronto = gerar_pdf_etiquetas(df_editado, arq_modelo)
            st.download_button("📥 BAIXAR PDF ÚNICO", data=pdf_pronto, file_name="etiquetas_finais.pdf", mime="application/pdf", use_container_width=True)
