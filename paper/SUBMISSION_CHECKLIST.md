# Submission Checklist

## Current Verified State

- Draft pages: 41 (`pdfinfo paper/main.pdf`).
- Bibliography: 48 entries, all cited (`python analysis/verify_manuscript_numbers.py`).
- Remaining manuscript markers: 4 `\todo{}` markers.
- Repository size excluding `.git` and ignored `release/`: approximately 53.60 MiB.
- Public package: 1,834 files, 7,201,192 bytes (approximately 6.87 MiB).
- GitHub repository visibility: `PUBLIC` as reported by `gh repo view daleluche/Treibacher --json visibility`; changing visibility is an author action in GitHub.
- `release/` remains ignored by `.gitignore`, and no files under `release/` are tracked.

## Author

- Fill the anonymized company-facts paragraph at `paper/sections/problem_model.tex:27`.
- Fill acknowledgements and funding agencies at `paper/main.tex:98`.
- Provide the corresponding-author e-mail for the front matter.
- Confirm the two affiliations currently written as:
  - São Paulo State University (UNESP), Guaratinguetá, SP, Brazil.
  - Department of Production Engineering, Federal University of São Carlos (UFSCar), São Carlos, SP, Brazil.
- Decide the final authorship composition and order.
- Deposit the public benchmark package on Zenodo and insert the DOI in the two current markers:
  - `paper/main.tex:105`
  - `paper/sections/experiments.tex:25`
- Make the GitHub repository private if that is still desired before submission.

## Automatic After the DOI

- Replace the two `\todo{Zenodo DOI}` markers.
- Run `make submission` from `paper/`.
- Re-run `python analysis/verify_manuscript_numbers.py`.
- Rebuild the release package with `python analysis/build_release_package.py` if the DOI or package metadata changes.

## Journal

- Check the current *Computers & Operations Research* Guide for Authors before submission, especially highlights, CRediT author contribution statement, declaration of interests, data availability, and any journal-specific source-file requirements.
- Check Elsevier's current generative-AI disclosure policy. The current guide says authors must declare generative AI or AI-assisted technology use in manuscript preparation when applicable.
- Confirm whether the journal wants a separate declaration for AI-assisted coding/data-analysis support or only writing-process support.

Reference checked during C12: https://www.sciencedirect.com/journal/computers-and-operations-research/publish/guide-for-authors

## Verified Build and Package Checks

- `python analysis/verify_manuscript_numbers.py` passes.
- `make draft` passes and produces 41 pages.
- `make submission` must be run once the DOI/company/front-matter markers are resolved.
- `python analysis/build_release_package.py` creates `release/psp_electrofused_benchmark_v1.zip`.
- A second package generation is byte-identical to the first.
- The ZIP does not contain `REAL_1` or `results_production/real/`.
- `checksums.sha256` validates every listed file.
- `release/README.md` states the policy used in the manuscript: 60 derived benchmark instances are released; the real order book is not released because it is a commercial order book.
