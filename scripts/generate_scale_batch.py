import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
"""Deterministic Synthetic Invoice Generator for LedgerGuard Phase 9 Scale Testing.

Generates structured test datasets and real PDF documents across enterprise volume tiers:
5, 50, 100, 500, 1,000, 10,000, and 50,000 documents.

Enforces:
1. Strict Decimal financial arithmetic with ROUND_HALF_UP (no float accumulation).
2. Enterprise distribution:
   - 80% Clean valid invoices (within policy -> AUTO_APPROVED)
   - 10% High-value or new vendor invoices (-> MANUAL_REVIEW)
   - 5% Duplicate invoices (-> DUPLICATE detection)
   - 3% Arithmetic mismatch invoices (-> MANUAL_REVIEW)
   - 2% Corrupt / incomplete documents (-> FAILED / EXTRACTION_FAILED)
3. Safe execution, reproducible seeding, and lightweight footprint.
"""

import argparse
from decimal import Decimal, ROUND_HALF_UP
import json
import os
import random
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

KNOWN_VENDORS = [
    ("vend_01", "Acme Corp"),
    ("vend_02", "Apex Solutions"),
    ("vend_03", "Nova Advisory Partners"),
    ("vend_04", "Global Logistics Inc"),
    ("vend_05", "SuperStore"),
]

NEW_VENDORS = [
    ("vend_new_01", "Quantum Edge Dynamics"),
    ("vend_new_02", "Vanguard Cybernetics"),
    ("vend_new_03", "Aether Industrial Works"),
]


