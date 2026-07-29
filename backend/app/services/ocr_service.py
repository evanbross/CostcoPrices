# ai: claude-sonnet-4-6 | 2026-06-19
import base64
import json
import logging
import re

import anthropic

from app.config import settings
from app.database.schemas import OcrResponse, ParsedLine

logger = logging.getLogger(__name__)

# ai: claude-sonnet-5 | 2026-07-20 (added Quantity-multiplier lines section below)
_SYSTEM_PROMPT = """\
You are a Costco receipt parser. Extract the receipt header info and every line item.

Regular line format:
  [optional single letter] <item_code> <description> <price> <tax_char>

Rules:
- item_code: typically 5-7 digit number
- tax_char: '3' = grocery/food, 'Y' = prepared food, 'A' = non-food (may be absent)
- Some items are priced by weight (meats, fish) — include the total price
- Ignore subtotals, taxes, totals, membership info
- Ignore page headers and footers: repeated store banners, page numbers, timestamps, \
"Member Since", "Member #", and any decorative separators that are not line items
- line_prefix: the optional single letter before the item code (if present), else null

Quantity-multiplier lines:
  Some items are preceded by their own line in the form "<qty> @ <unit_price>", e.g.:
    4 @ 14.99
    106173  CHKN SAUSAGE      59.96  E
  This means 4 units were bought at $14.99 each, and the item line's printed price (59.96) is the
  extended total (qty × unit_price), not the per-unit price. When you see this pattern:
  - Do NOT emit "<qty> @ <unit_price>" as its own line item — it is not a separate purchase.
  - For the item line that follows it, set `price` to the unit price after "@" (14.99 above),
    never the extended total printed on the item's own line (59.96 above).

Coupon lines:
  A coupon line has its OWN item code followed by a description that starts with a forward slash \
and the item code of the item being discounted, e.g.:
    376153  /1456653  3.20-
  Here 376153 is the coupon's item code and /1456653 means it discounts item 1456653.
  The price has a trailing minus sign (3.20- means -3.20).
  For coupon lines set:
  - item_code: the coupon's own code (e.g. "376153")
  - description: "Instant Savings" (or any text that appears after the referenced code, if present)
  - price: the negative value as a plain decimal (e.g. "-3.20")
  - is_coupon: true
  - coupon_for_code: the item code referenced after the slash (e.g. "1456653")

Also extract from the header/footer:
- barcode: the numeric barcode number printed under the barcode (typically at the bottom of the receipt, 10-15 digits)
- detected_date: the purchase date in YYYY-MM-DD format
- detected_store: the store name or location string (e.g. "Costco Warehouse #1234" or city/state)

If the receipt spans multiple images/pages, combine all line items into a single list and \
extract barcode/date/store from whichever page contains them.

Return JSON only — no markdown, no prose:
{
  "barcode": "1234567890123",
  "detected_date": "2026-01-15",
  "detected_store": "Costco Wholesale #123 Anytown, MA",
  "lines": [
    {
      "item_code": "123456",
      "description": "ITEM DESCRIPTION",
      "price": "9.99",
      "tax_type": "3",
      "is_coupon": false,
      "coupon_for_code": null,
      "line_prefix": null
    }
  ],
  "raw_text": "optional verbatim text from the image"
}
"""

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


async def parse_receipt_images(images: list[tuple[bytes, str]]) -> OcrResponse:
    """Call Claude vision with one or more receipt images (e.g. pages of a PDF).

    Each element of `images` is (raw_bytes, media_type). All pages are sent in a
    single API call so Claude has full context across page boundaries.
    """
    client = _get_client()

    content: list[dict] = []
    for page_bytes, media_type in images:
        b64 = base64.standard_b64encode(page_bytes).decode("utf-8")
        content.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64},
            }
        )

    page_word = "page" if len(images) == 1 else f"{len(images)} pages"
    content.append(
        {
            "type": "text",
            "text": f"Extract the barcode, date, store, and all line items from this Costco receipt ({page_word}).",
        }
    )

    logger.info(
        "Sending %d image(s) to Claude OCR (total %d bytes)",
        len(images),
        sum(len(b) for b, _ in images),
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    raw_response = message.content[0].text
    logger.debug("OCR raw response: %s", raw_response[:500])

    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
        else:
            logger.error("OCR response is not valid JSON: %s", raw_response[:300])
            raise ValueError(f"OCR returned non-JSON response: {raw_response[:200]}")

    lines = [ParsedLine(**line) for line in data.get("lines", [])]
    logger.info("OCR extracted %d line items, barcode=%s", len(lines), data.get("barcode"))

    return OcrResponse(
        lines=lines,
        raw_text=data.get("raw_text"),
        barcode=data.get("barcode") or None,
        detected_date=data.get("detected_date") or None,
        detected_store=data.get("detected_store") or None,
    )


async def parse_receipt_image(image_bytes: bytes, media_type: str = "image/jpeg") -> OcrResponse:
    """Convenience wrapper for a single receipt image."""
    return await parse_receipt_images([(image_bytes, media_type)])
