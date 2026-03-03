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
st.title("📝 Gerador de Etiquetas com Conferência")
st.write("1. Suba os arquivos | 2. Confira e edite os dados | 3. Gere o PDF final")

# --- FUNÇÕES DE APOIO ---

def extrair_dados_do_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    texto_bruto = ""
    for page in reader.pages:
        texto_bruto += page.extract_text() or ""
    
    # Passo essencial: Remove quebras de linha internas para o Regex não falhar
    texto_limpo = texto_bruto.replace('\n', ' ')
    texto_limpo = re.sub(r'\s+', ' ', texto_limpo)
    
    # NOVO REGEX: Captura Número, Endereço, Hora e Nota (Nome) entre aspas
    # "(\d+)" -> Número | "(.*?)" -> Endereço | ".*?" -> Hora (ignorado) | "(.*?)" -> Notas
    pattern = re.compile(r'"\s*(\d+)\s*"[\s,]*?"\s*([\s\S]*?)\s*"[\s,]*?"\s*[\s\S]*?\s*"[\s,]*?"\s*([\s\S]*?)\s*"')
    matches = pattern.findall(texto_limpo)
    
    dados = []
    for m in matches:
        # m[1] é o endereço, m[2] é a nota (onde está o nome)
        end_pdf = m[1].strip()
        nota_pdf = m[2].strip()

        # Limpeza do Endereço (remover cidade e estado redundantes)
        end_limpo = end_pdf.replace(', Belo Horizonte', '').replace(', Minas Gerais', '').replace(', MG', '')
        
        # Limpeza do Nome: Remove [] mas MANTÉM ()
        nome_limpo = re.sub(r'\[.*?\]', '', nota_pdf)
        nome_limpo = re.sub(r'\s+', ' ', nome_limpo).strip()
        
        if nome_limpo: # Só adiciona se o nome não for vazio
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
        
        # --- POSICIONAMENTO DO NOME ---
        # 38mm da esquerda, 70.5mm da base (ajuste aqui se precisar subir ou descer)
        can.setFont("Helvetica-Bold", 9)
        can.drawString(38 * mm, 70.5 * mm, str(row['Nome']).upper())
        
        # --- POSICIONAMENTO DO ENDEREÇO ---
        can.setFont("Helvetica", 8)
        end = str(row['Endereco'])
        if "," in end:
            partes = end.split(",", 1)
            can.drawString(9 * mm, 64 * mm, partes[0].strip())
            can.drawString(9 * mm, 60 * mm, partes[1].strip())
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

if 'dados_extraidos' not in st.session_state:
    st.session_state.dados_extraidos = None

col1, col2 = st.columns(2)
with col1:
    arq_circuit = st.file_uploader("📁 PDF do Circuit", type="pdf")
with col2:
    arq_modelo = st.file_uploader("🖼️ PDF Modelo (Etiqueta)", type="pdf")

if arq_circuit and arq_modelo:
    if st.button("🔍 1. Extrair e Revisar Texto", use_container_width=True):
        res = extrair_dados_do_pdf(arq_circuit)
        if res:
            st.session_state.dados_extraidos = pd.DataFrame(res)
            st.success(f"Encontradas {len(res)} etiquetas!")
        else:
            st.error("Não encontrei dados. Verifique se o PDF é o original do Circuit.")

if st.session_state.dados_extraidos is not None:
    st.info("💡 Dica: Clique em qualquer célula abaixo para corrigir o texto se algo veio bugado.")
    
    df_editado = st.data_editor(
        st.session_state.dados_extraidos,
        num_rows="dynamic",
        use_container_width=True
    )

    if st.button("🚀 2. Gerar PDF Final", type="primary", use_container_width=True):
        with st.spinner("Gerando arquivo de impressão..."):
            pdf_pronto = criar_pdf_etiquetas(df_editado, arq_modelo)
            st.download_button(
                label="📥 BAIXAR ETIQUETAS PARA IMPRIMIR",
                data=pdf_pronto,
                file_name="etiquetas_revisadas.pdf",
                mime="application/pdf",
                use_container_width=True
            )
