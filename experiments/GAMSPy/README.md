# GAMSPy - Problema de Seleção de Processos

Scripts Python/GAMSPy gerados automaticamente a partir dos modelos GAMS originais.

## Estrutura

```
GAMSPy/
├── 2X/           10 instâncias  T=38  J=159  RESLIM=3600s
├── 3X/           10 instâncias  T=57  J=159  RESLIM=3600s
├── 4X/           10 instâncias  T=76  J=159  RESLIM=3600s
├── 5X/           10 instâncias  T=95  J=159  RESLIM=3600s
├── Real/         10 instâncias  T=25  J=160  RESLIM=3600s
├── run_all.py    Runner para todas as instâncias
└── README.md     Este arquivo
```

## Pré-requisitos

```bash
pip install gamspy pandas
gamspy install solver CPLEX
```

## Como rodar

```bash
# Uma instância
python GAMSPy/Real/Ale_1.py

# Todas as instâncias
python GAMSPy/run_all.py

# Um conjunto específico
python GAMSPy/run_all.py Real
python GAMSPy/run_all.py 2X 3X
```

## Modelo

Minimiza a falta de produção `Z = sum(F[i,t] + 0.001*E[i,t])` sujeito a:

- **DEMANDA**: produção acumulada até t + falta - excesso = demanda acumulada até t
- **PROPORÇÃO**: no máximo um processo ativo por período

Variável `X[j,t]` binária indica se o processo j é usado no período t.
