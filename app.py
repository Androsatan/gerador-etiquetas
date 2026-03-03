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
st.title("📝 Gerador de Etiquetas Profissional")

# --- FUNÇÕES DE APOIO (LÓGICA PC) ---

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
            
            nome_etiqueta = re.sub(r'\[.*?\]', '', nome_original).strip()
            endereco_etiqueta = re.sub(r'^(.*?),\s*\d+\s*-', r'\1 -', endereco_original)
            
            if nome_original and nome_original.lower() != "none":
                dados.append({
                    "Nome Original": nome_original, 
                    "Endereco Original": endereco_original,
                    "Nome Etiqueta": nome_etiqueta.upper(),
                    "Endereco Etiqueta": endereco_etiqueta
                })
    return dados

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

# --- INTERFACE ---

# Inicialização do estado
if 'lista_clientes' not in st.session_state:
    st.session_state.lista_clientes = []

# --- 1) ENTRADA MANUAL ---
st.subheader("➕ Adicionar Cliente Manualmente")
with st.expander("Clique para abrir o formulário manual"):
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        m_nome = st.text_input("Nome do Cliente (ex: JOÃO [KK] (2PCT))")
    with col_m2:
        m_end = st.text_input("Endereço Completo (ex: Rua Exemplo, 10, Bairro, Cidade, CEP)")
    
    if st.button("Adicionar à Lista"):
        if m_nome and m_end:
            # Aplica as mesmas regras de limpeza do PDF
            nome_limpo = re.sub(r'\[.*?\]', '', m_nome).strip().upper()
            end_limpo = re.sub(r'^(.*?),\s*\d+\s*-', r'\1 -', m_end)
            
            st.session_state.lista_clientes.append({
                "Nome Original": m_nome,
                "Endereco Original": m_end,
                "Nome Etiqueta": nome_limpo,
                "Endereco Etiqueta": end_limpo
            })
            st.success(f"Cliente {m_nome} adicionado!")
        else:
            st.warning("Preencha nome e endereço.")

st.markdown("---")

# --- 2) UPLOAD DE ARQUIVO ---
st.subheader("📂 Upload Automático (Circuit)")
c1, c2 = st.columns(2)
with c1:
    arq_circuit = st.file_uploader("Subir Circuit.pdf", type="pdf")
with c2:
    arq_modelo = st.file_uploader("Modelo Etiqueta.pdf", type="pdf")

if arq_circuit:
    if st.button("🔍 Extrair Dados do PDF"):
        res = extrair_dados_completos(arq_circuit)
        if res:
            # Adiciona os novos dados à lista existente (sem apagar os manuais)
            st.session_state.lista_clientes.extend(res)
            st.success(f"Mais {len(res)} paradas adicionadas do PDF!")

# --- 3) EXIBIÇÃO E AÇÕES ---
if st.session_state.lista_clientes:
    df_atual = pd.DataFrame(st.session_state.lista_clientes)

    # Botão para limpar tudo
    if st.button("🗑️ Limpar Toda a Lista"):
        st.session_state.lista_clientes = []
        st.rerun()

    st.markdown("---")
    
    # ROTA PARA COPIAR
    st.subheader("📋 Rota para o Entregador (Original)")
    rota_texto = ""
    for c in st.session_state.lista_clientes:
        rota_texto += f"{c['Endereco Original']}\n{c['Nome Original']}\n\n"
    st.code(rota_texto, language="text")

    st.markdown("---")
    
    # EDIÇÃO PARA ETIQUETAS
    st.subheader("🏷️ Conferência para Etiquetas (Sem [])")
    df_editado = st.data_editor(df_atual[["Nome Etiqueta", "Endereco Etiqueta"]], num_rows="dynamic", use_container_width=True)

    if arq_modelo:
        if st.button("🚀 Gerar PDF Único de Etiquetas", type="primary", use_container_width=True):
            with st.spinner("Gerando arquivo..."):
                pdf_pronto = gerar_pdf_etiquetas(df_editado, arq_modelo)
                st.download_button("📥 BAIXAR PDF FINAL", data=pdf_pronto, file_name="etiquetas_finais.pdf", mime="application/pdf", use_container_width=True)
    else:
        st.info("⚠️ Suba o 'Modelo Etiqueta.pdf' para habilitar a geração do PDF.")
