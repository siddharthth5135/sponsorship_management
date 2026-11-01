"""Build Blithchron Excel + load brands/outreach into DB."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.database import get_conn, init_db
from app.services.emails import blithchron_brand_email, sender_profile
from app.services.messaging import enrich_channels, pitch_text
from scripts.blithchron_leads_master import LEADS
from scripts.blithchron_local_leads import LOCAL_LEADS

OUT_XLSX = ROOT / "exports" / "Blithchron27_Leads_100plus_Scripts.xlsx"
SEGMENT = "blithchron27"
SEGMENT_LOCAL = "blithchron27_local"


CONVINCE = [
    ("Exclusivity", "Sell Official Energy / Beverage / Hydration / Banking Partner — one brand only on ground. That lock is why they pay more than a logo."),
    ("Proof from THEIR brochure", "CBI Title '25, Krispy Hydration, Coke/Monster/Maggi/Souled Store logos — say 'brands like these already associated'."),
    ("Hard numbers", "22,000 footfall · 6,000+/Pronite night · 100+ partner colleges · 150k+ digital · 4–7 Feb 2027 IITGN."),
    ("Right package not Title for everyone", "Start Gold/Event/Energy Partner. Drop to stall if they flinch. Never oversell Associate as everywhere branding."),
    ("Cash + product hybrid", "FMCG/energy love stock. Banks pay cash. Offer 40–60% cash + rest MRP stock."),
    ("Urgency", "Category exclusivity is first-come. Creatives need logos 3–4 weeks out. Soft yes + MoU this week."),
    ("Local path beats HQ", "For QSR/auto/telecom: store GM / circle / dealer first — they say yes this week."),
    ("Your authority", "Before brand calls: WhatsApp Aarav/Jay/Parishi that you may sell packages. Brands ghost unauthorized brokers."),
    ("CSR for banks/Amul", "Brochure 'paying back to society' — education, cleanliness, blood donation."),
    ("Never", "Fake dealership WhatsApps · invented personal Gmails · two energy brands same week · course-sellers if blocked · collect money in personal account."),
]


def build_excel() -> Path:
    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()

    # —— Leads ——
    ws = wb.active
    ws.title = "Leads"
    headers = [
        "#", "Priority", "Brand", "Category", "City", "Package to sell", "Ask ₹",
        "Contact name", "Role", "Email", "Phone", "Website / LinkedIn",
        "Confidence", "Pitch", "How to convince (short)", "Call opener (say this)",
    ]
    head_fill = PatternFill("solid", fgColor="0F172A")
    head_font = Font(color="FFFFFF", bold=True, size=10)
    for col, h in enumerate(headers, 1):
        cell = ws.cell(1, col, h)
        cell.fill = head_fill
        cell.font = head_font
    for i, L in enumerate(sorted(LEADS, key=lambda x: (x["priority"], x["name"])), 1):
        route = L.get("website") or ""
        if L.get("linkedin_hint"):
            route = (route + " | " if route else "") + L["linkedin_hint"]
        row = [
            i, L["priority"], L["name"], L["category"], L["city"], L["package"], L["ask_inr"],
            L.get("contact_name") or "", L.get("contact_role") or "", L.get("email") or "",
            L.get("phone") or "", route, L["confidence"], L["pitch"], L["convince"], L["call_opener"],
        ]
        for col, val in enumerate(row, 1):
            c = ws.cell(i + 1, col, val)
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    widths = [5, 8, 28, 14, 12, 22, 16, 22, 16, 32, 28, 36, 12, 36, 36, 40]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i) if i <= 26 else "A"].width = w
    # fix columns beyond Z
    from openpyxl.utils import get_column_letter
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # —— How to convince ——
    w2 = wb.create_sheet("How_to_Convince")
    w2["A1"] = "How to convince Blithchron sponsors (bullet playbook)"
    w2["A1"].font = Font(bold=True, size=14)
    w2["A2"] = "Use with Leads sheet + Call_Scripts. Confirm ₹ with Aarav/Jay/Parishi before emailing numbers."
    w2.merge_cells("A3:B3")
    w2["A4"] = "#"
    w2["B4"] = "Point"
    w2["C4"] = "What to say / do"
    for cell in (w2["A4"], w2["B4"], w2["C4"]):
        cell.fill = head_fill
        cell.font = head_font
    for i, (title, body) in enumerate(CONVINCE, 1):
        w2.cell(i + 4, 1, i)
        w2.cell(i + 4, 2, title).font = Font(bold=True)
        w2.cell(i + 4, 3, body).alignment = Alignment(wrap_text=True)
    w2.column_dimensions["A"].width = 5
    w2.column_dimensions["B"].width = 22
    w2.column_dimensions["C"].width = 90

    # —— Universal call script ——
    w3 = wb.create_sheet("Call_Scripts")
    w3["A1"] = "Phone call scripts — Blithchron '27"
    w3["A1"].font = Font(bold=True, size=14)
    scripts = [
        ("1. Opening (any brand)",
         "Hi, I'm [Name], working with Blithchron '27 — IIT Gandhinagar's annual cultural fest, 4 to 7 February 2027. "
         "About 22,000 footfall, two Pronites with 6,000-plus a night, and 100-plus partner colleges across Gujarat. "
         "Past associates include Central Bank of India, Coca-Cola, Monster, Maggi and The Souled Store. "
         "We're closing the [PACKAGE] slot this fortnight with category exclusivity. Do you have two minutes?"),
        ("2. After they say yes / tell me more",
         "Great. The package is [PACKAGE] at roughly [ASK] — flexible, confirmed with the fest team. "
         "You get [2–3 deliverables: stall / LED / MC shout / sampling / exclusive category]. "
         "I'll email a one-pager today. Who signs off on campus spends — you or someone else?"),
        ("3. If 'send an email'",
         "Absolutely — within the hour. Quick question so I don't waste your time: "
         "are you looking more for sampling plus stall, stage or Pronite branding, or Title-level naming? "
         "And is campus in this quarter's budget?"),
        ("4. If 'too expensive'",
         "Understood — Title isn't mandatory. We can do Event Sponsor for Flavor Fest or Panache at a lower band, "
         "or a sampling stall with social posts, still with category protection in your zone. "
         "What budget line are you working with for campus this quarter?"),
        ("5. If 'only product / contra'",
         "We can do a hybrid — part cash, part stock at MRP. Cash covers banners and LED; stock covers sampling. "
         "Blithchron still needs a cash floor for Pronite costs. What's the maximum cash you can approve this week?"),
        ("6. If they stall",
         "Fair — two things: category exclusivity is first-come, and Pronite creatives need logo files about three to four weeks out. "
         "Can we hold the slot with a soft yes and MoU draft by Friday, fifty percent on signing?"),
        ("7. Close / ask",
         "Perfect — I'll send the MoU tonight with package name, amount, exclusivity clause, deliverables, stall size and logo deadline. "
         "Who signs on your side, and can we do a ten-minute call with the fest sponsorship executive so you hear it from organizers too?"),
        ("8. Exclusivity clause (read into MoU)",
         "Sponsor shall be the sole brand in the [Energy Drink / Packaged Water / Sparkling Beverage / Banking] category "
         "on Blithchron '27 premises and in official creatives for that category during 4–7 February 2027."),
        ("9. Fest team numbers (get authority first)",
         "Aarav Malde 9326144314 · Jay Hire 9137727484 · Parishi Shah 9653651177 · blithchron@iitgn.ac.in"),
        ("10. Per-brand openers",
         "See column 'Call opener' on the Leads sheet — use that as sentence two after the universal opening."),
    ]
    w3["A3"] = "Step"
    w3["B3"] = "Exact words"
    w3["A3"].fill = head_fill
    w3["A3"].font = head_font
    w3["B3"].fill = head_fill
    w3["B3"].font = head_font
    for i, (title, body) in enumerate(scripts, 1):
        w3.cell(i + 3, 1, title).font = Font(bold=True)
        w3.cell(i + 3, 2, body).alignment = Alignment(wrap_text=True, vertical="top")
        w3.row_dimensions[i + 3].height = 55
    w3.column_dimensions["A"].width = 36
    w3.column_dimensions["B"].width = 100

    # —— Emailable only ——
    w4 = wb.create_sheet("Emailable_Now")
    w4.append(["Brand", "Email", "Phone", "Package", "Ask", "Call opener"])
    for cell in w4[1]:
        cell.fill = head_fill
        cell.font = head_font
    for L in sorted(LEADS, key=lambda x: x["priority"]):
        if (L.get("email") or "").strip():
            w4.append([L["name"], L["email"], L.get("phone") or "", L["package"], L["ask_inr"], L["call_opener"]])
    for col in range(1, 7):
        w4.column_dimensions[get_column_letter(col)].width = 28

    # —— One-click WhatsApp / LinkedIn for non-email national leads ——
    w5 = wb.create_sheet("Message_NoEmail")
    w5.append(["Brand", "Phone", "WhatsApp click", "LinkedIn people search", "Pitch message (paste)"])
    for cell in w5[1]:
        cell.fill = head_fill
        cell.font = head_font
    for L in LEADS:
        if (L.get("email") or "").strip():
            continue
        ch = enrich_channels({**L, "contact_phone": L.get("phone") or ""})
        w5.append([L["name"], L.get("phone") or "", ch.get("wa_url") or "(no mobile — use LinkedIn)", ch["linkedin_people"], ch["pitch"]])
    for col in range(1, 6):
        w5.column_dimensions[get_column_letter(col)].width = 40

    # —— Local AMD/GN ——
    w6 = wb.create_sheet("Local_AMD_GN")
    w6.append(["#", "Brand", "City", "Category", "Package", "Ask", "Phone", "Email", "WhatsApp", "Pitch"])
    for cell in w6[1]:
        cell.fill = head_fill
        cell.font = head_font
    for i, L in enumerate(LOCAL_LEADS, 1):
        ch = enrich_channels({**L, "contact_phone": L.get("phone") or "", "contact_email": L.get("email") or ""})
        w6.append([
            i, L["name"], L["city"], L["category"], L["package"], L["ask_inr"],
            L.get("phone") or "", L.get("email") or "", ch.get("wa_url") or "", ch["pitch"],
        ])
    for col in range(1, 11):
        w6.column_dimensions[get_column_letter(col)].width = 22

    wb.save(OUT_XLSX)
    return OUT_XLSX


def _upsert_brand(conn, L: dict, segment: str, event_id: int, sender: dict, agent: str) -> tuple[str, bool]:
    """Returns ('inserted'|'updated', draft_created)."""
    email = (L.get("email") or "").strip()
    notes = (
        f"Blithchron'27 | {L['package']} | ask {L['ask_inr']} | "
        f"confidence={L['confidence']} | {L['pitch']}"
    )
    existing = conn.execute(
        "SELECT id FROM brands WHERE name=? AND segment=?",
        (L["name"], segment),
    ).fetchone()
    if existing:
        brand_id = existing["id"]
        conn.execute(
            """
            UPDATE brands SET city=?, category=?, contact_name=?, contact_email=?, contact_phone=?,
                contact_role=?, website=?, linkedin_url=?, notes=?, description=?,
                conversion_tier=?, intent_signal=?, status='prospect',
                target_categories=?, discovery_reason=?, updated_at=datetime('now')
            WHERE id=?
            """,
            (
                L["city"], L["category"], L.get("contact_name") or "", email,
                L.get("phone") or "", L.get("contact_role") or "",
                L.get("website") or "", L.get("linkedin_hint") or "",
                notes, L.get("convince") or "",
                "high" if L.get("priority", 3) <= 2 else "possible",
                "active" if L.get("confidence") in ("renew", "public_inbox", "named_public", "local_public") else "latent",
                "College cultural fest",
                "blithchron_pack",
                brand_id,
            ),
        )
        action = "updated"
    else:
        cur = conn.execute(
            """
            INSERT INTO brands (name, city, category, goal, contact_name, contact_email, contact_phone,
                contact_role, website, linkedin_url, notes, description, status, segment,
                conversion_tier, intent_signal, target_categories, discovery_reason, budget_min, budget_max)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                L["name"], L["city"], L["category"], "awareness",
                L.get("contact_name") or "", email, L.get("phone") or "",
                L.get("contact_role") or "", L.get("website") or "", L.get("linkedin_hint") or "",
                notes, L.get("convince") or "", "prospect", segment,
                "high" if L.get("priority", 3) <= 2 else "possible",
                "active" if L.get("confidence") in ("renew", "public_inbox", "named_public", "local_public") else "latent",
                "College cultural fest", "blithchron_pack", 0, 0,
            ),
        )
        brand_id = cur.lastrowid
        action = "inserted"

    conn.execute(
        """
        INSERT INTO matches (event_id, brand_id, fit_score, fit_tier, status, match_reason)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(event_id, brand_id) DO UPDATE SET
            fit_score=excluded.fit_score, match_reason=excluded.match_reason, updated_at=datetime('now')
        """,
        (
            event_id, brand_id, max(50, 100 - int(L.get("priority", 3)) * 8),
            "strong" if L.get("priority", 3) <= 2 else "partial",
            "suggested", f"Blithchron pack: {L['package']}",
        ),
    )

    subject, body = blithchron_brand_email(
        {
            "name": L["name"],
            "contact_name": L.get("contact_name") or "",
            "category": L["category"],
            "package": L["package"],
            "ask_inr": L["ask_inr"],
            "pitch": L["pitch"],
        },
        sender,
    )
    draft_new = False
    existing_o = conn.execute(
        """
        SELECT id FROM outreach
        WHERE target_type='brand' AND target_id=? AND agent_name=?
          AND status!='sent'
        """,
        (brand_id, agent),
    ).fetchone()
    if existing_o:
        conn.execute(
            """
            UPDATE outreach SET subject=?, body=?, to_name=?, to_email=?, from_email=?,
                channel='email', status='draft'
            WHERE id=?
            """,
            (subject, body, L.get("contact_name") or L["name"], email, sender.get("email") or "",
             existing_o["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO outreach (target_type, target_id, channel, subject, body, status,
                agent_name, to_name, to_email, from_email)
            VALUES ('brand', ?, 'email', ?, ?, 'draft', ?, ?, ?, ?)
            """,
            (brand_id, subject, body, agent, L.get("contact_name") or L["name"], email, sender.get("email") or ""),
        )
        draft_new = True
    return action, draft_new


def load_db() -> dict:
    init_db()
    sender = sender_profile()
    inserted = updated = drafts = 0
    with get_conn() as conn:
        # Ensure Blithchron event exists
        ev = conn.execute(
            "SELECT id FROM events WHERE name LIKE 'Blithchron%' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if ev:
            event_id = ev["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO events (name, city, category, event_date, date_label, planning_stage,
                    footfall_estimate, organizer_name, organizer_phone, organizer_email,
                    website, notes, discovery_reason, opportunity_tier, opportunity_score, audience)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "Blithchron '27 — IIT Gandhinagar Cultural Fest",
                    "Gandhinagar",
                    "College cultural fest",
                    "2027-02-04",
                    "4–7 Feb 2027",
                    "seeking_sponsors",
                    22000,
                    "Aarav Malde / Jay Hire / Parishi Shah",
                    "9326144314 / 9137727484 / 9653651177",
                    "blithchron@iitgn.ac.in",
                    "https://blithchron.iitgn.ac.in",
                    "Temporary focus event — SponsorDesk Blithchron pack",
                    "blithchron_pack",
                    "chase",
                    95,
                    "17–24 premier institute students, Gujarat + pan-India",
                ),
            )
            event_id = cur.lastrowid

        for L in LEADS:
            action, draft_new = _upsert_brand(conn, L, SEGMENT, event_id, sender, "blithchron27")
            if action == "inserted":
                inserted += 1
            else:
                updated += 1
            if draft_new:
                drafts += 1

        local_ins = local_upd = 0
        for L in LOCAL_LEADS:
            action, draft_new = _upsert_brand(conn, L, SEGMENT_LOCAL, event_id, sender, "blithchron27_local")
            if action == "inserted":
                local_ins += 1
            else:
                local_upd += 1
            if draft_new:
                drafts += 1

    return {
        "leads": len(LEADS),
        "local": len(LOCAL_LEADS),
        "local_with_phone": sum(1 for x in LOCAL_LEADS if any(c.isdigit() for c in (x.get("phone") or ""))),
        "emailable": sum(1 for x in LEADS if (x.get("email") or "").strip()),
        "inserted": inserted,
        "updated": updated,
        "local_inserted": local_ins,
        "local_updated": local_upd,
        "drafts": drafts,
        "xlsx": str(OUT_XLSX),
    }


if __name__ == "__main__":
    path = build_excel()
    stats = load_db()
    print("xlsx", path)
    print(stats)