def quantize_money(amount: Decimal) -> Decimal:
    """Format decimal amount strictly to 2 decimal places using standard rounding."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def generate_invoice_data(index: int, total_count: int = 100, seed: int = 42) -> dict[str, Any]:
    """Generate deterministic invoice metadata based on index and distribution."""
    rng = random.Random(seed + index)
    bucket = int((index / max(1, total_count)) * 100)

    # 1. Determine scenario type based on percentage distribution
    if bucket < 80:
        # 80% Clean valid within policy
        scenario = "CLEAN_VALID"
        vendor_id, vendor_name = rng.choice(KNOWN_VENDORS)
        qty1 = rng.randint(1, 5)
        rate1 = Decimal(f"{rng.randint(20, 80)}.50")
        qty2 = rng.randint(1, 4)
        rate2 = Decimal(f"{rng.randint(30, 90)}.00")
        line_items = [
            {"description": "Standard Hardware Supplies", "quantity": qty1, "unit_price": rate1, "amount": quantize_money(Decimal(qty1) * rate1)},
            {"description": "Technical Maintenance Service", "quantity": qty2, "unit_price": rate2, "amount": quantize_money(Decimal(qty2) * rate2)},
        ]
        subtotal = quantize_money(sum(item["amount"] for item in line_items))
        tax = quantize_money(subtotal * Decimal("0.08"))
        shipping = Decimal("15.00")
        discount = Decimal("0.00")
        total = quantize_money(subtotal + tax + shipping - discount)
        invoice_num = f"INV-SCALE-{index + 10000:06d}"

    elif bucket < 90:
        # 10% High-value / new vendor -> MANUAL_REVIEW
        scenario = "HIGH_VALUE_OR_NEW_VENDOR"
        if rng.random() < 0.5:
            vendor_id, vendor_name = rng.choice(KNOWN_VENDORS)
            qty1 = rng.randint(20, 50)
            rate1 = Decimal(f"{rng.randint(150, 300)}.00")
            line_items = [
                {"description": "Enterprise Infrastructure Server", "quantity": qty1, "unit_price": rate1, "amount": quantize_money(Decimal(qty1) * rate1)}
            ]
            subtotal = quantize_money(sum(item["amount"] for item in line_items))
            tax = quantize_money(subtotal * Decimal("0.08"))
            shipping = Decimal("150.00")
            discount = Decimal("100.00")
            total = quantize_money(subtotal + tax + shipping - discount)  # > $5,000 threshold
        else:
            vendor_id, vendor_name = rng.choice(NEW_VENDORS)
            qty1 = rng.randint(2, 6)
            rate1 = Decimal("120.00")
            line_items = [
                {"description": "Prototype Consultation", "quantity": qty1, "unit_price": rate1, "amount": quantize_money(Decimal(qty1) * rate1)}
            ]
            subtotal = quantize_money(sum(item["amount"] for item in line_items))
            tax = quantize_money(subtotal * Decimal("0.08"))
            shipping = Decimal("0.00")
            discount = Decimal("0.00")
            total = quantize_money(subtotal + tax + shipping - discount)
        invoice_num = f"INV-SCALE-{index + 10000:06d}"

    elif bucket < 95:
        # 5% Duplicate invoices
        scenario = "DUPLICATE"
        vendor_id, vendor_name = KNOWN_VENDORS[0]
        # Re-use an earlier invoice number to force duplicate detection
        duplicate_source_idx = (index // 20) * 20
        invoice_num = f"INV-SCALE-{duplicate_source_idx + 10000:06d}"
        line_items = [
            {"description": "Duplicate Office Supplies", "quantity": 2, "unit_price": Decimal("100.00"), "amount": Decimal("200.00")}
        ]
        subtotal = Decimal("200.00")
        tax = Decimal("16.00")
        shipping = Decimal("10.00")
        discount = Decimal("0.00")
        total = Decimal("226.00")

    elif bucket < 98:
        # 3% Arithmetic mismatch -> MANUAL_REVIEW
        scenario = "ARITHMETIC_MISMATCH"
        vendor_id, vendor_name = rng.choice(KNOWN_VENDORS)
        line_items = [
            {"description": "Logistics Dispatch Fee", "quantity": 1, "unit_price": Decimal("500.00"), "amount": Decimal("500.00")}
        ]
        subtotal = Decimal("500.00")
        tax = Decimal("40.00")
        shipping = Decimal("25.00")
        discount = Decimal("0.00")
        # Purposely mismatch total by +$50.00
        total = Decimal("615.00")
        invoice_num = f"INV-SCALE-{index + 10000:06d}"

    else:
        # 2% Corrupt / incomplete
        scenario = "CORRUPT_OR_INCOMPLETE"
        vendor_id, vendor_name = "vend_unknown", "Unknown Partner"
        line_items = []
        subtotal = Decimal("0.00")
        tax = None
        shipping = Decimal("0.00")
        discount = Decimal("0.00")
        total = Decimal("0.00")
        invoice_num = f"INV-CORRUPT-{index + 10000:06d}"

    return {
        "index": index,
        "scenario": scenario,
        "invoice_number": invoice_num,
        "vendor_id": vendor_id,
        "vendor_name": vendor_name,
        "invoice_date": "2026-09-01",
        "currency": "USD",
        "line_items": line_items,
        "subtotal": str(subtotal),
        "tax": str(tax) if tax is not None else None,
        "shipping": str(shipping),
        "discount": str(discount),
        "total": str(total),
    }


def render_invoice_pdf(data: dict[str, Any], filepath: str) -> None:
    """Render a clean, standard PDF invoice using ReportLab."""
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, data["vendor_name"])
    c.setFont("Helvetica", 9)
    c.drawString(50, height - 65, "Enterprise AP Settlement Center")
    c.drawString(50, height - 78, "ap-support@ledgerguard-verified.com")

    # Invoice Details Box
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(width - 50, height - 50, "INVOICE")
    c.setFont("Helvetica", 10)
    c.drawRightString(width - 50, height - 68, f"Invoice #: {data['invoice_number']}")
    c.drawRightString(width - 50, height - 82, f"Date: {data['invoice_date']}")
    c.drawRightString(width - 50, height - 96, f"Currency: {data['currency']}")

    # Table Header
    y = height - 130
    c.setLineWidth(1)
    c.line(50, y, width - 50, y)
    y -= 15
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, y, "Description")
    c.drawString(320, y, "Qty")
    c.drawString(380, y, "Rate")
    c.drawRightString(width - 50, y, "Amount")
    y -= 8
    c.line(50, y, width - 50, y)

    # Line items
    c.setFont("Helvetica", 9)
    for item in data.get("line_items", []):
        y -= 16
        c.drawString(50, y, str(item["description"])[:40])
        c.drawString(320, y, str(item["quantity"]))
        c.drawString(380, y, f"${item['unit_price']}")
        c.drawRightString(width - 50, y, f"${item['amount']}")

    # Financial Summary
    y -= 25
    c.line(320, y, width - 50, y)
    y -= 15
    c.drawString(320, y, "Subtotal:")
    c.drawRightString(width - 50, y, f"${data['subtotal']}")

    if data.get("tax"):
        y -= 14
        c.drawString(320, y, "Tax:")
        c.drawRightString(width - 50, y, f"${data['tax']}")

    if Decimal(data.get("shipping", "0.00")) > 0:
        y -= 14
        c.drawString(320, y, "Shipping:")
        c.drawRightString(width - 50, y, f"${data['shipping']}")

    if Decimal(data.get("discount", "0.00")) > 0:
        y -= 14
        c.drawString(320, y, "Discount:")
        c.drawRightString(width - 50, y, f"-${data['discount']}")

    y -= 16
    c.line(320, y, width - 50, y)
    y -= 15
    c.setFont("Helvetica-Bold", 11)
    c.drawString(320, y, "Total:")
    c.drawRightString(width - 50, y, f"${data['total']}")

    c.save()


def generate_batch(count: int, output_dir: str, generate_pdfs: bool = False) -> dict[str, Any]:
    """Generate a synthetic invoice batch dataset and optional PDF files."""
    os.makedirs(output_dir, exist_ok=True)
    manifest = []
    scenarios_count = {}

    total_value = Decimal("0.00")
    total_tax = Decimal("0.00")
    total_subtotal = Decimal("0.00")

    for i in range(count):
        inv_data = generate_invoice_data(i, total_count=count)
        scenario = inv_data["scenario"]
        scenarios_count[scenario] = scenarios_count.get(scenario, 0) + 1

        total_value += Decimal(inv_data["total"])
        total_subtotal += Decimal(inv_data["subtotal"])
        if inv_data["tax"]:
            total_tax += Decimal(inv_data["tax"])

        pdf_filename = f"{inv_data['invoice_number']}.pdf"
        inv_data["filename"] = pdf_filename
        manifest.append(inv_data)

        if generate_pdfs:
            pdf_path = os.path.join(output_dir, pdf_filename)
            if scenario == "CORRUPT_OR_INCOMPLETE" and i % 2 == 0:
                # Corrupt PDF bytes
                with open(pdf_path, "wb") as f:
                    f.write(b"%PDF-CORRUPTED-CORRUPT-BYTES-HEADER\x00\x11\x22")
            else:
                render_invoice_pdf(inv_data, pdf_path)

    summary = {
        "count": count,
        "scenarios": scenarios_count,
        "total_value": str(quantize_money(total_value)),
        "total_subtotal": str(quantize_money(total_subtotal)),
        "total_tax": str(quantize_money(total_tax)),
    }

    manifest_path = os.path.join(output_dir, "batch_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "invoices": manifest}, f, indent=2, default=str)

    return summary


def main():
    parser = argparse.ArgumentParser(description="Deterministic Scale Invoice Generator for LedgerGuard")
    parser.add_argument("--count", type=int, default=50, help="Number of invoices to generate (5, 50, 100, 500, 1000, 10000, 50000)")
    parser.add_argument("--output-dir", type=str, default="tests/fixtures/scale_batches", help="Target output directory")
    parser.add_argument("--generate-pdfs", action="store_true", help="Whether to render physical PDF files")
    args = parser.parse_args()

    summary = generate_batch(args.count, args.output_dir, generate_pdfs=args.generate_pdfs)
    print(f"Successfully generated batch of {args.count} invoices in {args.output_dir}:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
