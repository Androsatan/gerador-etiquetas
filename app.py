import streamlit as st
import re
import pandas as pd
from pypdf import PdfReader, PdfWriter, PageObject
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import mm
from io import BytesIO

# Configuração da Interface
st.set_page_config(page_title="Sara Lin - Editor de Etiquetas", page_icon="📝", layout="wide")
st.title("📝 Gerador de Etiquetas com Conferência")
st.write("1. Suba os arquivos | 2. Confira e edite os dados | 3. Gere o PDF final")

# --- FUNÇÕES DE APOIO ---

def extrair_dados_do_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    texto = ""
    for page in reader.pages:
        texto += page.extract_text() or ""
    
    # Regex baseada na sua estrutura do Circuit
    pattern = re.compile(r"(\d+)\s+(.*?)\s+(\d{5}-\d{3})(.*?)(?=\d+\s+|$)", re.DOTALL)
    matches = pattern.findall(texto)
    
    dados = []
    for m in matches:
        endereco_bruto = f"{m[1]} {m[2]}".strip()
        nota = m[3].strip()
        
        # Lógica de limpeza original (2CLIENTES)
        end_limpo = re.sub(r'^(.*?),\s*\d+\s*-', r'\1 -', endereco_bruto)
        nome_limpo = re.sub(r'\s*\[.*?\]', '', nota).strip()
        
        dados.append({"Nome": nome_limpo, "Endereco": end_limpo})
    return dados

def criar_pdf_etiquetas(df, pdf_modelo):
    modelo_reader = PdfReader(pdf_modelo)
    modelo_pagina = modelo_reader.pages[0]
    largura, altura = 100 * mm, 150 * mm
    pdf_final_writer = PdfWriter()

    for _, row in df.iterrows():
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=portrait((largura, altura)))
        
        # Nome
        can.setFont("Helvetica-Bold", 9)
        can.drawString(38 * mm, 70.5 * mm, str(row['Nome']))
        
        # Endereço
        can.setFont("Helvetica", 8)
        end = str(row['Endereco'])
        if "MG," in end:
            partes = end.split("MG,", 1)
            linha1 = partes[0].strip() + " MG"
            linha2 = partes[1].strip()
            can.drawString(9 * mm, 65 * mm, linha1)
            can.drawString(9 * mm, 62 * mm, linha2)
        else:
            can.drawString(9 * mm, 64 * mm, end)
        
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

# --- FLUXO DO SITE ---

# Inicializa o estado se não existir
if 'dados_extraidos' not in st.session_state:
    st.session_state.dados_extraidos = None

col1, col2 = st.columns(2)
with col1:
    arq_circuit = st.file_uploader("📁 PDF do Circuit", type="pdf")
with col2:
    arq_modelo = st.file_uploader("🖼️ PDF Modelo (Etiqueta)", type="pdf")

if arq_circuit and arq_modelo:
    # BOTÃO 1: EXTRAIR
    if st.button("🔍 1. Extrair e Revisar Texto", use_container_width=True):
        res = extrair_dados_do_pdf(arq_circuit)
        if res:
            st.session_state.dados_extraidos = pd.DataFrame(res)
        else:
            st.error("Não encontrei dados. Verifique se o PDF é o correto.")

# Se já extraiu, mostra a tabela editável
if st.session_state.dados_extraidos is not None:
    st.info("💡 Dica: Clique em qualquer célula abaixo para corrigir nomes ou endereços bugados.")
    
    # TABELA EDITÁVEL
    df_editado = st.data_editor(
        st.session_state.dados_extraidos,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Nome": st.column_config.TextColumn("Nome do Cliente", width="medium"),
            "Endereco": st.column_config.TextColumn("Endereço Completo", width="large"),
        }
    )

    # BOTÃO 2: GERAR ETIQUETAS
    if st.button("🚀 2. Gerar PDF Final com os dados acima", type="primary", use_container_width=True):
        with st.spinner("Gerando etiquetas..."):
            pdf_pronto = criar_pdf_etiquetas(df_editado, arq_modelo)
            
            st.success("✅ PDF Gerado com sucesso!")
            st.download_button(
                label="📥 BAIXAR ETIQUETAS PARA IMPRIMIR",
                data=pdf_pronto,
                file_name="etiquetas_revisadas.pdf",
                mime="application/pdf",
                use_container_width=True
            )
