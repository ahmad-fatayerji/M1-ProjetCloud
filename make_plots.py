#!/usr/bin/env python3
import os
import pandas as pd
import matplotlib.pyplot as plt
import re

OUT_DIR = "out"  # folder where conc.csv, post.csv, fanout.csv live, and where PNGs will be written


def load_and_prepare(csv_name: str) -> pd.DataFrame:
    """
    Load a CSV from OUT_DIR, normalize column names, handle different separators,
    drop FAILED==1 rows if the column exists, convert AVG_TIME to milliseconds (float),
    and compute mean/std per PARAM.
    """
    path = os.path.join(OUT_DIR, csv_name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV file not found: {path}")

    # Auto-detect separator (comma, semicolon, tab, etc.)
    df = pd.read_csv(path, sep=None, engine="python", header=None)

    # Check if first row looks like a header (contains non-numeric values like "PARAM")
    first_row = df.iloc[0]
    has_header = any(
        isinstance(val, str) and not val.replace('.', '').replace('-', '').isdigit()
        for val in first_row
    )

    if has_header:
        # First row is header, use it as column names
        df.columns = [str(c).strip().upper() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
    else:
        # No header, assign default column names based on number of columns
        if len(df.columns) == 4:
            df.columns = ["PARAM", "AVG_TIME", "RUN", "FAILED"]
        elif len(df.columns) == 3:
            df.columns = ["PARAM", "AVG_TIME", "RUN"]
        else:
            df.columns = ["PARAM", "AVG_TIME"] + [f"COL{i}" for i in range(2, len(df.columns))]

    # Normalize column names to uppercase without surrounding spaces
    df.columns = [c.strip().upper() for c in df.columns]

    required = {"PARAM", "AVG_TIME"}
    if not required.issubset(df.columns):
        raise ValueError(
            f"{csv_name} must contain at least columns: {required}. "
            f"Found: {list(df.columns)}"
        )

    # Convert FAILED column to numeric if present, then filter
    if "FAILED" in df.columns:
        df["FAILED"] = pd.to_numeric(df["FAILED"], errors="coerce").fillna(0)
        df = df[df["FAILED"] == 0]

    # Convert AVG_TIME to milliseconds (float)
    # - Accept values like "10ms", "10 ms", "0.01s", "0,01s", etc.
    def to_ms(x):
        s = str(x).strip().lower()
        # Extract numeric part
        m = re.search(r"([\d.,]+)", s)
        if not m:
            return float("nan")
        num = m.group(1).replace(",", ".")
        value = float(num)

        # Decide unit
        if "ms" in s:
            return value
        if "s" in s:
            return value * 1000.0  # seconds -> ms
        # default assume already ms
        return value

    df["AVG_TIME"] = df["AVG_TIME"].map(to_ms)

    # PARAM may be numeric or string; keep the original but also a numeric version for sorting
    df["PARAM_NUM"] = pd.to_numeric(df["PARAM"], errors="coerce")

    # Group by PARAM (string) to preserve labels
    grouped = (
        df.groupby("PARAM")["AVG_TIME"]
        .agg(["mean", "std"])
        .reset_index()
        .rename(columns={"mean": "MEAN", "std": "STD"})
    )

    # Replace NaN std (e.g. if only 1 run) by 0 so matplotlib doesn't complain
    grouped["STD"] = grouped["STD"].fillna(0.0)

    # Add numeric version of PARAM to sort (if possible)
    grouped["PARAM_NUM"] = pd.to_numeric(grouped["PARAM"], errors="coerce")
    grouped = grouped.sort_values(by=["PARAM_NUM", "PARAM"], na_position="last")

    return grouped


def make_barplot(data: pd.DataFrame, title: str, xlabel: str, ylabel: str, output_name: str):
    """
    Create a barplot with error bars (std dev) and save it to OUT_DIR/output_name.
    """
    if data.empty:
        raise ValueError(f"No data available to plot for {output_name}")

    x = range(len(data))
    heights = data["MEAN"]
    errors = data["STD"]

    plt.figure()
    plt.bar(x, heights, yerr=errors, capsize=5)
    plt.xticks(x, data["PARAM"])
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()

    out_path = os.path.join(OUT_DIR, output_name)
    plt.savefig(out_path)
    plt.close()
    print(f"Saved plot: {out_path}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # -------- 1) conc.png --------
    conc = load_and_prepare("conc.csv")
    make_barplot(
        conc,
        title="Temps moyen par requête selon la concurrence",
        xlabel="Nombre d’utilisateurs concurrents",
        ylabel="Temps moyen par requête (ms)",
        output_name="conc.png",
    )

    # -------- 2) post.png --------
    post = load_and_prepare("post.csv")
    make_barplot(
        post,
        title="Temps moyen par requête selon le nombre de posts par utilisateur",
        xlabel="Nombre de posts par utilisateur",
        ylabel="Temps moyen par requête (ms)",
        output_name="post.png",
    )

    # -------- 3) fanout.png --------
    fanout = load_and_prepare("fanout.csv")
    make_barplot(
        fanout,
        title="Temps moyen par requête selon le nombre de followees",
        xlabel="Nombre de followees par utilisateur",
        ylabel="Temps moyen par requête (ms)",
        output_name="fanout.png",
    )


if __name__ == "__main__":
    main()
