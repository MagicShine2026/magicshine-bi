from __future__ import annotations
import pandas as pd


def summarize(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"venta":0,"unidades":0,"tiendas":0,"skus":0,"ticket":0}
    venta = float(df["venta"].sum())
    unidades = float(df["unidades"].sum())
    return {
        "venta": venta,
        "unidades": unidades,
        "tiendas": int(df["tienda"].nunique()),
        "skus": int(df["sku"].nunique() if "sku" in df else df["producto"].nunique()),
        "ticket": venta / unidades if unidades else 0,
    }


def month_growth(df: pd.DataFrame) -> float | None:
    monthly = df.groupby("mes", as_index=False)["venta"].sum().sort_values("mes")
    if len(monthly) < 2:
        return None
    prev = monthly.iloc[-2]["venta"]
    curr = monthly.iloc[-1]["venta"]
    if prev == 0:
        return None
    return (curr / prev - 1) * 100


def top_table(df: pd.DataFrame, by: str, n: int = 10) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[by, "venta", "unidades"])
    return (df.groupby(by, as_index=False)
              .agg(venta=("venta","sum"), unidades=("unidades","sum"))
              .sort_values("venta", ascending=False)
              .head(n))
