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
st.title("📝 Gerador de Etiquetas Profissional (Lógica PC)")

# --- 1) FUNÇÕES DO SCRIPT 1 (ROTA.PY) ---

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

def extrair_dados_estilo_pc(pdf_file):
    reader = PdfReader(pdf_file)
    texto_corrigido = ""
    for pg in reader.pages:
        t = pg.extract_text() or ""
        # Aplica correção de espaçamento
        t = "\n".join(corrigir_espacamento_linha(l) for l in t.splitlines())
        t = "\n".join(corrigir_espacamento_linha(l) for l in t.splitlines())
        texto_corrigido += t + "\n"
    
    # Divisão em blocos por número de parada
    blocos = []
    bloco_atual = []
    for ln in texto_corrigido.splitlines():
        if re.match(r"^\s*([1-9]\d*)(?:\s+|$)", ln):
            if bloco_atual: blocos.append(" ".join(bloco_atual))
            bloco_atual = [ln]
        else:
            if bloco_atual: bloco_atual.append(ln)
    if bloco_atual: blocos.append(" ".join(bloco_atual))

    dados_finais = []
    for b in blocos:
        unico = " ".join([x.strip() for x in b.splitlines() if x.strip()])
        m_ord = re.match(r"^\s*([1-9]\d*)(?:\s+|$)(.*)$", unico)
        if not m_ord: continue
        
        resto = m_ord.group(2).strip()
        # Remove hora HH:MM e normaliza CEP
        resto = re.sub(r"\b(\d{1,2}:\d{2})\b", "", resto)
        resto = normalizar_ceps(resto)
        
        span = ultimo_cep_span(resto)
        if span:
            end_cep = span[1]
            endereco = resto[:end_cep].strip().rstrip(",")
            nome_nota = resto[end_cep:].strip()
            
            # --- LÓGICA DO SCRIPT 2 (CLIENTES.PY) ---
            # Limpeza de Endereço: Remove número antes do primeiro ' - '
            endereco_limpo = re.sub(r'^(.*?),\s*\d+\s*-', r'\1 -', endereco)
            # Limpeza de Nome: Remove [] mas mantém ()
            nome_limpo = re.sub(r'\s*\[.*?\]', '', nome_nota).strip()
            
            if nome_limpo:
                dados_finais.append({"Nome": nome_limpo, "Endereco": endereco_limpo})
    return dados_finais

# --- 2) FUNÇÃO DO SCRIPT 3 (ETIQUETAS.PY) ---

def criar_pdf_etiquetas(df, pdf_modelo_file):
    largura, altura = 100 * mm, 150 * mm
    modelo_reader = PdfReader(pdf_modelo_file)
    modelo_pagina = modelo_reader.pages[0]
    pdf_final_writer = PdfWriter()

    for _, row in df.iterrows():
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=portrait((largura, altura)))
        
        # Coordenadas exatas do seu PC: 38mm horizontal, 200 vertical (pontos)
        can.setFont("Helvetica-Bold", 9)
        can.drawString(38 * mm, 200, str(row['Nome']))

        can.setFont("Helvetica", 8)
        end = str(row['Endereco'])
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

# --- 3) INTERFACE DO SITE (FLUXO) ---

if 'clientes_data' not in st.session_state:
    st.session_state.clientes_data = None

col1, col2 = st.columns(2)
with col1:
    arq_circuit = st.file_uploader("📁 PDF do Circuit", type="pdf")
with col2:
    arq_modelo = st.file_uploader("🖼️ Modelo Etiqueta.pdf", type="pdf")

if arq_circuit and arq_modelo:
    if st.button("🔍 Extrair Dados (Lógica do PC)", use_container_width=True):
        res = extrair_dados_estilo_pc(arq_circuit)
        if res:
            st.session_state.clientes_data = pd.DataFrame(res)
            st.success(f"Sucesso! Encontradas {len(res)} paradas.")
        else:
            st.error("Não foi possível identificar o padrão de CEP/Endereço no PDF.")

if st.session_state.clientes_data is not None:
    st.info("💡 Revise os nomes e endereços abaixo antes de gerar o PDF.")
    df_editado = st.data_editor(st.session_state.clientes_data, num_rows="dynamic", use_container_width=True)

    if st.button("🚀 Gerar PDF Único de Etiquetas", type="primary", use_container_width=True):
        with st.spinner("Criando arquivo de impressão..."):
            pdf_pronto = criar_pdf_etiquetas(df_editado, arq_modelo)
            st.download_button("📥 BAIXAR ETIQUETAS", data=pdf_pronto, file_name="etiquetas.pdf", mime="application/pdf", use_container_width=True)
