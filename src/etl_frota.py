"""ETL de frota: planilhas brutas -> Star Schema pronto para o Power BI.

Uso:
    python src/etl_frota.py [pasta_brutos] [pasta_saida]   # padrão: dados_brutos/ e saida/

Script único e reexecutável: cada execução reconstrói o modelo inteiro a partir
das fontes brutas, sem depender de saídas anteriores.

Saídas (CSV em padrão brasileiro: separador ";" e decimal ","):
    Dimensoes/  DimData, DimVeiculo, DimMotorista, DimPosto
    Fatos/      FatoAbastecimento, FatoRevisao, FatoMulta
    Qualidade/  log_qualidade, registros_orfaos
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

MARCA_TIPO = {"caminhão": "Caminhão", "van": "Van", "oroch": "Picape", "frontier": "Picape",
              "hilux": "Picape", "strada": "Picape"}

log_qualidade: list[dict] = []
orfaos: list[dict] = []


def registrar(tabela: str, regra: str, qtd: int, detalhe: str = "") -> None:
    if qtd:
        log_qualidade.append({"Tabela": tabela, "Regra": regra, "Registros": int(qtd), "Detalhe": detalhe})


# --------------------------------------------------------------------------
# Funções de limpeza
# --------------------------------------------------------------------------
def ler(pasta: Path, nome: str) -> pd.DataFrame:
    return pd.read_csv(pasta / nome, sep=";", dtype=str, keep_default_na=False, encoding="utf-8-sig")


def para_data(serie: pd.Series, tabela: str, coluna: str) -> pd.Series:
    """Converte dd/mm/aaaa; anos fora de 2000–2100 viram nulo e vão para o log."""
    texto = serie.str.strip()
    datas = pd.to_datetime(texto, format="%d/%m/%Y", errors="coerce")
    invalidas = texto.ne("") & (datas.isna() | ~datas.dt.year.between(2000, 2100))
    registrar(tabela, f"Data implausível em '{coluna}' anulada", invalidas.sum(),
              ", ".join(sorted(texto[invalidas].unique())[:5]))
    return datas.mask(invalidas)


def para_numero(serie: pd.Series) -> pd.Series:
    """Converte '1.234,56' em 1234.56."""
    limpo = serie.str.strip().str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(limpo, errors="coerce")


def limpar_placa(serie: pd.Series, tabela: str) -> pd.Series:
    limpa = serie.str.strip().str.upper()
    registrar(tabela, "Placa normalizada (espaços e minúsculas)", (limpa != serie).sum())
    return limpa


def chave_data(datas: pd.Series) -> pd.Series:
    return datas.dt.strftime("%Y%m%d").astype("Int64")


# --------------------------------------------------------------------------
# Dimensões
# --------------------------------------------------------------------------
def dim_veiculo(bruto: pd.DataFrame) -> pd.DataFrame:
    d = pd.DataFrame({
        "Placa": limpar_placa(bruto["Placa"], "DimVeiculo"),
        "Marca": bruto["Marca"].str.strip(),
        "Modelo": bruto["Modelo"].str.strip(),
        "Ano": pd.to_numeric(bruto["Ano"], errors="coerce").astype("Int64"),
        "Setor": bruto["Setor"].str.strip(),
    })
    dup = d.duplicated("Placa").sum()
    registrar("DimVeiculo", "Placa duplicada no cadastro (mantida a primeira)", dup)
    d = d.drop_duplicates("Placa").reset_index(drop=True)

    def tipo(modelo: str) -> str:
        m = modelo.lower()
        return next((t for chave, t in MARCA_TIPO.items() if chave in m), "Passeio")

    d["TipoVeiculo"] = d["Modelo"].map(tipo)     # derivado do modelo: a origem não traz o tipo
    d.insert(0, "IdVeiculo", range(1, len(d) + 1))
    return d


def dim_simples(valores: pd.Series, nome_id: str, nome_col: str) -> pd.DataFrame:
    unicos = sorted(v for v in valores.str.strip().unique() if v)
    return pd.DataFrame({nome_id: range(1, len(unicos) + 1), nome_col: unicos})


def dim_data(inicio: pd.Timestamp, fim: pd.Timestamp) -> pd.DataFrame:
    dias = pd.date_range(pd.Timestamp(inicio.year, 1, 1), pd.Timestamp(fim.year, 12, 31), freq="D")
    meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    return pd.DataFrame({
        "IdData": dias.strftime("%Y%m%d").astype(int),
        "Data": dias.strftime("%d/%m/%Y"),
        "Ano": dias.year,
        "MesNumero": dias.month,
        "Mes": [meses[m - 1] for m in dias.month],
        "AnoMes": dias.strftime("%Y-%m"),
        "Trimestre": ["T" + str(q) for q in dias.quarter],
        "DiaUtil": (dias.dayofweek < 5).astype(int),
    })


# --------------------------------------------------------------------------
# Fatos
# --------------------------------------------------------------------------
def ligar_veiculo(df: pd.DataFrame, veiculos: pd.DataFrame, tabela: str) -> pd.DataFrame:
    """Troca a placa pelo IdVeiculo; placas sem cadastro saem para registros_orfaos."""
    df = df.merge(veiculos[["IdVeiculo", "Placa"]], on="Placa", how="left")
    sem = df["IdVeiculo"].isna()
    for _, linha in df[sem].iterrows():
        orfaos.append({"Tabela": tabela, "Chave": "Placa", "Valor": linha["Placa"]})
    registrar(tabela, "Registro órfão: placa sem cadastro (removido da fato)", sem.sum())
    df = df[~sem].copy()
    df["IdVeiculo"] = df["IdVeiculo"].astype(int)
    return df.drop(columns="Placa")


def fato_abastecimento(bruto, veiculos, motoristas, postos) -> pd.DataFrame:
    t = "FatoAbastecimento"
    f = pd.DataFrame({
        "Data": para_data(bruto["Data"], t, "Data"),
        "Placa": limpar_placa(bruto["Placa"], t),
        "Motorista": bruto["Motorista"].str.strip(),
        "Posto": bruto["Posto"].str.strip(),
        "Litros": para_numero(bruto["Litros"]),
        "Valor": para_numero(bruto["Valor"]),
        "KM": pd.to_numeric(bruto["KM"], errors="coerce").astype("Int64"),
    })
    f = ligar_veiculo(f, veiculos, t)
    f = f.merge(motoristas, on="Motorista", how="left").merge(postos, on="Posto", how="left")
    f["IdData"] = chave_data(f["Data"])
    f["PrecoLitro"] = (f["Valor"] / f["Litros"]).round(3)
    f.insert(0, "IdAbastecimento", range(1, len(f) + 1))
    return f[["IdAbastecimento", "IdData", "IdVeiculo", "IdMotorista", "IdPosto", "Litros", "Valor", "PrecoLitro", "KM"]]


def fato_revisao(bruto, veiculos) -> pd.DataFrame:
    """Unpivot: de um bloco de colunas por marco de KM para uma linha por revisão."""
    t = "FatoRevisao"
    marcos = sorted({int(c.split()[1]) for c in bruto.columns if c.startswith("Rev ")})
    partes = []
    for m in marcos:
        p = pd.DataFrame({
            "Placa": bruto["Placa"],
            "KMPrevisto": m,
            "Data": bruto[f"Rev {m} - Data"],
            "KMRealizado": bruto[f"Rev {m} - KM"],
            "Valor": bruto[f"Rev {m} - Valor"],
        })
        partes.append(p[p["Data"].str.strip() != ""])
    f = pd.concat(partes, ignore_index=True)
    f["Placa"] = limpar_placa(f["Placa"], t)
    f["Data"] = para_data(f["Data"], t, "Data")
    f["KMRealizado"] = pd.to_numeric(f["KMRealizado"], errors="coerce").astype("Int64")
    f["Valor"] = para_numero(f["Valor"])
    f["DesvioKM"] = f["KMRealizado"] - f["KMPrevisto"]
    f = ligar_veiculo(f, veiculos, t)
    f["IdData"] = chave_data(f["Data"])
    f.insert(0, "IdRevisao", range(1, len(f) + 1))
    return f[["IdRevisao", "IdData", "IdVeiculo", "KMPrevisto", "KMRealizado", "DesvioKM", "Valor"]]


def fato_multa(bruto, veiculos, motoristas) -> pd.DataFrame:
    t = "FatoMulta"
    f = pd.DataFrame({
        "Data": para_data(bruto["Data Infração"], t, "Data Infração"),
        "Placa": limpar_placa(bruto["Placa"], t),
        "Motorista": bruto["Motorista"].str.strip(),
        "Infracao": bruto["Infração"].str.strip(),
        "Valor": para_numero(bruto["Valor"]),
        # "Multa Paga" é a DATA do pagamento, e não um sim/não
        "DataPagamento": para_data(bruto["Multa Paga"], t, "Multa Paga"),
    })
    f["Paga"] = f["DataPagamento"].notna().map({True: "Sim", False: "Não"})
    f["DiasAtePagamento"] = (f["DataPagamento"] - f["Data"]).dt.days.astype("Int64")
    f = ligar_veiculo(f, veiculos, t)
    f = f.merge(motoristas, on="Motorista", how="left")
    f["IdData"] = chave_data(f["Data"])
    f["IdDataPagamento"] = chave_data(f["DataPagamento"])
    f.insert(0, "IdMulta", range(1, len(f) + 1))
    return f[["IdMulta", "IdData", "IdVeiculo", "IdMotorista", "Infracao", "Valor", "Paga", "IdDataPagamento", "DiasAtePagamento"]]


# --------------------------------------------------------------------------
# Integridade e gravação
# --------------------------------------------------------------------------
def conferir_integridade(fatos: dict, dims: dict) -> None:
    chaves = {"IdVeiculo": "DimVeiculo", "IdMotorista": "DimMotorista", "IdPosto": "DimPosto", "IdData": "DimData"}
    for nome, fato in fatos.items():
        for chave, dim in chaves.items():
            if chave not in fato.columns:
                continue
            validos = set(dims[dim][chave])
            fora = fato[chave].dropna().map(lambda v: v not in validos).sum()
            if fora:
                raise AssertionError(f"{nome}.{chave}: {fora} valor(es) sem correspondência em {dim}")
    print("Integridade referencial: OK em todas as fatos")


def gravar(df: pd.DataFrame, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(caminho, sep=";", decimal=",", index=False, encoding="utf-8-sig")


def main(brutos: Path, saida: Path) -> None:
    log_qualidade.clear()
    orfaos.clear()

    veic = dim_veiculo(ler(brutos, "veiculos.csv"))
    b_abast, b_rev, b_multa = ler(brutos, "abastecimentos.csv"), ler(brutos, "revisoes_largo.csv"), ler(brutos, "multas.csv")

    motoristas = dim_simples(pd.concat([b_abast["Motorista"], b_multa["Motorista"]]), "IdMotorista", "Motorista")
    postos = dim_simples(b_abast["Posto"], "IdPosto", "Posto")

    fatos = {
        "FatoAbastecimento": fato_abastecimento(b_abast, veic, motoristas, postos),
        "FatoRevisao": fato_revisao(b_rev, veic),
        "FatoMulta": fato_multa(b_multa, veic, motoristas),
    }

    todas = pd.concat([pd.to_datetime(f["IdData"].dropna().astype(str), format="%Y%m%d") for f in fatos.values()])
    dims = {"DimData": dim_data(todas.min(), todas.max()), "DimVeiculo": veic, "DimMotorista": motoristas, "DimPosto": postos}

    conferir_integridade(fatos, dims)

    for nome, df in dims.items():
        gravar(df, saida / "Dimensoes" / f"{nome}.csv")
    for nome, df in fatos.items():
        gravar(df, saida / "Fatos" / f"{nome}.csv")
    gravar(pd.DataFrame(log_qualidade, columns=["Tabela", "Regra", "Registros", "Detalhe"]), saida / "Qualidade" / "log_qualidade.csv")
    gravar(pd.DataFrame(orfaos, columns=["Tabela", "Chave", "Valor"]), saida / "Qualidade" / "registros_orfaos.csv")

    print(f"\n{'Tabela':<20}{'Linhas':>8}")
    for nome, df in {**dims, **fatos}.items():
        print(f"{nome:<20}{len(df):>8,}")
    print(f"\nApontamentos de qualidade: {len(log_qualidade)} regra(s), {sum(l['Registros'] for l in log_qualidade)} registro(s)")
    print(f"Saída gravada em {saida}/")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]   # ignora flags injetadas por notebooks
    main(Path(args[0]) if args else Path("dados_brutos"), Path(args[1]) if len(args) > 1 else Path("saida"))
