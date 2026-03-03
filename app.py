import streamlit as st
import re
import pandas as pd
from pypdf import PdfReader, PdfWriter, PageObject
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import mm
from io import BytesIO
import zipfile

# Configuração da Interface
st.set_page_config(page_title="Sara Lin - Gerador de Etiquetas", page_icon="🏷️")
st.title("🏷️ Gerador de Etiquetas 10x15")
st.write("Suba os arquivos e baixe suas etiquetas prontas.")

# --- LÓGICA DE PROCESSAMENTO ---

def processar_tudo(pdf_circuit, pdf_modelo):
    # 1. Extração (Equivalente ao 1ROTA)
    reader = PdfReader(pdf_circuit)
    texto_completo = ""
    for page in reader.pages:
        texto_completo += page.extract_text() or ""
    
    # Busca paradas (Regex do seu script original adaptada)
    # Procura por: Parada, Endereço até CEP, e Notas
    pattern = re.compile(r"(\d+)\s+(.*?)\s+(\d{5}-\d{3})(.*?)(?=\d+\s+|$)", re.DOTALL)
    matches = pattern.findall(texto_completo)
    
    # 2. Limpeza (Equivalente ao 2CLIENTES)
    clientes = []
    for m in matches:
        endereco_bruto = f"{m[1]} {m[2]}".strip()
        nota = m[3].strip()
        
        # Remove número da residência antes do '-' e limpa colchetes
        end_limpo = re.sub(r'^(.*?),\s*\d+\s*-', r'\1 -', endereco_bruto)
        nome_limpo = re.sub(r'\s*\[.*?\]', '', nota).strip()
        
        clientes.append({"Nome": nome_limpo, "Endereco": end_limpo})
    
    if not clientes:
        return None

    # 3. Geração (Equivalente ao 3ETIQUETAS)
    modelo_reader = PdfReader(pdf_modelo)
    modelo_pagina = modelo_reader.pages[0]
    largura, altura = 100 * mm, 150 * mm
    
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for c in clientes:
            # Criar sobreposição
            packet = BytesIO()
            can = canvas.Canvas(packet, pagesize=portrait((largura, altura)))
            
            # Nome
            can.setFont("Helvetica-Bold", 9)
            can.drawString(38 * mm, 70.5 * mm, c['Nome']) # Ajuste de posição
            
            # Endereço
            can.setFont("Helvetica", 8)
            end = c['Endereco']
            if "MG," in end:
                l1, l2 = end.split("MG,", 1)
                can.drawString(9 * mm, 65 * mm, l1.strip() + " MG")
                can.drawString(9 * mm, 62 * mm, l2.strip())
            else:
                can.drawString(9 * mm, 64 * mm, end)
            
            can.save()
            packet.seek(0)
            
            # Mesclar e salvar no ZIP
            overlay = PdfReader(packet).pages[0]
            saida_pag = PageObject.create_blank_page(width=largura, height=altura)
            saida_pag.merge_page(modelo_pagina)
            saida_pag.merge_page(overlay)
            
            pdf_writer = PdfWriter()
            pdf_writer.add_page(saida_pag)
            
            pdf_final = BytesIO()
            pdf_writer.write(pdf_final)
            
            nome_arq = f"{re.sub(r'[^A-Z]', '_', c['Nome'].upper())}.pdf"
            zf.writestr(nome_arq, pdf_final.getvalue())
            
    return zip_buffer.getvalue(), len(clientes)

# --- INTERFACE ---
arq_circuit = st.file_uploader("1. Selecione o Circuit.pdf", type="pdf")
arq_modelo = st.file_uploader("2. Selecione o Etiqueta.pdf", type="pdf")

if arq_circuit and arq_modelo:
    if st.button("🪄 Gerar Etiquetas Agora"):
        resultado = processar_tudo(arq_circuit, arq_modelo)
        if resultado:
            zip_data, qtd = resultado
            st.success(f"✅ {qtd} etiquetas processadas com sucesso!")
            st.download_button(
                label="📥 Baixar ZIP com Etiquetas",
                data=zip_data,
                file_name="etiquetas_prontas.zip",
                mime="application/zip",
                use_container_width=True
            )
        else:
            st.error("Erro: Não encontrei dados de clientes no PDF da rota.")