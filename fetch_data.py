"""
got tired of duo secure
pull data directly from WRDS using python and SQL
credentials are saved on .env on first run
"""

import getpass
import io
import os
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

import wrds

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")
CRED_FILE = Path(".env")
DATA_DIR.mkdir(exist_ok=True)
START, END = "2020-01-31", "2024-12-31"
TICKERS = ["MSFT", "NVDA", "JPM", "XOM", "WMT", "JNJ"]


def load_credentials() -> tuple[str, str] | None:
  user = os.getenv("WRDS_USERNAME", "")
  pw = os.getenv("WRDS_PASSWORD", "")
  if user and pw:
    return user, pw
  if not CRED_FILE.exists():
    return None
  for line in CRED_FILE.read_text(encoding="utf-8").splitlines():
    key, _, value = line.partition("=")
    key, value = key.strip(), value.strip()
    if key == "WRDS_USERNAME" and not user:
      user = value
    elif key == "WRDS_PASSWORD" and not pw:
      pw = value
  if user and pw:
    return user, pw
  return None


def prompt_credentials() -> tuple[str, str]:
  user = input("WRDS username: ").strip()
  pw = getpass.getpass(f"WRDS password (for {user}): ")
  save = input("Save credentials to .env so future runs are automatic? [y/n]: ").strip().lower()
  if save == "y":
    CRED_FILE.write_text(f"WRDS_USERNAME={user}\nWRDS_PASSWORD={pw}\n", encoding="utf-8")
    print(f"Saved {CRED_FILE.resolve()} - it is gitignored, but never share or upload this file.")
  return user, pw


def connect() -> wrds.Connection:
  creds = load_credentials()
  while True:
    if not creds:
      creds = prompt_credentials()
    user, pw = creds
    try:
      db = wrds.Connection(wrds_username=user, wrds_password=pw)
      print(f"Connected to WRDS as {user}")
      return db
    except Exception as err:
      print(f"Login failed ({err}). Please re-enter your credentials.")
      creds = None


def _check_schema(db: wrds.Connection, table: str, required: list[str]) -> None:
  cols = db.raw_sql(
    """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema || '.' || table_name = %(table)s
    """,
    params={"table": table},
  )["column_name"].tolist()
  if not cols:
    raise SystemExit(
      f"{table} was not found in your WRDS subscription (information_schema "
      "has no columns for it) - check the schema/table name and your "
      "CRSP product access, or write the fix into fetch_stock_data()."
    )
  missing = [c for c in required if c not in cols]
  if missing:
    raise SystemExit(
      f"{table} is missing the expected columns {missing}.\n"
      f"Available columns: {sorted(cols)}\n"
      "Adjust the SQL in fetch_stock_data() to match this schema."
    )


def fetch_stock_data(db: wrds.Connection) -> pd.DataFrame:
  _check_schema(db, "crsp.msf_v2",
                ["permno", "permco", "mthcaldt", "mthret", "primaryexch",
                 "sharetype", "securitytype", "securitysubtype",
                 "usincflg", "issuertype"])
  _check_schema(db, "crsp.stocknames",
                ["permno", "ticker", "comnam", "siccd", "namedt", "nameenddt"])
  names = db.raw_sql(
    """
    SELECT DISTINCT ON (UPPER(ticker)) permno, UPPER(ticker) AS ticker, comnam, siccd, namedt
    FROM crsp.stocknames
    WHERE UPPER(ticker) = ANY(%(tickers)s)
      AND st_date <= %(end)s
      AND COALESCE(nameenddt, DATE '9999-12-31') >= %(start)s
    ORDER BY UPPER(ticker), st_date DESC
    """,
    params={"tickers": TICKERS, "start": START, "end": END},
  )
  permnos = names["permno"].tolist()
  print(f"Matched {len(names)} / {len(TICKERS)} tickers to CRSP identifiers")
  returns = db.raw_sql(
    """
    SELECT permno, permco, mthcaldt, mthret, primaryexch, sharetype
    FROM crsp.msf_v2
    WHERE mthcaldt BETWEEN %(start)s AND %(end)s
      AND permno = ANY(%(permnos)s)
      AND sharetype = 'NS'
      AND securitytype = 'EQTY'
      AND securitysubtype = 'COM'
      AND usincflg = 'Y'
      AND issuertype IN ('ACOR', 'CORP')
    """,
    params={"start": START, "end": END, "permnos": permnos},
  )

  indu = db.raw_sql(
    """
    SELECT DISTINCT ON (permno) permno, siccd, comnam
    FROM crsp.stocknames
    WHERE permno = ANY(%(permnos)s)
    ORDER BY permno, st_date DESC
    """,
    params={"permnos": permnos},
  )

  df = returns.merge(names[["permno", "ticker"]], on="permno", how="left")
  df = df.merge(indu, on="permno", how="left")
  return df


