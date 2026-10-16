"""Test Excel loading, column validation and product row limits."""

import pandas as pd
import pytest

from app.services.excel import MAX_PRODUCTS, load_products


def test_load_products_from_valid_excel(tmp_path) -> None:
    """Load product inputs in worksheet order and preserve an empty selector."""
    file_path = tmp_path / "products.xlsx"

    dataframe = pd.DataFrame(
        [
            {
                "title": "Test Product 1",
                "url": "https://example.com/1",
                "selector": ".price",
            },
            {
                "title": "Test Product 2",
                "url": "https://example.com/2",
                "selector": None,
            },
        ]
    )

    dataframe.to_excel(file_path, index=False)

    products = load_products(file_path)

    assert len(products) == 2

    assert products[0].title == "Test Product 1"
    assert products[0].url == "https://example.com/1"
    assert products[0].selector == ".price"

    assert products[1].title == "Test Product 2"
    assert products[1].url == "https://example.com/2"
    assert products[1].selector is None


def test_load_products_with_missing_columns(tmp_path) -> None:
    """Reject a worksheet missing the required selector column."""
    file_path = tmp_path / "missing_columns.xlsx"

    dataframe = pd.DataFrame(
        [
            {
                "title": "Test Product",
                "url": "https://example.com/product",
            }
        ]
    )
    dataframe.to_excel(file_path, index=False)

    with pytest.raises(ValueError, match="Missing required columns: selector"):
        load_products(file_path)


def test_load_products_with_empty_rows(tmp_path) -> None:
    """Reject a worksheet with no valid product inputs."""
    file_path = tmp_path / "empty_rows.xlsx"

    dataframe = pd.DataFrame(
        [
            {
                "title": None,
                "url": None,
                "selector": None,
            },
        ]
    )
    dataframe.to_excel(file_path, index=False)

    with pytest.raises(ValueError, match="does not contain any valid product rows"):
        load_products(file_path)


def test_load_products_skips_invalid_rows(tmp_path) -> None:
    """Skip rows missing a title or URL while keeping valid rows."""
    file_path = tmp_path / "invalid_rows.xlsx"

    dataframe = pd.DataFrame(
        [
            {
                "title": "Valid Product",
                "url": "https://example.com/product",
                "selector": None,
            },
            {
                "title": None,
                "url": "https://example.com/other",
                "selector": None,
            },
            {
                "title": "Missing URL",
                "url": None,
                "selector": None,
            },
        ]
    )
    dataframe.to_excel(file_path, index=False)

    products = load_products(file_path)

    assert len(products) == 1
    assert products[0].title == "Valid Product"
    assert products[0].url == "https://example.com/product"


def test_load_products_exceeds_limit(tmp_path) -> None:
    """Reject a worksheet with more than MAX_PRODUCTS valid product rows."""
    file_path = tmp_path / "too_many_products.xlsx"

    dataframe = pd.DataFrame(
        [
            {
                "title": f"Product {index}",
                "url": f"https://example.com/{index}",
                "selector": None,
            }
            for index in range(MAX_PRODUCTS + 1)
        ]
    )
    dataframe.to_excel(file_path, index=False)

    with pytest.raises(ValueError, match="Too many product rows"):
        load_products(file_path)
