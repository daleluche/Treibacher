# paper/ — manuscrito C&OR (PSP grãos eletrofundidos)

## Estrutura
- `main.tex` — arquivo principal (classe **elsarticle**, opção authoryear).
- `sections/` — introdução e related work REDIGIDOS; demais seções são
  esqueletos comentados com o plano de conteúdo (aguardam Sprint 2).
- `references.bib` — 48 entradas; flags `% [OK]` (verificada em busca) e
  `% [VERIFY]` (conferir campos antes da submissão).
- `main_localtest.tex` — wrapper de validação que compila com a classe
  `article` + shims (uso local/CI apenas; NÃO é o build de submissão).
- `elsarticle-harv.bst` — estilo bibliográfico Elsevier (incluído).

## Builds
Requer `elsarticle.cls` (Overleaf já tem; no TeX Live:
`tlmgr install elsarticle`) e as ferramentas `pdflatex` e `bibtex`.

- `make draft` compila `main.tex` normalmente e mantém visíveis os
  marcadores editoriais `\todo{...}` e `\sprintii{...}` no PDF de
  trabalho (`main.pdf`).
- `make submission` compila com `\submissionbuild` definido, removendo
  esses marcadores do PDF final em `build/main.pdf`. O alvo também
  monta `build/sources/` com os arquivos necessários para submissão; o
  `main.tex` copiado ali já recebe `\def\submissionbuild{}` no topo, de
  modo que o pacote compile sem flags adicionais.

## Convenções de rascunho
- `\todo{...}` (vermelho): pendência de escrita.
- `\sprintii{...}` (azul): número/afirmativa que depende do relatório
  da Sprint 2 — não redigir antes do veredito de H1–H4.
