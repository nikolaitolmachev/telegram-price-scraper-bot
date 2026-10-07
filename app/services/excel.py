from pathlib import Path

import pandas as pd

from app.models import ProductInput


REQUIRED_COLUMNS = {"title", "url", "selector"}

MAX_PRODUCTS = 100


def load_products(path: str | Path) -> list[ProductInput]:
    df = pd.read_excel(path)

    missing_columns = REQUIRED_COLUMNS - set(df.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing}")

    products: list[ProductInput] = []

    for _, row in df.iterrows():
        title = str(row["title"]).strip() if pd.notna(row["title"]) else ""
        url = str(row["url"]).strip() if pd.notna(row["url"]) else ""

        selector = None
        if pd.notna(row["selector"]):
            value = str(row["selector"]).strip()
            selector = value or None

        if not title or not url:
            continue

        products.append(
            ProductInput(
                title=title,
                url=url,
                selector=selector,
            )
        )

    if not products:
        raise ValueError("The file does not contain any valid product rows.")

    if len(products) > MAX_PRODUCTS:
        raise ValueError(f"Too many product rows: {len(products)}. Maximum allowed is {MAX_PRODUCTS}.")

    return products
