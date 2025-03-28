import re
import pdfplumber
import pandas as pd
from datetime import datetime
import streamlit as st
from io import BytesIO

import streamlit as st
import base64

def imagem_para_base64(caminho_imagem):
    with open(caminho_imagem, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

logo_base64 = imagem_para_base64("logo.png")

st.set_page_config(page_title="Extrator PER/DCOMP", layout="wide")

st.markdown(
    f"""
    <style>
    .logo-direita {{
        position: absolute;
        top: 30px;
        right: 30px;
        z-index: 1;
    }}
    </style>
    <div class="logo-direita">
        <img src="data:image/png;base64,{logo_base64}" width="200"/>
    </div>
    """,
    unsafe_allow_html=True
)


codigos_receita = [
    "1170-01", "1184-01", "1181-01", "1200-01", "1196-01", "1191-01", "1176-01",
    "1170-21", "1170-51", "1176-02", "1176-21", "1176-22", "1176-51", "1176-52",
    "1181-21", "1181-51", "1184-21", "1184-51", "1191-21", "1191-51", "1196-21", "1196-51",
    "1200-02", "1200-21", "1200-22", "1200-51", "1200-52",
    "1205-01", "1205-21", "1205-51",
    "1209-01", "1209-21", "1209-51",
    "1213-01", "1213-03", "1213-05", "1213-23", "1213-53",
    "1218-01", "1218-02", "1218-21", "1218-51", "1218-52",
    "1221-01", "1221-02", "1221-21", "1221-51", "1221-52",
    "1225-01", "1225-21", "1225-51",
    "1213-02", "1213-04", "1213-06", "1213-07", "1213-08", "1213-09",
    "1170-31", "1176-31", "1181-31", "1184-31", "1200-31"
]



def extrair_regex(texto, padrao):
    match = re.search(padrao, texto)
    return match.group(1).strip() if match else None

def parse_valor(valor_str):
    try:
        return float(valor_str.replace('.', '').replace(',', '.'))
    except:
        return None

def parse_data(data_str):
    try:
        return datetime.strptime(data_str, "%d/%m/%Y").date()
    except:
        return None

def extrair_valores_de_credito(texto_completo):
    valores = {codigo: None for codigo in codigos_receita}
    blocos = re.findall(
        r'Código da Receita\s*(\d{4}-\d{2}).*?Valor Original do Crédito\s*([\d\.,]+)',
        texto_completo,
        re.DOTALL
    )
    for codigo, valor in blocos:
        if codigo in valores:
            valores[codigo] = parse_valor(valor)
    return valores

def extrair_primeiro_periodo_apuracao(texto_completo):
    match = re.search(r'Período de Apuração\s*(\d{2}/\d{2}/\d{4})', texto_completo)
    return parse_data(match.group(1)) if match else None

def extrair_dados_de_um_pdf(file):
    try:
        with pdfplumber.open(file) as pdf:
            texto_pag1 = pdf.pages[0].extract_text()
            texto_tudo = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

        retificador = extrair_regex(texto_pag1, r'PER/DCOMP Retificador\s*(\w+)')
        numero_retificado = None
        if retificador and retificador.lower() == "sim":
            numero_retificado = extrair_regex(texto_pag1, r'N[º°o]?\s*PER/DCOMP Retificado\s*([\d\.\-]+)')

        dados = {
            "Arquivo": file.name,
            "Data de Criação": parse_data(extrair_regex(texto_pag1, r'Data de Criação\s*([\d/]{10})')),
            "Data de Transmissão": parse_data(extrair_regex(texto_pag1, r'Data de Transmissão\s*([\d/]{10})')),
            "Tipo de Documento": extrair_regex(texto_pag1, r'Tipo de Documento\s*(.*)'),
            "CNPJ": extrair_regex(texto_pag1, r'CNPJ\s*([\d./-]+)'),
            "DComp": extrair_regex(texto_pag1, r'CNPJ\s*[\d./-]+\s*([0-9.]+-[0-9]+)'),
            "PER/DCOMP Retificador": retificador,
            "Nº PER/DCOMP Retificado": numero_retificado,
            "Período de Apuração": extrair_primeiro_periodo_apuracao(texto_tudo)
        }

        dados.update(extrair_valores_de_credito(texto_tudo))
        # Adiciona coluna "Códigos presentes"
        codigos_presentes = [codigo for codigo in codigos_receita if dados.get(codigo) and dados[codigo] > 0]
        dados["Códigos presentes"] = "; ".join(codigos_presentes)
        return dados

    except Exception as e:
        return {"Arquivo": file.name, "Erro": str(e)}

# Interface Streamlit
st.title("📄 Extrator de Dados de PDFs PER/DCOMP")
st.markdown("Faça upload de **1 ou mais PDFs** para extrair as informações.")

# CSS para traduzir a área de drop de arquivos
with st.container():
    st.markdown("""
        <style>
        /* Esconde o texto em inglês do drag and drop */
        .stFileUploader > div > div > span {
            display: none;
        }

        /* Adiciona o texto em português acima do botão */
        .texto-pt {
            font-weight: 500;
            color: #444;
            margin-bottom: 8px;
            display: block;
            font-size: 0.95rem;
        }
        </style>
        <span class='texto-pt'>Arraste e solte os arquivos abaixo ou clique em "Browse files"</span>
    """, unsafe_allow_html=True)

uploaded_files = st.file_uploader("📤 Envie os arquivos PDF", type="pdf", accept_multiple_files=True)

if uploaded_files:
    dados_coletados = []
    st.info(f"{len(uploaded_files)} arquivos recebidos. Processando...")

    for file in uploaded_files:
        dados = extrair_dados_de_um_pdf(file)
        dados_coletados.append(dados)

    df = pd.DataFrame(dados_coletados)

    # Reorganiza as colunas para colocar "Códigos presentes" antes dos códigos de receita
    colunas_fixas = [
        "Arquivo", "Data de Criação", "Data de Transmissão", "Tipo de Documento",
        "CNPJ", "DComp", "PER/DCOMP Retificador", "Nº PER/DCOMP Retificado",
        "Período de Apuração", "Códigos presentes"
    ]
    colunas_codigos = [col for col in df.columns if col in codigos_receita]
    outras_colunas = [col for col in df.columns if col not in colunas_fixas + colunas_codigos]

    nova_ordem = colunas_fixas + outras_colunas + colunas_codigos
    df = df[nova_ordem]
    df = df.sort_values(by=["CNPJ", "Período de Apuração"], ascending=[True, True]).reset_index(drop=True)


    st.success("✅ Processamento concluído!")

    st.dataframe(df)

    # Gera Excel para download
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados')
    output.seek(0)

    st.download_button(
        label="📥 Baixar Excel com os dados",
        data=output,
        file_name="Dados DCOMP.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
