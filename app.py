
import streamlit as st
import json
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="Controle de Estoque",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DB_PATH = Path(__file__).with_name("database_estoque_final.json")

def carregar():
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    return {"unidades": {}}

def salvar(data):
    DB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def registrar(item, antes, depois, unidade):
    tipo = "SALDO INICIAL" if antes is None else "AJUSTE"
    item.setdefault("historico", []).append({
        "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "unidade": unidade,
        "tipo": tipo,
        "saldo_anterior": None if antes is None else int(antes),
        "saldo_novo": int(depois),
        "diferenca": int(depois) if antes is None else int(depois) - int(antes)
    })

def key_saldo(unidade, idx):
    return f"saldo_{unidade}_{idx}"

def aumentar(unidade, idx):
    k = key_saldo(unidade, idx)
    atual = st.session_state.get(k)
    st.session_state[k] = 1 if atual is None else int(atual) + 1

def diminuir(unidade, idx):
    k = key_saldo(unidade, idx)
    atual = st.session_state.get(k)
    st.session_state[k] = 0 if atual is None else max(0, int(atual) - 1)

st.markdown("""
<style>
[data-testid="stSidebar"] {display:none;}

.block-container {
    max-width: 1180px;
    padding-top: 1rem;
    padding-bottom: 2.5rem;
}

/* TELA INICIAL */
.landing-wrap {
    min-height: 78vh;
    display:flex;
    align-items:center;
    justify-content:center;
}
.landing-card {
    width: 100%;
    max-width: 760px;
    background:#ffffff;
    border:1px solid #dce5ec;
    border-radius:18px;
    box-shadow:0 10px 30px rgba(15,76,129,.12);
    overflow:hidden;
}
.landing-head {
    background:linear-gradient(90deg,#0f4c81 0%,#1667a8 100%);
    color:#fff;
    padding:22px 26px 18px 26px;
}
.landing-head h1 {
    margin:0;
    font-size:1.8rem;
}
.landing-head p {
    margin:8px 0 0 0;
    line-height:1.45;
    font-size:.96rem;
    opacity:.96;
}
.landing-body {
    padding:24px 26px 18px 26px;
}
.landing-title {
    font-size:1.05rem;
    font-weight:800;
    text-align:center;
    margin-bottom:12px;
    color:#27333c;
}

/* CABEÇALHO APÓS ENTRAR NA UNIDADE */
.top-card {
    background:linear-gradient(90deg,#0f4c81 0%,#1667a8 100%);
    color:white;
    padding:14px 18px;
    border-radius:12px;
    margin-bottom:10px;
    box-shadow:0 3px 10px rgba(0,0,0,.08);
}
.top-card h1 {
    margin:0;
    font-size:1.55rem;
}
.top-card p {
    margin:4px 0 0 0;
    line-height:1.3;
    font-size:.9rem;
    opacity:.95;
}

.section-blue, .section-office, .section-clean {
    color:white;
    font-weight:800;
    padding:8px 12px;
    border-radius:8px;
    margin-top:13px;
    margin-bottom:4px;
    letter-spacing:.15px;
}
.section-blue {background:#1676c4;}
.section-office {background:#394b59;}
.section-clean {background:#3c7f73;}

.table-head {
    background:#edf2f6;
    border:1px solid #dce3e8;
    border-radius:6px;
    padding:5px 8px;
    font-size:.78rem;
    font-weight:800;
    color:#42505a;
    margin-bottom:1px;
}
.item-row {
    border-bottom:1px solid #edf0f2;
    padding:0 3px;
    margin:0;
}
.item-name {
    font-weight:650;
    font-size:.91rem;
    padding-top:5px;
    line-height:1.05;
}
.min-text {
    font-size:.86rem;
    padding-top:5px;
    color:#4d5a64;
}
.warn {
    background:#fff6dc;
    border-left:3px solid #e5a500;
    border-radius:4px;
    padding-left:5px;
}
.zero {
    background:#fdeceb;
    border-left:3px solid #c9433a;
    border-radius:4px;
    padding-left:5px;
}
div[data-testid="stNumberInput"] input {
    text-align:center;
    font-weight:700;
    font-size:.9rem;
    min-height:32px;
    padding-top:2px;
    padding-bottom:2px;
}
div[data-testid="stNumberInput"] {
    margin-top:-7px;
    margin-bottom:-7px;
}
.stButton > button {
    min-height:38px;
    border-radius:9px;
    font-weight:800;
}
[data-testid="stVerticalBlock"] {
    gap:.35rem;
}
.save-area {
    background:#f5f8fa;
    border:1px solid #dfe6eb;
    padding:10px 12px;
    border-radius:9px;
    margin-top:10px;
}
</style>
""", unsafe_allow_html=True)

