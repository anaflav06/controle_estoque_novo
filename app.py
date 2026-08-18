
import streamlit as st
import json
from pathlib import Path
from datetime import datetime
import hashlib
import io
import pandas as pd

st.set_page_config(
    page_title="Controle de Estoque",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DB_PATH = Path(__file__).with_name("database_estoque.json")

def _github_config():
    try:
        token = st.secrets.get("GITHUB_TOKEN", "")
        repo = st.secrets.get("GITHUB_REPO", "")
        branch = st.secrets.get("GITHUB_DATA_BRANCH", "main")
        db_path = st.secrets.get("GITHUB_ESTOQUE_DB_PATH", "database_estoque.json")
        if token and repo:
            return token, repo, branch, db_path
    except Exception:
        pass
    return None

def _github_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def carregar():
    cfg = _github_config()
    if cfg:
        import requests, base64
        token, repo, branch, db_path = cfg
        url = f"https://api.github.com/repos/{repo}/contents/{db_path}"
        r = requests.get(url, headers=_github_headers(token), params={"ref": branch}, timeout=20)
        if r.status_code == 200:
            payload = r.json()
            conteudo = base64.b64decode(payload["content"]).decode("utf-8")
            return json.loads(conteudo)
        elif r.status_code != 404:
            st.error("Não foi possível carregar o banco de dados do GitHub.")
            st.stop()

    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    return {"unidades": {}}

def salvar(data):
    cfg = _github_config()
    if cfg:
        import requests, base64
        token, repo, branch, db_path = cfg
        url = f"https://api.github.com/repos/{repo}/contents/{db_path}"

        atual = requests.get(url, headers=_github_headers(token), params={"ref": branch}, timeout=20)

        payload = {
            "message": "Atualiza estoque SAO12/CPQ08",
            "content": base64.b64encode(
                json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            ).decode("ascii"),
            "branch": branch,
        }

        if atual.status_code == 200:
            payload["sha"] = atual.json()["sha"]
        elif atual.status_code != 404:
            raise RuntimeError("Falha ao consultar a versão atual do banco no GitHub.")

        gravacao = requests.put(url, headers=_github_headers(token), json=payload, timeout=25)

        if gravacao.status_code not in (200, 201):
            raise RuntimeError(f"Falha ao salvar o banco no GitHub (HTTP {gravacao.status_code}).")
        return

    DB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def salvar_unidade_seguro(unidade, unidade_data):
    """
    Salva somente a unidade alterada.
    No GitHub, busca sempre o JSON mais recente e faz merge para não
    sobrescrever dados da outra unidade. Em caso de conflito, tenta novamente.
    """
    cfg = _github_config()

    if cfg:
        import requests, base64
        token, repo, branch, db_path = cfg
        url = f"https://api.github.com/repos/{repo}/contents/{db_path}"

        for tentativa in range(3):
            atual = requests.get(
                url,
                headers=_github_headers(token),
                params={"ref": branch},
                timeout=20
            )

            if atual.status_code == 200:
                payload_atual = atual.json()
                sha = payload_atual["sha"]
                conteudo = base64.b64decode(payload_atual["content"]).decode("utf-8")
                db_mais_recente = json.loads(conteudo)
            elif atual.status_code == 404:
                sha = None
                db_mais_recente = {"unidades": {}}
            else:
                raise RuntimeError(
                    f"Falha ao consultar banco no GitHub (HTTP {atual.status_code})."
                )

            db_mais_recente.setdefault("unidades", {})
            db_mais_recente["unidades"][unidade] = unidade_data

            payload = {
                "message": f"Atualiza estoque {unidade}",
                "content": base64.b64encode(
                    json.dumps(db_mais_recente, ensure_ascii=False, indent=2).encode("utf-8")
                ).decode("ascii"),
                "branch": branch,
            }
            if sha:
                payload["sha"] = sha

            gravacao = requests.put(
                url,
                headers=_github_headers(token),
                json=payload,
                timeout=25
            )

            if gravacao.status_code in (200, 201):
                return db_mais_recente

            if gravacao.status_code in (409, 422):
                continue

            raise RuntimeError(
                f"Falha ao salvar banco no GitHub (HTTP {gravacao.status_code})."
            )

        raise RuntimeError(
            "O banco foi alterado por outro usuário ao mesmo tempo. Tente salvar novamente."
        )

    # Local: relê o JSON antes de gravar e altera somente a unidade atual.
    if DB_PATH.exists():
        db_mais_recente = json.loads(DB_PATH.read_text(encoding="utf-8"))
    else:
        db_mais_recente = {"unidades": {}}

    db_mais_recente.setdefault("unidades", {})
    db_mais_recente["unidades"][unidade] = unidade_data
    DB_PATH.write_text(
        json.dumps(db_mais_recente, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return db_mais_recente


def gerar_excel_bytes(itens_exportar, unidade, titulo):
    """Gera um Excel simples e profissional em memória."""
    linhas = []
    for item in itens_exportar:
        saldo = 0 if item.get("saldo") is None else int(item["saldo"])
        minimo = int(item["minimo"])
        faltam = max(0, minimo - saldo)
        linhas.append({
            "Categoria": item["categoria"],
            "Material": item["material"],
            "Unidade de medida": item["unidade"],
            "Saldo atual": saldo,
            "Estoque mínimo": minimo,
            "Faltam para o mínimo": faltam,
        })

    df = pd.DataFrame(linhas)
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Estoque", index=False, startrow=2)

        workbook = writer.book
        worksheet = writer.sheets["Estoque"]

        fmt_titulo = workbook.add_format({
            "bold": True,
            "font_size": 16,
            "font_color": "#FFFFFF",
            "bg_color": "#1565C0" if unidade == "SAO12" else "#F57C00",
            "align": "left",
            "valign": "vcenter",
        })
        fmt_header = workbook.add_format({
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#394B59",
            "border": 0,
            "align": "center",
            "valign": "vcenter",
        })
        fmt_int = workbook.add_format({"num_format": "0", "align": "center"})
        fmt_text = workbook.add_format({"valign": "vcenter"})

        worksheet.merge_range("A1:F1", f"{titulo} — {unidade}", fmt_titulo)
        worksheet.set_row(0, 28)

        for col_num, value in enumerate(df.columns.values):
            worksheet.write(2, col_num, value, fmt_header)

        worksheet.set_column("A:A", 29, fmt_text)
        worksheet.set_column("B:B", 34, fmt_text)
        worksheet.set_column("C:C", 18, fmt_text)
        worksheet.set_column("D:F", 18, fmt_int)
        worksheet.freeze_panes(3, 0)

    buffer.seek(0)
    return buffer.getvalue()


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
    padding-top: .5rem;
    padding-bottom: 2.5rem;
}

/* TELA INICIAL */
.landing-wrap {
    width:100%;
    margin-top:4vh;
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



/* Remove a barra superior padrão do Streamlit para evitar sobreposição */
header[data-testid="stHeader"] {
    height: 0 !important;
    min-height: 0 !important;
    background: transparent !important;
}
[data-testid="stToolbar"],
[data-testid="stDecoration"] {
    display: none !important;
}

/* Cabeçalho realmente fixo durante a rolagem */
.top-card {
    position: fixed !important;
    top: 10px !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    width: min(1180px, calc(100% - 48px)) !important;
    z-index: 10000 !important;
    margin: 0 !important;
    box-sizing: border-box !important;
}

/* Espaço reservado para o cabeçalho fixo */
.fixed-header-spacer {
    height: 118px;
}

/* Identificação da unidade ativa */
.unit-row {
    margin-top: 16px;
    margin-bottom: 14px;
}
.unit-info-card {
    border: 2px solid var(--unit-color);
    background: var(--unit-soft);
    border-radius: 12px;
    padding: 11px 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,.05);
}
.unit-info-label {
    color:#5f6b76;
    font-size:.78rem;
    font-weight:700;
    text-transform:uppercase;
    letter-spacing:.35px;
    margin-bottom:1px;
}
.unit-info-name {
    color:var(--unit-color);
    font-size:1.25rem;
    font-weight:900;
    line-height:1.15;
}
.unit-dot {
    display:inline-block;
    width:10px;
    height:10px;
    border-radius:50%;
    background:var(--unit-color);
    margin-right:7px;
}
.st-key-unit_switch button {
    background: var(--unit-color) !important;
    color: white !important;
    border: 2px solid var(--unit-color) !important;
    box-shadow: 0 3px 9px var(--unit-shadow) !important;
    min-height: 48px !important;
    font-size: .95rem !important;
}
.st-key-unit_switch button:hover {
    filter: brightness(.94);
    transform: translateY(-1px);
}

/* Garante espaço seguro no topo da página */
.block-container {
    padding-top: .5rem !important;
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

# Identidade visual por unidade
if unidade == "SAO12":
    unit_color = "#1565C0"
    unit_color_2 = "#0D47A1"
    unit_soft = "#EAF3FF"
    unit_shadow = "rgba(21,101,192,.22)"
else:  # CPQ08
    unit_color = "#F57C00"
    unit_color_2 = "#E65100"
    unit_soft = "#FFF3E0"
    unit_shadow = "rgba(245,124,0,.24)"

st.markdown(f"""
<style>
:root {{
    --unit-color: {unit_color};
    --unit-color-2: {unit_color_2};
    --unit-soft: {unit_soft};
    --unit-shadow: {unit_shadow};
}}
.top-card {{
    background: linear-gradient(90deg, var(--unit-color-2) 0%, var(--unit-color) 100%) !important;
    box-shadow: 0 4px 14px var(--unit-shadow) !important;
}}
</style>
<div class="top-card">
    <h1>📦 Controle de Estoque — {unidade}</h1>
    <p>Atualize o saldo sempre que houver retirada ou recebimento de materiais.</p>
</div>
<div class="fixed-header-spacer"></div>
""", unsafe_allow_html=True)

st.markdown('<div class="unit-row"></div>', unsafe_allow_html=True)
top1, top2 = st.columns([4.2, 1.35], gap="large", vertical_alignment="center")

with top1:
    st.markdown(
        f"""
        <div class="unit-info-card">
            <div class="unit-info-label">Unidade selecionada</div>
            <div class="unit-info-name"><span class="unit-dot"></span>{unidade}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with top2:
    if st.button("↔  TROCAR UNIDADE", use_container_width=True, key="unit_switch"):
        st.session_state.pop("unidade_selecionada", None)
        st.rerun()

itens = db["unidades"][unidade]["itens"]

categorias = [
    ("MATERIAL OPERACIONAL AZUL", "section-blue"),
    ("ITENS GDS — ESCRITÓRIO", "section-office"),
    ("ITENS GDS — COPA / LIMPEZA", "section-clean"),
]

# Formulário: alterações nos campos não recarregam a página a cada clique.
with st.form(key=f"form_estoque_{unidade}", clear_on_submit=False):
    valores_form = {}

    for categoria, classe in categorias:
        st.markdown(f'<div class="{classe}">{categoria}</div>', unsafe_allow_html=True)

        h1, h2, h3 = st.columns([5.4, 1.6, 1.8], gap="small")
        with h1:
            st.markdown('<div class="table-head">MATERIAL</div>', unsafe_allow_html=True)
        with h2:
            st.markdown('<div class="table-head">MÍNIMO</div>', unsafe_allow_html=True)
        with h3:
            st.markdown('<div class="table-head">SALDO ATUAL</div>', unsafe_allow_html=True)

        for idx, item in enumerate(itens):
            if item["categoria"] != categoria:
                continue

            saldo_atual = 0 if item.get("saldo") is None else int(item["saldo"])

            row_class = "item-row"
            if saldo_atual == 0:
                row_class += " zero"
            elif saldo_atual < int(item["minimo"]):
                row_class += " warn"

            st.markdown(f'<div class="{row_class}">', unsafe_allow_html=True)
            c1, c2, c3 = st.columns([5.4, 1.6, 1.8], gap="small", vertical_alignment="center")

            with c1:
                st.markdown(
                    f'<div class="item-name">{item["material"]}</div>',
                    unsafe_allow_html=True
                )

            with c2:
                st.markdown(
                    f'<div class="min-text">{int(item["minimo"])} {item["unidade"]}</div>',
                    unsafe_allow_html=True
                )

            with c3:
                valores_form[idx] = st.number_input(
                    "Saldo",
                    min_value=0,
                    step=1,
                    value=saldo_atual,
                    key=f"form_saldo_{unidade}_{idx}",
                    label_visibility="collapsed"
                )

            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="save-area">', unsafe_allow_html=True)
    salvar_form = st.form_submit_button(
        "💾 SALVAR ALTERAÇÕES",
        type="primary",
        use_container_width=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

if salvar_form:
    alterados = 0

    for idx, item in enumerate(itens):
        novo = int(valores_form[idx])
        antigo = item.get("saldo")
        antigo_comp = 0 if antigo is None else int(antigo)

        if antigo is None or antigo_comp != novo:
            registrar(item, antigo, novo, unidade)
            item["saldo"] = novo
            alterados += 1

    unidade_data = dict(db["unidades"][unidade])
    unidade_data["itens"] = itens
    unidade_data["ultima_atualizacao"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    try:
        db = salvar_unidade_seguro(unidade, unidade_data)
    except Exception as e:
        st.error(f"Não foi possível salvar o estoque. Detalhe: {e}")
        st.stop()

    # Limpa estados antigos da caixa de mensagem e mantém a tela sincronizada.
    for k in list(st.session_state.keys()):
        if k.startswith(f"msg_{unidade}_"):
            del st.session_state[k]

    if alterados:
        st.success(
            f"✅ Estoque da unidade {unidade} salvo com sucesso. "
            f"{alterados} item(ns) atualizado(s)."
        )
    else:
        st.info("Nenhuma alteração nova para salvar.")

    st.rerun()

# Após salvar/rerun, usa os dados efetivamente persistidos.
itens = db["unidades"][unidade]["itens"]

# Reposição: somente quando o saldo estiver ABAIXO do mínimo.
# Assim a mensagem nunca exibe "faltam 0".
itens_repor = []
for item in itens:
    saldo = 0 if item.get("saldo") is None else int(item["saldo"])
    minimo = int(item["minimo"])

    if saldo < minimo:
        item_msg = dict(item)
        item_msg["saldo_exibicao"] = saldo
        item_msg["faltam"] = minimo - saldo
        itens_repor.append(item_msg)

st.markdown(f"### ⚠️ Solicitação de reposição — {unidade}")

if not itens_repor:
    st.success("✅ Nenhum material precisa de reposição neste momento.")
else:
    linhas = [
        "📦 *Olá! Segue solicitação de reposição*",
        f"🏢 *Unidade: {unidade}*",
        "",
        "Precisamos dos materiais abaixo:",
        ""
    ]

    icones_categoria = {
        "MATERIAL OPERACIONAL AZUL": "🔵",
        "ITENS GDS — ESCRITÓRIO": "🗂️",
        "ITENS GDS — COPA / LIMPEZA": "🧹",
    }

    for categoria, _ in categorias:
        grupo = [x for x in itens_repor if x["categoria"] == categoria]
        if not grupo:
            continue

        linhas.append(f"{icones_categoria.get(categoria, '•')} *{categoria}*")
        for item in grupo:
            faltam = int(item["faltam"])
            unidade_medida = item["unidade"]
            verbo = "falta" if faltam == 1 else "faltam"
            linhas.append(
                f"• {item['material']} — {verbo} *{faltam} {unidade_medida}*"
            )
        linhas.append("")

    linhas.append("🙏 Por gentileza, providenciar os itens acima.")
    mensagem = "\n".join(linhas)

    msg_hash = hashlib.md5(mensagem.encode("utf-8")).hexdigest()[:10]

    st.text_area(
        "Mensagem pronta para WhatsApp",
        value=mensagem,
        height=280,
        key=f"msg_{unidade}_{msg_hash}"
    )
    st.caption("Selecione a mensagem e use Ctrl+C para copiar.")

st.markdown("---")
st.markdown("### 📊 Relatórios rápidos")

# Excel 1 — somente Material Operacional Azul
itens_operacional = [
    x for x in itens if x["categoria"] == "MATERIAL OPERACIONAL AZUL"
]
excel_operacional = gerar_excel_bytes(
    itens_operacional,
    unidade,
    "Material Operacional Azul"
)

# Excel 2 — estoque completo da unidade
excel_completo = gerar_excel_bytes(
    itens,
    unidade,
    "Estoque Completo"
)

b1, b2 = st.columns(2, gap="medium")
with b1:
    st.download_button(
        "📘 Baixar Excel — Material Operacional Azul",
        data=excel_operacional,
        file_name=f"material_operacional_{unidade}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

with b2:
    st.download_button(
        "📗 Baixar Excel — Estoque Completo",
        data=excel_completo,
        file_name=f"estoque_completo_{unidade}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

st.markdown("### 📋 Visão geral do estoque")

linhas_geral = []
for item in itens:
    saldo = 0 if item.get("saldo") is None else int(item["saldo"])
    minimo = int(item["minimo"])
    faltam = max(0, minimo - saldo)

    linhas_geral.append({
        "Categoria": item["categoria"],
        "Material": item["material"],
        "Saldo": saldo,
        "Mínimo": minimo,
        "Faltam": faltam,
    })

df_geral = pd.DataFrame(linhas_geral)

st.dataframe(
    df_geral,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Categoria": st.column_config.TextColumn("Categoria", width="medium"),
        "Material": st.column_config.TextColumn("Material", width="large"),
        "Saldo": st.column_config.NumberColumn("Saldo", format="%d"),
        "Mínimo": st.column_config.NumberColumn("Mínimo", format="%d"),
        "Faltam": st.column_config.NumberColumn("Faltam", format="%d"),
    }
)

ultima = db["unidades"][unidade].get("ultima_atualizacao")
if ultima:
    st.caption(f"🕒 Última atualização da unidade: {ultima}")

st.caption(
    "💾 Os dados continuam sendo salvos no database_estoque.json. "
    "SAO12 e CPQ08 permanecem com estoques independentes."
)
