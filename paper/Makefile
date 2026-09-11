.PHONY: draft submission clean

draft:
	pdflatex -interaction=nonstopmode -halt-on-error main.tex
	bibtex main
	pdflatex -interaction=nonstopmode -halt-on-error main.tex
	pdflatex -interaction=nonstopmode -halt-on-error main.tex

submission:
	if not exist build mkdir build
	pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build -jobname=main "\def\submissionbuild{}\input{main.tex}"
	bibtex build/main
	pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build -jobname=main "\def\submissionbuild{}\input{main.tex}"
	pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build -jobname=main "\def\submissionbuild{}\input{main.tex}"
	powershell -NoProfile -ExecutionPolicy Bypass -Command "$$ErrorActionPreference = 'Stop'; Remove-Item -Recurse -Force -ErrorAction SilentlyContinue 'build/sources'; New-Item -ItemType Directory -Force 'build/sources' | Out-Null; Copy-Item -Recurse -Force 'sections','tables','figures','references.bib','elsarticle-harv.bst' 'build/sources'; $$main = Get-Content -Raw 'main.tex'; Set-Content -Encoding UTF8 'build/sources/main.tex' (\"\\def\\submissionbuild{}`r`n\" + $$main)"

clean:
	powershell -NoProfile -ExecutionPolicy Bypass -Command "Remove-Item -Force -ErrorAction SilentlyContinue *.aux,*.bbl,*.blg,*.log,*.out,*.spl; if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' }"
