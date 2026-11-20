"""Gera planilhas brutas fictícias de uma frota, com os defeitos típicos de dados operacionais.

Uso:
    python scripts/gerar_dados_brutos.py [pasta_saida]     # padrão: dados_brutos/

Defeitos inseridos de propósito:
- datas com ano digitado errado (ex.: 27/07/0225)
- valores em formato brasileiro ("1.234,56") e placas com espaços e minúsculas
- revisões em formato "largo": um bloco de colunas por marco de quilometragem
- multas de placas que não existem no cadastro (registros órfãos)
"""
from __future__ import annotations

import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

MODELOS = [
    ("Renault", "Oroch Outsider", "Picape"), ("Nissan", "Frontier Attack", "Picape"),
    ("Toyota", "Hilux SR", "Picape"), ("Fiat", "Strada Freedom", "Picape"),
    ("Chevrolet", "Onix LT", "Passeio"), ("Volkswagen", "Polo Track", "Passeio"),
    ("Mercedes-Benz", "Sprinter 417 Van", "Van"), ("Volvo", "VM 270 Caminhão", "Caminhão"),
]
SETORES = ["Operações", "Educação", "Administrativo", "Comunicação", "Diretoria"]
MOTORISTAS = ["Ana Prado", "Bruno Lima", "Carla Nunes", "Diego Ramos", "Elisa Farias", "Fábio Souza",
              "Gabriela Moraes", "Heitor Campos", "João Barros", "Karina Duarte", "Lucas Gomes", "Marina Queiroz"]
POSTOS = ["Posto Cerrado", "Posto Pantanal", "Posto Chapada", "Auto Posto Araguaia", "Posto Trevo"]
MARCOS_KM = [10000, 20000, 30000, 40000, 50000]


def brl(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def placa(rnd: random.Random) -> str:
    letras = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(rnd.choice(letras) for _ in range(3)) + str(rnd.randrange(10)) + rnd.choice(letras) + f"{rnd.randrange(100):02d}"


def escrever(caminho: Path, cabecalho: list[str], linhas: list[list]) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cabecalho)
        w.writerows(linhas)
    print(f"{caminho.name}: {len(linhas)} linha(s)")


def main(pasta: Path, semente: int = 2026) -> None:
    rnd = random.Random(semente)
    pasta.mkdir(parents=True, exist_ok=True)

    # ---- veículos ----
    veiculos = []
    for _ in range(40):
        marca, modelo, _tipo = rnd.choice(MODELOS)
        veiculos.append([placa(rnd), marca, modelo, rnd.randint(2019, 2025), rnd.choice(SETORES)])
    escrever(pasta / "veiculos.csv", ["Placa", "Marca", "Modelo", "Ano", "Setor"], veiculos)
    placas = [v[0] for v in veiculos]

    # ---- abastecimentos ----
    abast = []
    km = {p: rnd.randint(5_000, 60_000) for p in placas}
    for _ in range(3_000):
        p = rnd.choice(placas)
        d = date(2025, 1, 1) + timedelta(days=rnd.randrange(700))
        km[p] += rnd.randint(150, 700)
        litros = round(rnd.uniform(25, 70), 2)
        preco = rnd.uniform(5.6, 6.9)
        data_txt = d.strftime("%d/%m/%Y")
        if rnd.random() < 0.004:
            data_txt = d.strftime("%d/%m/") + "0" + d.strftime("%Y")[1:]   # 2025 -> 0025
        placa_txt = p if rnd.random() > 0.05 else f" {p.lower()} "
        abast.append([data_txt, placa_txt, rnd.choice(MOTORISTAS), brl(litros), brl(litros * preco), km[p], rnd.choice(POSTOS)])
    escrever(pasta / "abastecimentos.csv", ["Data", "Placa", "Motorista", "Litros", "Valor", "KM", "Posto"], abast)

    # ---- revisões (formato largo) ----
    cab = ["Placa"] + [c for m in MARCOS_KM for c in (f"Rev {m} - Data", f"Rev {m} - KM", f"Rev {m} - Valor")]
    rev = []
    for p in placas:
        linha = [p]
        feitas = rnd.randint(0, len(MARCOS_KM))
        d = date(2025, 2, 1) + timedelta(days=rnd.randrange(60))
        for i, marco in enumerate(MARCOS_KM):
            if i < feitas:
                d += timedelta(days=rnd.randint(60, 150))
                linha += [d.strftime("%d/%m/%Y"), marco + rnd.randint(-800, 1_500), brl(rnd.uniform(450, 2_800))]
            else:
                linha += ["", "", ""]
        rev.append(linha)
    escrever(pasta / "revisoes_largo.csv", cab, rev)

    # ---- multas ----
    multas = []
    for _ in range(90):
        p = rnd.choice(placas) if rnd.random() > 0.05 else placa(rnd)   # ~5% órfãs
        d = date(2025, 1, 1) + timedelta(days=rnd.randrange(700))
        paga = rnd.random() < 0.7
        pagamento = (d + timedelta(days=rnd.randint(10, 60))).strftime("%d/%m/%Y") if paga else ""
        multas.append([d.strftime("%d/%m/%Y"), p, rnd.choice(MOTORISTAS),
                       rnd.choice(["Excesso de velocidade", "Estacionamento irregular", "Avanço de sinal"]),
                       brl(rnd.choice([88.38, 130.16, 195.23, 293.47])), pagamento])
    escrever(pasta / "multas.csv", ["Data Infração", "Placa", "Motorista", "Infração", "Valor", "Multa Paga"], multas)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dados_brutos"))
