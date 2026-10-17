"""Loading and validation of product rows from Excel workbooks."""

from pathlib import Path

import pandas as pd

from app.models import ProductInput

REQUIRED_COLUMNS = {"title", "url", "selector"}

MAX_PRODUCTS = 400


def load_products(path: str | Path) -> list[ProductInput]:
    """Load and validate product rows from the first Excel worksheet.

    The worksheet must contain title, url and selector columns with these
    exact names. Skip rows without a title or URL, trim surrounding whitespace
    and store a blank selector as None. Enforce MAX_PRODUCTS on the remaining
    valid rows after reading the worksheet. URL syntax is not validated here.
    Workbook reading errors from pandas propagate to the caller.

    Args:
        path: Path to the .xlsx file.

    Returns:
        The valid product inputs in worksheet order.

    Raises:
        ValueError: If required columns are missing, no valid rows remain,
            or the number of valid product rows exceeds MAX_PRODUCTS.
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
