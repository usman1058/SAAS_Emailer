"""
Export Service

Handles exporting leads to CSV, Excel, and HTML formats.
"""
import csv
import logging
import os
from typing import List

from openpyxl import Workbook
from openpyxl.styles import Font

from leads.models import Lead, SearchJob

logger = logging.getLogger(__name__)

FIELDNAMES = [
    "name", "category", "address", "phone", "website", "has_website",
    "whatsapp_status", "whatsapp_check_link", "osm_url",
]


def write_csv(path: str, leads: List[Lead]) -> int:
    """Write leads to CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for lead in leads:
            writer.writerow(_lead_to_dict(lead))
    return os.path.getsize(path)


def write_excel(path: str, leads: List[Lead]) -> int:
    """Write leads to Excel file with multiple sheets."""
    wb = Workbook()
    header_font = Font(bold=True)

    def add_sheet(ws, rows, title):
        ws.title = title
        ws.append(FIELDNAMES)
        for cell in ws[1]:
            cell.font = header_font
        for row in rows:
            ws.append([row.get(f, "") for f in FIELDNAMES])
        for col_cells in ws.columns:
            length = max(
                (len(str(c.value)) for c in col_cells if c.value), default=10
            )
            ws.column_dimensions[col_cells[0].column_letter].width = min(
                max(length + 2, 12), 45
            )

    no_website = [lead for lead in leads if not lead.has_website]
    with_website = [lead for lead in leads if lead.has_website]
    priority = [lead for lead in no_website if lead.is_priority]

    add_sheet(wb.active, [_lead_to_dict(lead) for lead in leads], "All")
    add_sheet(wb.create_sheet(), [_lead_to_dict(lead) for lead in no_website], "No Website")
    add_sheet(wb.create_sheet(), [_lead_to_dict(lead) for lead in priority], "Priority Leads")
    add_sheet(wb.create_sheet(), [_lead_to_dict(lead) for lead in with_website], "Has Website")

    wb.save(path)
    return os.path.getsize(path)


def write_html_report(path: str, leads: List[Lead], title: str) -> int:
    """Write interactive HTML report."""
    rows_html = []
    for lead in leads:
        website_cell = (
            f'<a href="{lead.website}" target="_blank">{lead.website}</a>'
            if lead.website else "—"
        )
        wa_cell = (
            f'<a href="{lead.whatsapp_check_link}" target="_blank">check</a>'
            if lead.whatsapp_check_link else ""
        )
        wa_class = 'mobile' if lead.whatsapp_status.startswith('Mobile') else 'other'
        rows_html.append(f"""
        <tr data-has-website="{'Yes' if lead.has_website else 'No'}" data-wa="{wa_class}">
          <td>{lead.name}</td><td>{lead.category}</td><td>{lead.address}</td>
          <td>{lead.phone}</td><td>{website_cell}</td>
          <td>{lead.whatsapp_status} {wa_cell}</td>
          <td><a href="{lead.osm_url}" target="_blank">OSM</a></td>
        </tr>""")

    total = len(leads)
    no_site = sum(1 for lead in leads if not lead.has_website)
    has_site = total - no_site
    mobile_count = sum(1 for lead in leads if lead.whatsapp_status.startswith("Mobile"))

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>{title}</title>
<style>
body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; background: #fafafa; }}
h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
.stats {{ color: #555; margin-bottom: 16px; }}
.filters button {{ padding: 8px 16px; margin: 0 6px 6px 0; border-radius: 20px; border: 1px solid #ccc; background: white; cursor: pointer; }}
.filters button.active {{ background: #1a1a1a; color: white; border-color: #1a1a1a; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 16px; background: white; }}
th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #eee; font-size: 0.86rem; }}
th {{ background: #f0f0f0; }}
tr[data-has-website="No"] {{ background: #fff6f6; }}
</style></head><body>
<h1>{title}</h1>
<div class="stats">{total} businesses &nbsp;|&nbsp; {no_site} without a website &nbsp;|&nbsp; {has_site} with a website &nbsp;|&nbsp; {mobile_count} with a mobile number</div>
<div class="filters">
  <button class="active" onclick="filterRows('All', this)">All ({total})</button>
  <button onclick="filterRows('site-no', this)">No Website</button>
  <button onclick="filterRows('site-yes', this)">Has Website</button>
  <button onclick="filterRows('mobile', this)">Mobile Number Only</button>
</div>
<table><thead><tr><th>Name</th><th>Category</th><th>Address</th><th>Phone</th><th>Website</th><th>WhatsApp likelihood</th><th>OSM</th></tr></thead>
<tbody id="rows">{''.join(rows_html)}</tbody></table>
<script>
function filterRows(mode, btn) {{
  document.querySelectorAll('.filters button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#rows tr').forEach(row => {{
    let show = true;
    if (mode === 'site-no') show = row.getAttribute('data-has-website') === 'No';
    else if (mode === 'site-yes') show = row.getAttribute('data-has-website') === 'Yes';
    else if (mode === 'mobile') show = row.getAttribute('data-wa') === 'mobile';
    row.style.display = show ? '' : 'none';
  }});
}}
</script></body></html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return os.path.getsize(path)


def _lead_to_dict(lead: Lead) -> dict:
    """Convert Lead model to dictionary for export."""
    return {
        "name": lead.name,
        "category": lead.category,
        "address": lead.address,
        "phone": lead.phone,
        "website": lead.website,
        "has_website": "Yes" if lead.has_website else "No",
        "whatsapp_status": lead.whatsapp_status,
        "whatsapp_check_link": lead.whatsapp_check_link,
        "osm_url": lead.osm_url,
    }


def export_job_results(job: SearchJob, output_dir: str, base_name: str) -> dict:
    """
    Export all results for a search job.

    Returns:
        dict with file paths and sizes for each format
    """
    leads = list(job.leads.all())

    results = {}

    # CSV exports
    csv_all = os.path.join(output_dir, f"{base_name}_all.csv")
    csv_no_site = os.path.join(output_dir, f"{base_name}_no_website.csv")
    csv_priority = os.path.join(output_dir, f"{base_name}_priority.csv")

    results['csv_all'] = write_csv(csv_all, leads)
    results['csv_no_website'] = write_csv(csv_no_site, [lead for lead in leads if not lead.has_website])
    results['csv_priority'] = write_csv(csv_priority, [lead for lead in leads if lead.is_priority])

    # Excel export
    xlsx_path = os.path.join(output_dir, f"{base_name}.xlsx")
    results['xlsx'] = write_excel(xlsx_path, leads)

    # HTML report
    html_path = os.path.join(output_dir, f"{base_name}_report.html")
    results['html'] = write_html_report(html_path, leads, f"Website gap report — {job.city}")

    return results