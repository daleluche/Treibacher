# C11 Bibliography Verification Log

This log replaces the earlier bibliography notes described in the C11 brief. The earlier
report diverged from the actual `references.bib` file, so every entry with `TODO` or
`[VERIFY]` was rechecked from the file state current at the start of C11.

## Corrected Entries

- `luche2005otimizacao`: completed journal, volume, number, pages, and DOI from SciELO
  and cross-citations in Villas Boas et al. (2021). Final fields: `Gestao & Producao`,
  12(1), 135--149, DOI `10.1590/S0104-530X2005000100012`.
- `toledo2015sitlsp`: replaced `others` with Toledo, Kimms, Franca, and Morabito;
  added DOI `10.1155/2015/182781`. Source: Wiley/Hindawi and RePEc records.
- `leachman2002semiconductor`: added editors, address, and pages 746--762 from the
  Handbook of Applied Optimization table of contents and chapter PDF metadata.
- `ng2007robust`: replaced `others` with Ng and Fowler; added pages 1073--1077 and
  DOI `10.1109/IEEM.2007.4419357`. Source: Arizona State University Pure record.
- `silva2023formulations`: added volume 304, number 2, pages 443--460, and DOI
  `10.1016/j.ejor.2022.04.023`. Source: ScienceDirect/Strathprints/RePEc records.
- `furlan2024matheuristic`: replaced `others` with Furlan, Almada-Lobo, Santos, and
  Morabito; added volume 192, article 110183, and DOI `10.1016/j.cie.2024.110183`.
  Source: ScienceDirect and FAPESP records.
- `toscano2020formulation`: removed the TODO note and added DOI
  `10.1016/j.compchemeng.2020.107038`. Source: Crossref.
- `jors2021perishable`: completed authors Soler, Santos, and Akartunali; added pages
  1691--1706 and DOI `10.1080/01605682.2019.1640588`. Source: Taylor & Francis,
  Strathprints, and Crossref.
- `gleixner2021miplib`: replaced `others` with the full Crossref author list and added
  issue 3 and DOI `10.1007/s12532-020-00194-3`. Source: Springer/Crossref.
- `fischetti2018matheuristics`: corrected authors to Martina Fischetti and Matteo
  Fischetti and added DOI `10.1007/978-3-319-07124-4_14`. Source: Springer/Crossref.

## Verified Entries

The following entries were checked against Crossref, Springer, INFORMS, ScienceDirect,
or publisher/library records and marked `% [OK]`: `karmarkar1985deterministic`,
`fleischmann1990dlsp`, `drexl1995proportional`, `haase1996clsd`,
`fleischmann1997general`, `drexl1997lotsizing`, `karimi2003capacitated`,
`jans2008modeling`, `buschkuhl2010dynamic`, `glock2014tertiary`,
`copil2017simultaneous`, `worbelauer2019secondary`, `pochet2006production`,
`martinez2018coupled`, `araujo2008foundry`, `toso2009lot`, `clark2010production`,
`villasboas2021modeling`, `ferreira2009solution`, `dillenberger1994practical`,
`sahling2009solving`, `helber2010fix`, `toledo2015relax`, `santos2012integrated`,
`figueira2013hybrid`, `james2011single`, `wolsey2002solving`, `feo1995greedy`,
`prais2000reactive`, `lourenco2010iterated`, `laguna1999grasp`,
`resende2016optimization`, `aiex2007ttt`, `koch2022progress`,
`achterberg2013analyzing`, `achterberg2020presolve`, `bixby2012brief`,
`dolan2002benchmarking`, and `baker1977experimental`.

## Remaining TODO or VERIFY Fields

None remain in `paper/references.bib` after C11. Any unresolved items are editorial
markers in the manuscript, not bibliography fields.

## Uncited Entries

At the start of C11, the BibTeX file contained 51 entries and the manuscript cited 48.
The uncited entries were:

- The obsolete 2011 thesis entry was removed, as instructed. No citation to that key
  remained in the manuscript.
- `luche2005otimizacao`: retained. Recommendation: keep available for possible use in
  the historical/provenance discussion or remove after the senior researcher confirms it
  is not needed.
- `wolsey2002solving`: retained. Recommendation: either cite it in the MIP/lot-sizing
  formulation discussion or remove it if the bibliography should contain only cited work.

## Primary Sources Used

- SciELO article page for Luche and Morabito (2005):
  https://www.scielo.br/j/gp/a/Ktrdtc8rFSxbMYdTLnYNjPR/?lang=pt
- Taylor & Francis DOI page for Soler, Santos, and Akartunali (2021):
  https://www.tandfonline.com/doi/abs/10.1080/01605682.2019.1640588
- Wiley/Hindawi DOI page for Toledo et al. (2015):
  https://onlinelibrary.wiley.com/doi/10.1155/2015/182781
- ScienceDirect page for Furlan et al. (2024):
  https://www.sciencedirect.com/science/article/pii/S0360835224003048
- Springer DOI page for MIPLIB 2017:
  https://link.springer.com/article/10.1007/s12532-020-00194-3
- Springer DOI page for Haase (1996):
  https://link.springer.com/article/10.1007/BF01539882
- ASU Pure record for Ng and Fowler (2007):
  https://asu.elsevierpure.com/en/publications/semiconductor-production-planning-using-robust-optimization/
- Handbook of Applied Optimization chapter metadata:
  https://ieor.berkeley.edu/wp-content/uploads/2019/10/Handbook-of-Applied-Optimization-Leachman-Chapter.pdf
- Crossref API records for DOI-bearing entries, used as the normalizing source for
  authors, volumes, issues, pages, and DOI strings where publisher pages were not opened
  separately.
