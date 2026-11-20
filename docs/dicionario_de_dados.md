# Dicionário de dados

Arquivos em CSV com separador `;`, decimal `,` e codificação UTF-8 com BOM (abrem direto no Excel e no Power BI em português).

## Dimensões

### DimData
Granularidade: um dia. Cobre do primeiro ao último ano com movimento.

| Coluna | Tipo | Descrição |
|---|---|---|
| IdData | inteiro | Chave no formato AAAAMMDD |
| Data | data | Data no formato dd/mm/aaaa |
| Ano | inteiro | Ano |
| MesNumero | inteiro | Mês (1 a 12), usado para ordenar `Mes` |
| Mes | texto | Mês abreviado (jan, fev, ...) |
| AnoMes | texto | AAAA-MM |
| Trimestre | texto | T1 a T4 |
| DiaUtil | inteiro | 1 para segunda a sexta, 0 para fim de semana |

### DimVeiculo
Granularidade: um veículo.

| Coluna | Tipo | Descrição |
|---|---|---|
| IdVeiculo | inteiro | Chave substituta |
| Placa | texto | Placa normalizada (maiúsculas, sem espaços) |
| Marca | texto | Fabricante |
| Modelo | texto | Modelo e versão |
| Ano | inteiro | Ano de fabricação |
| Setor | texto | Setor responsável pelo veículo |
| TipoVeiculo | texto | Picape, Passeio, Van ou Caminhão. **Derivado** do modelo |

### DimMotorista
| Coluna | Tipo | Descrição |
|---|---|---|
| IdMotorista | inteiro | Chave substituta |
| Motorista | texto | Nome do condutor |

### DimPosto
| Coluna | Tipo | Descrição |
|---|---|---|
| IdPosto | inteiro | Chave substituta |
| Posto | texto | Nome do estabelecimento |

## Fatos

### FatoAbastecimento
Granularidade: um abastecimento.

| Coluna | Tipo | Descrição |
|---|---|---|
| IdAbastecimento | inteiro | Chave da linha |
| IdData | inteiro | Data do abastecimento. Nulo quando a data de origem era implausível |
| IdVeiculo, IdMotorista, IdPosto | inteiro | Chaves das dimensões |
| Litros | decimal | Volume abastecido |
| Valor | decimal | Valor pago (R$) |
| PrecoLitro | decimal | Valor ÷ Litros |
| KM | inteiro | Hodômetro no abastecimento. **Não aditivo**: use máximo menos mínimo |

### FatoRevisao
Granularidade: uma revisão preventiva realizada (resultado do *unpivot*).

| Coluna | Tipo | Descrição |
|---|---|---|
| IdRevisao | inteiro | Chave da linha |
| IdData | inteiro | Data da revisão |
| IdVeiculo | inteiro | Chave do veículo |
| KMPrevisto | inteiro | Marco de quilometragem da revisão (10.000, 20.000, ...) |
| KMRealizado | inteiro | Hodômetro quando a revisão foi feita |
| DesvioKM | inteiro | KMRealizado − KMPrevisto. Positivo indica revisão atrasada |
| Valor | decimal | Custo da revisão (R$) |

### FatoMulta
Granularidade: uma infração.

| Coluna | Tipo | Descrição |
|---|---|---|
| IdMulta | inteiro | Chave da linha |
| IdData | inteiro | Data da infração |
| IdVeiculo, IdMotorista | inteiro | Chaves das dimensões |
| Infracao | texto | Tipo de infração |
| Valor | decimal | Valor da multa (R$) |
| Paga | texto | "Sim" quando há data de pagamento |
| IdDataPagamento | inteiro | Data do pagamento (relacionamento inativo com DimData) |
| DiasAtePagamento | inteiro | Dias entre a infração e o pagamento |

## Qualidade

| Arquivo | Conteúdo |
|---|---|
| `log_qualidade.csv` | Uma linha por regra aplicada: tabela, regra, quantidade de registros e exemplos |
| `registros_orfaos.csv` | Registros removidos das fatos por não terem correspondência em uma dimensão |