def write_stock_csv(df: pd.DataFrame) -> None:
  out = "data/crsp_monthly.csv"

  tidy = pd.DataFrame({
    "PERMNO": df["permno"].astype(int),
    "PERMCO": df["permco"].astype(int),
    "MthCalDt": pd.to_datetime(df["mthcaldt"]).dt.strftime("%Y-%m-%d"),
    "MthRet": df["mthret"],
    "Ticker": df["ticker"].astype(str).str.upper(),
    "PrimaryExch": df["primaryexch"],
    "ShareType": df["sharetype"],
    "SIC": df["siccd"].astype("Int64"),
    "Company": df["comnam"],
  })

  tidy = tidy.dropna(subset=["MthRet"])

  tidy.to_csv(out, index=False)


  counts = tidy.groupby("Ticker").size()
  months_per_ticker = tidy.dropna(subset=["MthRet"]).groupby("Ticker")["MthCalDt"].nunique()
  print("Rows per ticker:")
  print(counts.to_string())
  low = months_per_ticker[months_per_ticker < 60]
  assert low.empty, f"Incomplete histories (<60 months): {low.to_dict()}"
  n_industries = tidy.dropna(subset=["SIC"])["SIC"].map(sic_industry).nunique()
  print(f"Distinct industries (SIC-based): {n_industries}")
  print(f"Wrote {out}")


def sic_industry(sic: int) -> str:
  try:
    sic = int(sic)
  except (TypeError, ValueError):
    return "Unknown"
  ranges = {
    "Agriculture": (0, 999),
    "Mining": (1000, 1499),
    "Construction": (1500, 1799),
    "Healthcare": (2830, 2839),
    "Manufacturing": (2000, 3999),
    "Transport/Utilities": (4000, 4999),
    "Retail/Wholesale": (5000, 5999),
    "Financials": (6000, 6799),
    "Services": (7000, 8999),
  }
  for name, (lo, hi) in ranges.items():
    if lo <= sic <= hi:
      return name
  return "Other"


def fetch_risk_free() -> pd.Series:
  url = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip"
  print(f"Downloading risk-free rate from {url}")
  raw = urllib.request.urlopen(url, timeout=120).read()
  z = zipfile.ZipFile(io.BytesIO(raw))
  with z.open(z.namelist()[0]) as f:
    lines = io.TextIOWrapper(f, encoding="ascii", errors="ignore").read().splitlines()

  header_idx = next(i for i, line in enumerate(lines) if line.startswith(","))
  rows = []
  for line in lines[header_idx + 1:]:
    if not line.strip():
      break
    date, _, _, _, rf = [part.strip() for part in line.split(",")]
    rows.append((pd.Period(date, freq="M"), float(rf) / 100))

  rf = pd.Series(dict(rows), name="Rf")
  return rf


def align_rf(rf: pd.Series, month_ends: pd.Index) -> pd.DataFrame:
  out = pd.DataFrame({
    "MthCalDt": month_ends,
    "Rf": [rf.loc[pd.Period(f"{d.year}-{d.month:02d}", freq="M")] for d in month_ends],
  })
  assert out["Rf"].notna().all(), "Risk-free rate missing for some months"
  return out


def main() -> None:
  with connect() as db:
    stock_data = fetch_stock_data(db)
  write_stock_csv(stock_data)

  rf = fetch_risk_free()
  month_ends = sorted(pd.to_datetime(stock_data["mthcaldt"]).unique())
  write_risk_free = align_rf(rf, month_ends)
  write_risk_free.to_csv("data/rf_monthly.csv", index=False)
  print(f"Wrote data/rf_monthly.csv ({len(write_risk_free)} months)")
  print("Done - run solution.ipynb next.")


if __name__ == "__main__":
  main()
