"""Test JSON-LD and Microdata price extraction from HTML."""

from decimal import Decimal

import pytest

from app.scraping.extractors import extract_json_ld_price, extract_microdata_price


@pytest.mark.parametrize(
    ("html", "expected_price", "expected_currency"),
    [
        (
            '''
            <script type="application/ld+json">
            {
                "@type": "Product",
                "name": "Test Product",
                "offers": {
                    "@type": "Offer",
                    "price": "24990.00",
                    "priceCurrency": "RUB"
                }
            }
            </script>
            ''',
            Decimal("24990.00"),
            "RUB",
        ),
        (
            '''
            <script type="application/ld+json">
            {
                "@graph": [
                    {"@type": "Organization", "name": "Example Store"},
                    {
                        "@type": ["Thing", "Product"],
                        "offers": [
                            {
                                "@type": "Offer",
                                "price": "965,33",
                                "priceCurrency": "RUB"
                            }
                        ]
                    }
                ]
            }
            </script>
            ''',
            Decimal("965.33"),
            "RUB",
        ),
        (
            '''
            <script type="application/ld+json">
            {
                "@type": "Product",
                "offers": {
                    "@type": "AggregateOffer",
                    "lowPrice": "860",
                    "priceCurrency": "RUB"
                }
            }
            </script>
            ''',
            Decimal("860"),
            "RUB",
        ),
    ],
)
def test_extract_json_ld_price(
    html: str,
    expected_price: Decimal,
    expected_currency: str,
) -> None:
    assert extract_json_ld_price(html) == (
        expected_price,
        expected_currency,
    )


def test_extract_json_ld_skips_invalid_json() -> None:
    html = '''
    <script type="application/ld+json">
    {invalid json}
    </script>

    <script type="application/ld+json">
    {
        "@type": "Product",
        "offers": {
            "price": "1200",
            "priceCurrency": "RUB"
        }
    }
    </script>
    '''

    assert extract_json_ld_price(html) == (Decimal("1200"), "RUB")


def test_extract_json_ld_without_product() -> None:
    html = '''
    <script type="application/ld+json">
    {
        "@type": "Organization",
        "name": "Example Store"
    }
    </script>
    '''

    assert extract_json_ld_price(html) == (None, None)


def test_extract_json_ld_with_invalid_price() -> None:
    html = '''
    <script type="application/ld+json">
    {
        "@type": "Product",
        "offers": {
            "price": "Not available",
            "priceCurrency": "RUB"
        }
    }
    </script>
    '''

    assert extract_json_ld_price(html) == (None, None)


def test_extract_microdata_from_content() -> None:
    html = '''
    <div>
        <meta itemprop="price" content="32840">
        <meta itemprop="priceCurrency" content="RUB">
    </div>
    '''

    assert extract_microdata_price(html) == (Decimal("32840"), "RUB")


def test_extract_microdata_from_text() -> None:
    html = '''
    <div>
        <span itemprop="price">34 599 ₽</span>
        <span itemprop="priceCurrency">RUB</span>
    </div>
    '''

    assert extract_microdata_price(html) == (Decimal("34599"), "RUB")


def test_extract_microdata_without_currency() -> None:
    html = '''
    <span itemprop="price" content="1020"></span>
    '''

    assert extract_microdata_price(html) == (Decimal("1020"), None)


def test_extract_microdata_without_price() -> None:
    html = '''
    <meta itemprop="priceCurrency" content="RUB">
    '''

    assert extract_microdata_price(html) == (None, None)


def test_extract_microdata_with_invalid_price() -> None:
    html = '''
    <meta itemprop="price" content="Price unavailable">
    <meta itemprop="priceCurrency" content="RUB">
    '''

    assert extract_microdata_price(html) == (None, None)
