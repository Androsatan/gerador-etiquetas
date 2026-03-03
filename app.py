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
st.write("1. Suba os arquivos | 2. Confira os dados | 3. Gere o PDF único")

# --- FUNÇÕES DE APOIO ---

def extrair_dados_do_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    texto_bruto = ""
    for page in reader.pages:
        texto_bruto += page.extract_text() or ""
    
    # LIMPEZA FUNDAMENTAL: Remove aspas e quebras de linha que bugam o reconhecimento
    texto_limpo = texto_bruto.replace('"', '').replace('\n', ' ')
    texto_limpo = re.sub(r'\s+', ' ', texto_limpo)
    
    # REGEX: Baseada na estrutura que você enviou e que funciona
    # Procura: Número | Endereço | CEP | Notas
    pattern = re.compile(r"(\d+)\s+(.*?)\s+(\d{5}-\d{3})(.*?)(?=\d+\s+|$)", re.DOTALL)
    matches = pattern.findall(texto_limpo)
    
    dados = []
    for m in matches:
        # m[1] = endereço completo | m[3] = notas (onde está o nome e horário)
        endereco_bruto = f"{m[1]} {m[2]}".strip()
        nota_bruta = m[3].strip()
        
        # Limpeza do Nome: 
        # 1. Remove horários (ex: 18:40) que ficam grudados no nome
        nome_limpo = re.sub(r'\d{1,2}:\d{2}', '', nota_bruta)
        # 2. Remove o que estiver em colchetes []
        nome_limpo = re.sub(r'\[.*?\]', '', nome_limpo)
        # 3. Remove vírgulas e espaços que sobraram no início/fim
        nome_limpo = nome_limpo.replace(',', '').strip()
        
        # Limpeza do Endereço (Removendo Belo Horizonte e MG para caber na etiqueta)
        end_limpo = endereco_bruto.replace(', Belo Horizonte', '').replace(', Minas Gerais', '').replace(', MG', '')
        
        if nome_limpo:
            dados.append({"Nome": nome_limpo.upper(), "Endereco": end_limpo})
            
    return dados

def criar_pdf_etiquetas(df, pdf_modelo):
    modelo_reader = PdfReader(pdf_modelo)
    modelo_pagina = modelo_reader.pages[0]
    largura, altura = 100 * mm, 150 * mm
    pdf_final_writer = PdfWriter()

    for _, row in df.iterrows():
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=portrait((largura, altura)))
        
        # Nome do Cliente (Negrito e Maiúsculo)
        can.setFont("Helvetica-Bold", 10)
        can.drawString(38 * mm, 70.5 * mm, str(row['Nome']))
        
        # Endereço (Dividido em duas linhas se for muito longo)
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
        pdf_final_writer.add_page(saida_pag)

    pdf_saida = BytesIO()
    pdf_final_writer.write(pdf_saida)
    return pdf_saida.getvalue()

# --- FLUXO DO SITE ---

if 'dados_extraidos' not in st.session_state:
    st.session_state.dados_extraidos = None

c1, c2 = st.columns(2)
with c1:
    arq_circuit = st.file_uploader("📁 PDF do Circuit", type="pdf")
with c2:
    arq_modelo = st.file_uploader("🖼️ PDF Modelo (Etiqueta)", type="pdf")

if arq_circuit and arq_modelo:
    if st.button("🔍 1. Extrair e Revisar Texto", use_container_width=True):
        res = extrair_dados_do_pdf(arq_circuit)
        if res:
            st.session_state.dados_extraidos = pd.DataFrame(res)
            st.success(f"Sucesso! Encontradas {len(res)} etiquetas.")
        else:
            st.error("Não encontrei dados. O PDF pode estar em um formato protegido ou sem o padrão esperado.")

if st.session_state.dados_extraidos is not None:
    st.info("💡 Revise a tabela abaixo. Se o nome estiver errado, você pode clicar e editar aqui mesmo.")
    
    # Tabela Editável
    df_editado = st.data_editor(st.session_state.dados_extraidos, num_rows="dynamic", use_container_width=True)

    if st.button("🚀 2. Gerar PDF Final de Impressão", type="primary", use_container_width=True):
        with st.spinner("Gerando arquivo..."):
            pdf_pronto = criar_pdf_etiquetas(df_editado, arq_modelo)
            st.download_button(
                label="📥 BAIXAR ETIQUETAS",
                data=pdf_pronto,
                file_name="etiquetas_revisadas.pdf",
                mime="application/pdf",
                use_container_width=True
            )