db = carregar()

unidade = st.session_state.get("unidade_selecionada")

if not unidade:
    st.markdown('<div class="landing-wrap"><div class="landing-card">', unsafe_allow_html=True)
    st.markdown("""
    <div class="landing-head">
        <h1>📦 Controle de Estoque</h1>
        <p>
            Faça a contagem inicial e atualize as quantidades sempre que houver retirada ou recebimento de materiais.<br>
            Ao final, envie a mensagem de reposição para a liderança providenciar os itens faltantes.
        </p>
    </div>
    <div class="landing-body">
        <div class="landing-title">Selecione a unidade para acessar o estoque</div>
    </div>
    """, unsafe_allow_html=True)

    esp1, col1, col2, esp2 = st.columns([1.1, 1.6, 1.6, 1.1], gap="medium")

    with col1:
        if st.button("🏢  SAO12", use_container_width=True, key="btn_sao12"):
            st.session_state["unidade_selecionada"] = "SAO12"
            st.rerun()

    with col2:
        if st.button("🏢  CPQ08", use_container_width=True, key="btn_cpq08"):
            st.session_state["unidade_selecionada"] = "CPQ08"
            st.rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)
    st.stop()

if unidade not in db.get("unidades", {}):
    st.error("Unidade não encontrada no banco de dados.")
    st.stop()

st.markdown(f"""
<div class="top-card">
    <h1>📦 Controle de Estoque — {unidade}</h1>
    <p>Atualize o saldo sempre que houver retirada ou recebimento de materiais.</p>
</div>
""", unsafe_allow_html=True)

top1, top2 = st.columns([5, 1])
with top1:
    st.caption(f"Unidade selecionada: {unidade}")
with top2:
    if st.button("↩ Trocar unidade", use_container_width=True):
        st.session_state.pop("unidade_selecionada", None)
        st.rerun()

itens = db["unidades"][unidade]["itens"]

categorias = [
    ("MATERIAL OPERACIONAL AZUL", "section-blue"),
    ("ITENS GDS — ESCRITÓRIO", "section-office"),
    ("ITENS GDS — COPA / LIMPEZA", "section-clean"),
]

# Initialize session state separately for each unit
for idx, item in enumerate(itens):
    k = key_saldo(unidade, idx)
    if k not in st.session_state:
        st.session_state[k] = item.get("saldo")

