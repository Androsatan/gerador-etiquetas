import streamlit as st
import re
import pandas as pd
from pypdf import PdfReader, PdfWriter, PageObject
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import mm
from io import BytesIO

# Configuração da Interface
st.set_page_config(page_title="Editor de Etiquetas Sara Lin", page_icon="📝", layout="wide")
st.title("📝 Gerador de Etiquetas Profissional")
st.write("Confira os dados na tabela antes de gerar o PDF único.")

# --- FUNÇÕES DE EXTRAÇÃO ---

def extrair_dados_do_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    texto_bruto = ""
    for page in reader.pages:
        texto_bruto += page.extract_text() or ""
    
    # Normaliza as aspas (alguns PDFs usam aspas curvas)
    texto_limpo = texto_bruto.replace('“', '"').replace('”', '"').replace('„', '"')
    
    # REGEX FLEXÍVEL: 
    # Procura por 4 blocos de texto entre aspas, ignorando quebras de linha e espaços extras
    # Grupo 1: Número | Grupo 2: Endereço | Grupo 3: Hora | Grupo 4: Notas (Nome)
    pattern = re.compile(r'"\s*(\d+)\s*"[\s,]*?"\s*([\s\S]*?)\s*"[\s,]*?"\s*([\s\S]*?)\s*"[\s,]*?"\s*([\s\S]*?)\s*"')
    matches = pattern.findall(texto_limpo)
    
    dados = []
    for m in matches:
        # Limpa as quebras de linha internas que o PDF gera
        endereco_bruto = m[1].replace('\n', ' ').strip()
        nota_bruto = m[3].replace('\n', ' ').strip()

        # 1. Regra de Limpeza: Remove [] mas MANTÉM ()
        nome_limpo = re.sub(r'\[.*?\]', '', nota_bruto)
        nome_limpo = re.sub(r'\s+', ' ', nome_limpo).strip()
        
        # 2. Limpeza do Endereço
        end_limpo = endereco_bruto.replace(', Belo Horizonte', '').replace(', Minas Gerais', '').replace(', MG', '')
        # Formata o CEP para ter um traço padrão
        end_limpo = re.sub(r',\s*(\d{5})', r' - \1', end_limpo)
        
        if nome_limpo:
            dados.append({"Nome": nome_limpo, "Endereco": end_limpo})
            
    return dados

def gerar_pdf_final(df, pdf_modelo):
    modelo_reader = PdfReader(pdf_modelo)
    modelo_pagina = modelo_reader.pages[0]
    largura, altura = 100 * mm, 150 * mm
    writer = PdfWriter()

    for _, row in df.iterrows():
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=portrait((largura, altura)))
        
        # Nome do Cliente (MAIÚSCULO e Negrito)
        can.setFont("Helvetica-Bold", 10)
        can.drawString(38 * mm, 70.5 * mm, str(row['Nome']).upper())
        
        # Endereço (Tenta quebrar em duas linhas se houver vírgula)
        can.setFont("Helvetica", 9)
        end = str(row['Endereco'])
        if "," in end:
            partes = end.split(",", 1)
            can.drawString(9 * mm, 64 * mm, partes[0].strip())
            can.drawString(9 * mm, 60 * mm, partes[1].strip())
        else:
            can.drawString(9 * mm, 62 * mm, end)
        
        can.save()
        packet.seek(0)
        
        overlay = PdfReader(packet).pages[0]
        saida_pag = PageObject.create_blank_page(width=largura, height=altura)
        saida_pag.merge_page(modelo_pagina)
        saida_pag.merge_page(overlay)
        writer.add_page(saida_pag)

    saida_bytes = BytesIO()
    writer.write(saida_bytes)
    return saida_bytes.getvalue()

# --- INTERFACE ---

if 'tabela_clientes' not in st.session_state:
    st.session_state.tabela_clientes = None

col1, col2 = st.columns(2)
with col1:
    arq_rota = st.file_uploader("1. PDF do Circuit", type="pdf")
with col2:
    arq_modelo = st.file_uploader("2. PDF Modelo (Etiqueta)", type="pdf")

if arq_rota and arq_modelo:
    if st.button("🔍 Extrair e Conferir Dados", use_container_width=True):
        extraido = extrair_dados_do_pdf(arq_rota)
        if extraido:
            st.session_state.tabela_clientes = pd.DataFrame(extraido)
            st.success(f"Sucesso! Encontradas {len(extraido)} paradas.")
        else:
            st.error("Erro: Não encontrei os nomes no PDF. Verifique se é o arquivo original.")

if st.session_state.tabela_clientes is not None:
    st.markdown("### 📝 Revise os dados abaixo")
    st.caption("Dica: Se algo vier errado, você pode clicar na célula e corrigir antes de gerar o PDF.")
    
    # Tabela editável
    df_editado = st.data_editor(st.session_state.tabela_clientes, num_rows="dynamic", use_container_width=True)

    if st.button("🚀 Gerar PDF Único de Etiquetas", type="primary", use_container_width=True):
        with st.spinner("Unificando etiquetas em um único PDF..."):
            pdf_final = gerar_pdf_final(df_editado, arq_modelo)
            st.download_button(
                "📥 BAIXAR PDF DE IMPRESSÃO", 
                data=pdf_final, 
                file_name="etiquetas_unificadas.pdf", 
                mime="application/pdf", 
                use_container_width=True
            )
