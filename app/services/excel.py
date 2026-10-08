"""Loading and validation of product rows from Excel workbooks."""

from pathlib import Path

import pandas as pd

from app.models import ProductInput


REQUIRED_COLUMNS = {"title", "url", "selector"}

MAX_PRODUCTS = 400


def load_products(path: str | Path) -> list[ProductInput]:
    """Load product rows from an Excel workbook.

    The workbook must contain title, url and selector columns. Rows
    without a title or a URL are skipped, and a blank selector cell is
    stored as None.

    Args:
        path: Path to the .xlsx file.

    Returns:
        The parsed products in file order.

    Raises:
        ValueError: If required columns are missing, no valid rows remain,
            or the row count exceeds MAX_PRODUCTS.
    """
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
