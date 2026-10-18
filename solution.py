from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")
STOCK_FILE = DATA_DIR / "crsp_monthly.csv"
RF_FILE = DATA_DIR / "rf_monthly.csv"

OUTPUT_DIR.mkdir(exist_ok=True)

ALLOW_SHORT = False

def load_data():
  stock_data = pd.read_csv(STOCK_FILE, parse_dates=["MthCalDt"])
  rf_data = pd.read_csv(RF_FILE, parse_dates=["MthCalDt"])
  return stock_data, rf_data

stocks, rf = load_data()
returns = stocks.pivot(index="MthCalDt", columns="Ticker", values="MthRet")

rf = rf.set_index("MthCalDt").sort_index()["Rf"]
data = returns.join(rf, how="inner")

tickers = data.columns[:-1]

R = data[tickers]
rf_monthly = data["Rf"]

mu = R.mean()
cov = R.cov()

n = len(tickers)

def portfolio_return(w): 
  return float(w @ mu.to_numpy())

def portfolio_variance(w):
  return float(w @ cov.to_numpy() @ w)

def optimize_min_var(exp_return): 
  constraints = [
    {
      "type": "eq",
      "f": lambda w: np.sum(w) -1,
    },
    {
      "type": "eq",
      "f": lambda w: portfolio_return(w) - exp_return,
    },
  ]

  bounds = [(0, 1) for _ in range(n)] if not ALLOW_SHORT else None
  result = minimize(portfolio_variance, x0=np.ones(n)/n, bounds=bounds, constraints=constraints)
  return result.x

def sharpe_ratio(w):
  ret = portfolio_return(w)
  rf_mean = float(rf_monthly.mean())
  sd = np.sqrt(portfolio_variance(w))
  return (ret - rf_mean) / sd

def tangency_portfolio():
  constraints = [
    {
      "type": "eq",
      "f": lambda w: np.sum(w) -1,
    },
  ]

  bounds = [(0, 1) for _ in range(n)] if not ALLOW_SHORT else None
  result = minimize(lambda w: -sharpe_ratio(w), x0=np.ones(n)/n, bounds=bounds, constraints=constraints)
  return result.x

tangency_res = tangency_portfolio()
tangency_weights = tangency_res.x

targets = 

exp_months = 60