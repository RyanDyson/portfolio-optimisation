# Portfolio Optimisation

Mean-variance using CAPM analysis of a $100 million fund: six U.S.-listed common stocks selected from WRDS (CRSP monthly returns, Jan 2020 – Dec 2024) plus the one-month U.S. Treasury bill as the risk-free asset. All statistics are computed from monthly observations and annualized (mean ×12, standard deviation ×√12).

## Repository contents

| Path                        | Purpose                                                                                     |
| --------------------------- | ------------------------------------------------------------------------------------------- |
| `solution.ipynb`            | Main solution notebook (Tasks 1–7)                                                          |
| `data/crsp_monthly.csv`     | CRSP monthly returns exported from WRDS (columns: `PERMNO`, `Ticker`, `MthCalDt`, `MthRet`) |
| `data/rf_monthly.csv`       | One-month T-bill rate exported from WRDS (columns: `MthCalDt`, `Rf`)                        |
| `output/`                   | Generated outputs (Excel workbook, frontier chart)                                          |
| `Assignment 2026-27(1).pdf` | Assignment brief                                                                            |

## Setup

```powershell
# one-time: create the environment
python -m venv .venv
.venv\Scripts\python.exe -m pip install pandas numpy scipy matplotlib openpyxl jupyterlab nbconvert
```

## Usage

```powershell
.venv\Scripts\jupyter.exe lab
```

Then open `solution.ipynb` and **Run All**. The notebook writes:

- `output/EF3320_Assignment1_Challenge.xlsx` — one sheet per task (returns, risk-free rate, asset statistics, equal-weight portfolio, tangency portfolio, frontier coordinates, efficient-vs-equal-weight comparison, floor allocation). Key answer rows are bolded.
- `output/frontier.png` — minimum-variance frontier + capital allocation line chart.

## Before submitting

1. **6th asset** — Challenge requires six assets from ≥3 industries. Add your WRDS export to `data/crsp_monthly.csv` (the notebook auto-detects the ticker) and update the industry table in the Task 1 markdown cell.
2. **Risk-free rate** — `data/rf_monthly.csv` must exist with the same `MthCalDt`,`Rf` format; the load cell raises a clear error if missing. Document the source in the Task 1 cell.
3. **Task 7** — update the AI-verification text to your actual usage, and type it into the Excel file when finalizing.
4. Re-run the notebook on the real data before exporting the final Excel file.

## Notes

- `ALLOW_SHORT = False` (top of the notebook) enforces long-only weights; set to `True` for an unconstrained frontier.
- Duplicated CRSP rows are dropped automatically in the load step.
