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
st.title("📝 Gerador de Etiquetas Profissional")
st.write("Suba os arquivos e revise os dados. Colchetes [] removidos, Parênteses () mantidos.")

# --- FUNÇÕES DE EXTRAÇÃO E LIMPEZA ---

def extrair_dados_revisado(pdf_file):
    reader = PdfReader(pdf_file)
    texto_bruto = ""
    for page in reader.pages:
        texto_bruto += page.extract_text() or ""
    
    # 1. LIMPEZA AGRESSIVA: Remove quebras de linha e normaliza espaços
    # Isso transforma o PDF "sujo" em uma linha contínua de texto fácil de ler
    texto_limpo = texto_bruto.replace('\n', ' ')
    texto_limpo = re.sub(r'\s+', ' ', texto_limpo)
    
    # 2. REGEX ROBUSTO: 
    # Captura "NÚMERO" , "ENDEREÇO" , "HORA" , "NOTAS"
    # Aceita espaços extras dentro e fora das aspas
    pattern = re.compile(r'"\s*(\d+)\s*"\s*,\s*"(.*?)"\s*,\s*"(.*?)"\s*,\s*"(.*?)"')
    matches = pattern.findall(texto_limpo)
    
    dados = []
    for m in matches:
        # m[0]=Número, m[1]=Endereço, m[2]=Hora, m[3]=Notas (Nome)
        end_pdf = m[1].strip()
        nota_pdf = m[3].strip()

        # Limpeza do Endereço (Remove o que é desnecessário para a etiqueta)
        end_limpo = end_pdf.replace(', Belo Horizonte', '').replace(', Minas Gerais', '')
        # Garante o traço antes do CEP
        end_limpo = re.sub(r',\s*(\d{5})', r' - \1', end_limpo)
        
        # Limpeza do Nome: Remove [] mas mantém ()
        nome_limpo = re.sub(r'\[.*?\]', '', nota_pdf)
        nome_limpo = re.sub(r'\s+', ' ', nome_limpo).strip()
        
        if nome_limpo: # Só adiciona se o nome não estiver vazio
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
        
        # Nome do Cliente (MAIÚSCULO + Negrito)
        can.setFont("Helvetica-Bold", 10)
        can.drawString(38 * mm, 70.5 * mm, str(row['Nome']).upper())
        
        # Endereço (Quebra em duas linhas se houver vírgula)
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

c1, c2 = st.columns(2)
with c1:
    arq_rota = st.file_uploader("1. Carregar Circuit.pdf", type="pdf")
with c2:
    arq_modelo = st.file_uploader("2. Carregar Etiqueta.pdf", type="pdf")

if arq_rota and arq_modelo:
    if st.button("🔍 Extrair e Revisar Dados", use_container_width=True):
        extraido = extrair_dados_revisado(arq_rota)
        if extraido:
            st.session_state.tabela_clientes = pd.DataFrame(extraido)
            st.success(f"Encontradas {len(extraido)} paradas!")
        else:
            st.error("Não foi possível extrair dados. Verifique se o PDF é o exportado do Circuit.")

if st.session_state.tabela_clientes is not None:
    st.markdown("### 📝 Tabela de Conferência")
    st.info("Ajuste qualquer nome ou endereço abaixo se necessário.")
    
    # Exibe a tabela para edição
    df_editado = st.data_editor(
        st.session_state.tabela_clientes,
        num_rows="dynamic",
        use_container_width=True
    )

    if st.button("🚀 Gerar PDF Único de Etiquetas", type="primary", use_container_width=True):
        with st.spinner("Gerando arquivo de impressão..."):
            pdf_final = gerar_pdf_final(df_editado, arq_modelo)
            st.download_button(
                "📥 BAIXAR PDF DE IMPRESSÃO",
                data=pdf_final,
                file_name="etiquetas_finais.pdf",
                mime="application/pdf",
                use_container_width=True
            )