for categoria, classe in categorias:
    st.markdown(f'<div class="{classe}">{categoria}</div>', unsafe_allow_html=True)

    h1, h2, h3, h4, h5 = st.columns([5.0, 1.45, 1.6, .55, .55], gap="small")
    with h1:
        st.markdown('<div class="table-head">MATERIAL</div>', unsafe_allow_html=True)
    with h2:
        st.markdown('<div class="table-head">MÍNIMO</div>', unsafe_allow_html=True)
    with h3:
        st.markdown('<div class="table-head">SALDO ATUAL</div>', unsafe_allow_html=True)
    with h4:
        st.markdown('<div class="table-head" style="text-align:center;">−</div>', unsafe_allow_html=True)
    with h5:
        st.markdown('<div class="table-head" style="text-align:center;">+</div>', unsafe_allow_html=True)

    for idx, item in enumerate(itens):
        if item["categoria"] != categoria:
            continue

        valor = st.session_state.get(key_saldo(unidade, idx))
        saldo_visual = 0 if valor is None else int(valor)

        row_class = "item-row"
        if saldo_visual == 0:
            row_class += " zero"
        elif saldo_visual <= int(item["minimo"]):
            row_class += " warn"

        st.markdown(f'<div class="{row_class}">', unsafe_allow_html=True)
        c1, c2, c3, c4, c5 = st.columns([5.0, 1.45, 1.6, .55, .55], gap="small", vertical_alignment="center")

        with c1:
            st.markdown(f'<div class="item-name">{item["material"]}</div>', unsafe_allow_html=True)

        with c2:
            st.markdown(
                f'<div class="min-text">{int(item["minimo"])} {item["unidade"]}</div>',
                unsafe_allow_html=True
            )

        with c3:
            st.number_input(
                "Saldo",
                min_value=0,
                step=1,
                value=valor,
                placeholder="0",
                key=key_saldo(unidade, idx),
                label_visibility="collapsed"
            )

        with c4:
            st.button(
                "−",
                key=f"menos_{unidade}_{idx}",
                on_click=diminuir,
                args=(unidade, idx),
                use_container_width=True
            )

        with c5:
            st.button(
                "+",
                key=f"mais_{unidade}_{idx}",
                on_click=aumentar,
                args=(unidade, idx),
                use_container_width=True
            )

        st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="save-area">', unsafe_allow_html=True)

if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True, key=f"salvar_{unidade}"):
    alterados = 0

    for idx, item in enumerate(itens):
        novo_ui = st.session_state.get(key_saldo(unidade, idx))
        antigo = item.get("saldo")

        novo = 0 if novo_ui is None else int(novo_ui)
        antigo_comp = 0 if antigo is None else int(antigo)

        if antigo is None or antigo_comp != novo:
            registrar(item, antigo, novo, unidade)
            item["saldo"] = novo
            alterados += 1

    db["unidades"][unidade]["itens"] = itens
    salvar(db)

    if alterados:
        st.success(f"Estoque da unidade {unidade} salvo. {alterados} item(ns) atualizado(s).")
    else:
        st.info("Nenhuma alteração nova para salvar.")

    st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

itens_repor = []
for idx, item in enumerate(itens):
    valor_ui = st.session_state.get(key_saldo(unidade, idx))
    saldo = 0 if valor_ui is None else int(valor_ui)

    if saldo <= int(item["minimo"]):
        item_msg = dict(item)
        item_msg["saldo_exibicao"] = saldo
        itens_repor.append(item_msg)

st.markdown(f"### ⚠️ Solicitação de reposição — {unidade}")

if not itens_repor:
    st.success("Nenhum material está no estoque mínimo.")
else:
    linhas = [
        "⚠️ *SOLICITAÇÃO DE REPOSIÇÃO*",
        f"*Unidade: {unidade}*",
        "",
        "Seguem os materiais que atingiram o estoque mínimo:",
        ""
    ]

    for categoria, _ in categorias:
        grupo = [x for x in itens_repor if x["categoria"] == categoria]
        if not grupo:
            continue

        linhas.append(f"*{categoria}*")
        for item in grupo:
            saldo = int(item["saldo_exibicao"])
            linhas.append(
                f"• {item['material']} — *Saldo: {saldo} {item['unidade']} | "
                f"Mínimo: {int(item['minimo'])} {item['unidade']}*"
            )
        linhas.append("")

    linhas.append("📦 *Solicito a reposição dos itens acima.*")
    mensagem = "\n".join(linhas)

    st.text_area(
        "Mensagem pronta para WhatsApp",
        value=mensagem,
        height=300,
        key=f"msg_{unidade}"
    )
    st.caption("Selecione a mensagem e use Ctrl+C para copiar.")
