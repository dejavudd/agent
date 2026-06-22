$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

python .\generate_figures.py
xelatex -interaction=nonstopmode -halt-on-error agentic_study_system_design.tex
xelatex -interaction=nonstopmode -halt-on-error agentic_study_system_design.tex

Write-Host "Report built: $scriptDir\agentic_study_system_design.pdf"
