"""Blithchron '27 sponsorship playbook PDF — how deals work, tiers, pricing, close scripts."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "exports" / "Blithchron27_Sponsorship_Playbook_Pricing_Close.pdf"
HIRES = ROOT / "exports" / "extracted" / "brochure_hires"
PAGES = ROOT / "exports" / "extracted" / "brochure_pages"
SPONSOR_IMGS = ROOT / "exports" / "extracted" / "sponsor_imgs"

NAVY = colors.HexColor("#0f172a")
BLUE = colors.HexColor("#1d4ed8")
SOFT = colors.HexColor("#f1f5f9")
LINE = colors.HexColor("#cbd5e1")
GREEN = colors.HexColor("#065f46")
AMBER = colors.HexColor("#92400e")
RED = colors.HexColor("#991b1b")


def styles():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=16, textColor=NAVY, spaceAfter=6, leading=20,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=12, textColor=BLUE, spaceBefore=8, spaceAfter=5, leading=15,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontName="Helvetica-Bold",
            fontSize=9.5, textColor=NAVY, spaceBefore=6, spaceAfter=3, leading=12,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName="Helvetica",
            fontSize=8.2, leading=11, textColor=NAVY, alignment=TA_JUSTIFY, spaceAfter=5,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["BodyText"], fontName="Helvetica",
            fontSize=8, leading=10.5, textColor=NAVY, leftIndent=4,
        ),
        "th": ParagraphStyle(
            "th", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=7, leading=9, textColor=colors.white, alignment=TA_CENTER,
        ),
        "td": ParagraphStyle(
            "td", parent=base["BodyText"], fontName="Helvetica",
            fontSize=6.5, leading=8.4, textColor=NAVY, alignment=TA_LEFT,
        ),
        "warn": ParagraphStyle(
            "warn", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=8, leading=10.5, textColor=RED, spaceAfter=6,
        ),
        "cap": ParagraphStyle(
            "cap", parent=base["BodyText"], fontName="Helvetica-Oblique",
            fontSize=7, textColor=colors.HexColor("#64748b"), spaceBefore=3, spaceAfter=6,
        ),
        "ok": ParagraphStyle(
            "ok", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=8, leading=10.5, textColor=GREEN, spaceAfter=5,
        ),
    }


def P(text, st):
    return Paragraph(str(text).replace("\n", "<br/>"), st)


def brochure_img(path: Path, max_w_mm=130, max_h_mm=160):
    """Embed a brochure page / logo crop, scaled to fit landscape cells."""
    if not path.exists():
        return Paragraph(f"[missing {path.name}]", ParagraphStyle("miss", fontSize=7, textColor=RED))
    img = Image(str(path))
    max_w, max_h = max_w_mm * mm, max_h_mm * mm
    iw, ih = float(img.imageWidth), float(img.imageHeight)
    scale = min(max_w / iw, max_h / ih, 1.0)
    img.drawWidth = iw * scale
    img.drawHeight = ih * scale
    return img


def two_up(left_path, right_path, st, caption_l="", caption_r="", max_h=155):
    """Two brochure pages side-by-side on landscape A4."""
    left = [brochure_img(left_path, 128, max_h)]
    right = [brochure_img(right_path, 128, max_h)]
    if caption_l:
        left.append(P(caption_l, st["cap"]))
    if caption_r:
        right.append(P(caption_r, st["cap"]))
    t = Table([[left, right]], colWidths=[135 * mm, 135 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def logo_grid(paths, st, cols=6, cell_w=42, cell_h=22):
    """Grid of cropped past-sponsor logo images from brochure."""
    cells = []
    row = []
    for p in paths:
        if not p.exists():
            continue
        cell = brochure_img(p, cell_w, cell_h)
        row.append(cell)
        if len(row) == cols:
            cells.append(row)
            row = []
    if row:
        while len(row) < cols:
            row.append(Spacer(1, 1))
        cells.append(row)
    if not cells:
        return P("(no logo crops found — brochure page spreads still included below)", st["cap"])
    t = Table(cells, colWidths=[cell_w * mm] * cols)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.3, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, LINE),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def header_footer(canvas, doc):
    canvas.saveState()
    w, h = landscape(A4)
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 12 * mm, w, 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.drawString(10 * mm, h - 7.5 * mm, "SponsorDesk Playbook  ·  Blithchron '27 (4–7 Feb 2027)  ·  How sponsorship works + pricing + close scripts")
    canvas.setFont("Helvetica", 7.5)
    canvas.drawRightString(w - 10 * mm, h - 7.5 * mm, "Aligned to official brochure + sample proposal")
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, w, 7 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(10 * mm, 2.5 * mm, "Brochure does NOT publish ₹ rates — pitch bands below are market-calibrated openings. Confirm every number with Blithchron before sending a brand proposal.")
    canvas.drawRightString(w - 10 * mm, 2.5 * mm, f"p.{doc.page}")
    canvas.restoreState()


def table(data, col_w, header, st):
    rows = [[P(h, st["th"]) for h in header]]
    for row in data:
        rows.append([P(c, st["td"]) for c in row])
    t = Table(rows, colWidths=col_w, repeatRows=1)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("GRID", (0, 0), (-1, -1), 0.25, LINE),
    ]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), SOFT))
    t.setStyle(TableStyle(cmds))
    return t


# ---- DATA from brochure OCR + proposal + market ----

TIERS = [
    ["1", "Title Sponsor", "₹8–15 Lakh<br/>(open ₹10–12L)", "ONE brand only. Highest logo everywhere. 'Blithchron presented by X'.",
     "Banks (CBI did Title '25), Campa, big telco/fintech, Amul if they want hero.",
     "You are the face of the fest. Every poster, Pronite LED, website masthead, emailer, after-movie. Category lock for your industry if negotiated.",
     "Ask Blithchron: 'Is Title still open? What was last year's ballpark?' Then pitch CBI renewal OR Campa/Amul as Title."],
    ["2", "Co-Title Sponsor", "₹5–8 Lakh", "Second name beside Title. Strong visibility, less cash than Title.",
     "Union Bank / Canara / SBI / AU Bank / big F&B",
     "Shared masthead: 'Title presents Blithchron, Co-Title by Y'. Still exclusive vs other banks if you lock banking category.",
     "If Title sold: sell Co-Title to the other bank. Never put two colas on Co-Title."],
    ["3", "Powered by Sponsor", "₹3.5–6 Lakh", "'Powered by X' line under fest name. Tech/energy often loves this.",
     "Cloud9, realme, Zebronics, PlayStation, Vivo",
     "Logo on all key creatives + stall + stage mention. Less than Title, more than Gold.",
     "Pitch tech/energy: 'Powered by' feels like product energy, not a bank title."],
    ["4", "Pronites Sponsor", "₹4–8 Lakh (both nights)<br/>₹2.5–5L (one night)", "Owns the celebrity nights (6,000+/night). Highest youth heat.",
     "Monster Energy, Campa Energy, Coca-Cola, JBL/Zebronics, fashion",
     "Exclusive for that night/category. LED, MC shoutouts, sampling at gate, after-movie cut.",
     "THIS is where energy drinks belong. Sell 'Official Energy Partner of Pronites'."],
    ["5", "Platinum Sponsor", "₹3–5 Lakh", "Premium multi-event branding below Title stack.",
     "ITC, Nestlé, Hyundai, Gujarat Tourism, Spykar",
     "Website + socials + stall + standees + screen ads + brochure logo.",
     "Good for national FMCG that won't pay Title but want IIT association."],
    ["6", "Gold Sponsor", "₹2–3.5 Lakh", "Strong mid-tier. Most convertible for Gujarat brands.",
     "Balaji, Gopal, Havmor, Vadilal, La Pino'z HQ",
     "Stall + banners + social posts + announcements at 1–2 flagship events.",
     "Default ask for Gujarat FMCG. Easy yes if Title/Platinum feel too heavy."],
    ["7", "Strategic Sponsor", "₹1.5–2.5 Lakh", "Targeted brand goal (recruitment, app installs, sampling).",
     "EaseMyTrip, Unstop, Insiders, fintech",
     "Custom mix of stall + digital + CA reach. Brochure says custom packages exist.",
     "Ask brand: 'What's your KPI — leads, installs, sampling?' Then shape Strategic."],
    ["8", "Core Sponsor", "₹1–2 Lakh", "Solid logo presence + stall. Fills inventory.",
     "Regional F&B, gyms (SFW), beauty (Meraki), local banks",
     "Stall + standees + social mention + flyer distribution.",
     "Use when brand says Gold is too much. Keep deliverables honest."],
    ["9", "Associate Sponsor", "₹75k–1.5 Lakh", "Entry official sponsor. Logo in brochure + some on-ground.",
     "First-time campus brands, startups, local QSR",
     "Website logo, 1 social post, stall OR standees (not always both).",
     "Never oversell Associate as 'everywhere branding'."],
    ["10", "Event Sponsor", "₹50k–1.5 Lakh", "Owns ONE event: Panache / Antaragnee / String Theory / Flavor Fest / Sociothon.",
     "Fashion→Spykar/Souled Store; Food→Maggi/Nestlé; Music→Furtados/Zebronics",
     "Event stage branding, MC mentions during that event, stall near that zone.",
     "Easiest close. Match brand to event from brochure mapping."],
]

PARTNERS = [
    ["Social Media Partner", "₹40k–1.2L or contra", "Handles/boosts fest content; logo as Social Media Partner", "Local agencies / student media / Radio Mirchi digital"],
    ["Outreach Partner", "₹30k–1L or contra", "Helps ticketing/outreach (Insider did this historically)", "Insider, Unstop, college media"],
    ["Online Fashion Partner", "₹50k–1.5L + merch", "Owns online fashion association (Panache synergy)", "The Souled Store, Spykar, Bewakoof"],
    ["Print Media Partner", "Mostly contra", "Coverage in print; logo as Print Partner", "Local Gujarati/English papers"],
    ["Gifting Partner", "Product + ₹25–75k", "Supplies goodie-bag gifts; logo as Gifting Partner", "Instax, FMCG mini packs, merch"],
    ["Hydration / Beverage / Energy (custom exclusive)", "₹1.5–5L + stock", "Category lock: only one water OR cola OR energy", "Krispy Water, Coca-Cola, Campa, Monster, Cloud9, Hustle"],
]

PAST = [
    ["Title / Banking", "Central Bank of India (Title '25), Bank of Baroda, SBI/YONO, Union Bank, Canara Bank, Surat People's Co-op Bank",
     "Banks buy Title/Co-Title for student accounts. CBI already said yes once — renew or pitch AU/IDFC as Co-Title."],
    ["Beverage / Energy / Food", "Coca-Cola, Monster Energy, Maggi, Nestlé/KitKat, Krispy Water (Hydration '25)",
     "Category exclusives work. Pitch Campa Energy into the Monster/Coke lane; Krispy for water renewal."],
    ["FMCG / Lifestyle", "ITC, Spykar, The Souled Store, Woodland, Instax Fujifilm, Meraki Beauty",
     "Fashion→Panache Event Sponsor. Instax→Gifting/Photography. ITC→Platinum/Gold sampling."],
    ["Tech / Gadgets / Gaming", "realme, vivo, Zebronics, PlayStation, BMW Motorrad",
     "Powered By or Pronites/tech stall. realme already appears in past book — warm path."],
    ["Travel / Auto / Tourism", "EaseMyTrip / Trips 24x7, Hyundai, Gujarat Tourism, BMW Motorrad",
     "Strategic/Gold. Student travel + two-wheeler display."],
    ["Media / Outreach / Ed-adjacent", "Radio Mirchi, Insider, Unstop, Interview Buddy, Livdemy, Henry Harvin, Course Hero, Furtados",
     "Partnership categories + Event. Note: Interview Buddy/Henry Harvin are course-ish — you asked to AVOID course-sellers for NEW pitches."],
    ["Others seen in brochure logo pages", "RevUp, Gurjari, HoverRobotix, Evepaper, Patang, Tinder, CCD/cafe brands, AXA, SFW Gym, Codeversity, DST Gujarat",
     "Proof that Blithchron historically mixes national + Gujarat mid brands — your SME pitches are normal here."],
]

EVENT_MAP = [
    ["Pronites (2 nights, 6,000+/night)", "Energy drinks, cola, audio (JBL/Zebronics), fashion, fintech QR", "Pronites Sponsor / Energy Partner / Beverage Partner"],
    ["Panache (fashion show)", "Apparel, footwear, grooming, D2C fashion", "Event Sponsor — Panache / Online Fashion Partner"],
    ["Antaragnee & Street Beat", "Youth lifestyle, snacks, hydration (day crowd near stalls)", "Event Sponsor + stall in activation zone"],
    ["String Theory & Euphony", "Audio tech, beverage, lifestyle", "Event Sponsor"],
    ["Flavor Fest & Aerosol", "FMCG sampling, food brands, paint/visual", "Event Sponsor + sampling rights"],
    ["Sociothon / Quizzitch / Blithmun", "Fintech, consulting, IT recruitment (NOT course-selling coaching)", "Event Sponsor / Strategic"],
]

CLOSE_SCRIPTS = [
    ["Krispy Water", "Hydration Partner (renew)", "₹80k–2L + water stock",
     "1) Call +91 99249 64118 / mail info@krispywater.com. 2) Open: 'You were Hydration Partner for Blithchron '25 — IITGN wants to renew for '27 (4–7 Feb).' 3) Offer exclusive packaged-water lock so no Bisleri/Kinley on-ground. 4) Deliverables: stall + sampling + logo as Hydration Partner + Pronite gate bottles. 5) Ask for written yes in 7 days."],
    ["Campa Energy / RCPL", "Pronites Energy Partner OR Powered By", "₹2.5–6L + cans (or Title if aggressive)",
     "1) LinkedIn Megha Raturi (CMO RCPL) — NOT fake dealership WhatsApps. 2) Story: Monster/Coke have done Blithchron before; Campa Energy is the youth SKU fighting that lane. 3) Ask exclusive ENERGY category (no second energy brand). 4) Offer Pronites sampling + LED + MC 'powered by Campa Energy'. 5) Bundle Campa Cola as Beverage if energy taken. 6) One meeting = Cola + Energy + Sports drink."],
    ["Hustle Energy", "Pronites / Energy Partner", "₹1.5–3.5L + stock",
     "1) Call Sushant Mehta +91 95992 25334 / sushant.mehta@radioheadbrands.com. 2) Say IITGN cultural, 22k footfall, Pronite exclusivity available. 3) They are smaller than Red Bull — faster yes. 4) Lock category exclusivity in the MoU clause."],
    ["Cloud9", "Energy / Powered By", "₹1.5–4L + cans",
     "1) info@thecloud9corp.com / 1800 266 9669 + LinkedIn Vibin Thomas. 2) Position as Indian energy #2 needing IIT cultural proof vs Campa. 3) Same exclusivity rule."],
    ["Coca-Cola / Thums Up XForce (HCCB)", "Official Beverage Partner", "₹2–5L + product (or product-heavy)",
     "1) Find HCCB Gujarat ASM (LinkedIn). 2) Brochure history shows Coca-Cola already associated — renew/upgrade. 3) Pitch Thums Up XForce (new zero-sugar youth SKU) not only classic Thums Up. 4) Exclusive sparkling beverage lock."],
    ["Monster Energy", "Pronites Co-Title / Energy", "₹2–5L + product",
     "1) They appear in past Blithchron sponsors. 2) Pitch Pronites co-brand like Mood Indigo Hip-Hop nite model. 3) If Campa already close, don't double-energy."],
    ["Amul", "Title / Platinum / Food Partner", "₹3–10L or parlour+product",
     "1) gcmmf@amul.coop + retail@amul.coop / 02692-258506. 2) Home-state IIT. 3) Pitch Amul parlour kiosk + chocolate/ice-cream sampling + Title if bank slot open. 4) CSR angle exists in brochure (paying back to society)."],
    ["Balaji Wafers", "Gold / Flavor Fest Event Sponsor", "₹1.5–3L + stock",
     "1) contact@balajiwafers.com / +91 281-2783755. 2) 'Gujarat's snack brand at Gujarat's IIT cultural fest.' 3) Open Gold; if pushback drop to Event Sponsor — Flavor Fest. 4) Sampling near food street."],
    ["Gopal Snacks", "Gold / Associate", "₹1–2.5L + stock",
     "1) info@gopalsnacks.com / 02827-297060. 2) Same Gujarat snack story as Balaji. 3) Don't pitch both Balaji+Gopal as Gold same week without different packages (one Gold, one Event)."],
    ["Havmor / Vadilal", "Gold / Stall + sampling", "₹80k–2.5L + product",
     "1) Both HQ Ahmedabad — walk-in possible. havmor@havmor.com / 079-30909000; Vadilal info@vadilalgroup.com. 2) Feb ice-cream weather. 3) Scooping stall near Pronite queue."],
    ["Central Bank of India", "Title renewal", "₹8–15L",
     "1) They were Title '25. 2) Approach Gandhinagar/Ahmedabad zonal + Corporate Communications. 3) Pitch student accounts + UPI + Title continuity. 4) If they decline, take Co-Title to AU/IDFC and keep CBI as Associate Banking Partner."],
    ["SBI / Union / Canara", "Co-Title / Platinum", "₹3–8L",
     "1) All appear in past sponsor pages. 2) Pitch Co-Title if CBI not renewing. 3) Student savings + YONO/app installs + stall."],
    ["The Souled Store", "Online Fashion Partner / Panache Event", "₹50k–1.5L + merch deal",
     "1) corporate@thesouledstore.com. 2) They are in past brochure. 3) Offer official merch + Panache. Revenue share on tees possible."],
    ["Spykar", "Panache Event / Gold", "₹1–2.5L",
     "1) Past brochure logo. 2) Fashion show = perfect. 3) Styling wardrobe + stage branding."],
    ["realme / vivo", "Powered By / Tech Partner", "₹2–5L + units",
     "1) Both in past book. 2) Lucky-draw phones at Pronite + stall demos. 3) Powered By line fits gadgets."],
    ["Zebronics / PlayStation", "Audio / Gaming Partner", "₹1–3L + gear",
     "1) Past logos. 2) String Theory + Pronite audio wall / gaming zone. 3) Product display heavy."],
    ["Instax Fujifilm", "Gifting / Photography Partner", "Product + ₹40–1L",
     "1) Past brochure. 2) Photo booth + goodie-bag Instax mini film. 3) Easy contra-friendly close."],
    ["EaseMyTrip", "Strategic / Travel Partner", "₹1–2.5L",
     "1) Past brochure. 2) Student travel coupons + stall. 3) App installs KPI."],
    ["ITC / Nestlé / Maggi", "Platinum / Flavor Fest", "₹2–5L + stock",
     "1) All in past sponsors. 2) Maggi night-hunger stall is a proven fest mechanic. 3) Ask Gujarat Area Brand/Trade Marketing."],
    ["La Pino'z / local Domino's", "Food stall / Associate", "₹30–80k or stall-only",
     "1) Local owner first. 2) Food street exclusive pizza. 3) Fastest cash close this week."],
]


STEPS = [
    ["Day 1", "Align with Blithchron", "Call Aarav Malde 9326144314 / Jay Hire 9137727484 / Parishi Shah 9653651177. Ask: (a) which tiers still open, (b) their unpublished rate card, (c) can you sell as authorized associate, (d) commission/ MoU."],
    ["Day 1", "Get authority in writing", "WhatsApp/email confirmation: you may represent Blithchron packages to brands. Without this, brands will ghost you."],
    ["Day 2", "Build shortlist of 12", "1 Title/bank, 1 energy, 1 beverage, 1 water, 2 snacks, 2 ice-cream/F&B, 1 fashion, 1 tech, 2 easy stalls. Use exclusivity — don't pitch 3 energy brands the same day."],
    ["Day 2–3", "Send tailored one-pagers", "Use their Sample Proposal template (blithchron@iitgn.ac.in header). Fill company name + Amount from THIS playbook after Blithchron confirms rates."],
    ["Day 3–7", "Follow up calls", "Script: footfall 22k, Pronite 6k/night, past sponsors like CBI/Coca-Cola/Monster/Maggi, exclusive category available THIS WEEK."],
    ["Close", "MoU + invoice + deliverables list", "Lock exclusivity clause, payment split (50% advance common), logo guidelines, stall size, sampling rules (no competing brand)."],
    ["Your fee", "Broker commission", "Typical private brokerage: 10–15% of cash sponsorship (organizer side). Agree this with Blithchron UPFRONT. Product-only deals = smaller fee or fixed retainer."],
]


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    st = styles()
    doc = SimpleDocTemplate(
        str(OUT), pagesize=landscape(A4),
        leftMargin=8 * mm, rightMargin=8 * mm, topMargin=16 * mm, bottomMargin=10 * mm,
        title="Blithchron '27 Sponsorship Playbook", author="SponsorDesk",
    )
    story = []

    # COVER / INTRO
    story.append(P("Blithchron '27 — Complete Sponsorship Playbook for a New Broker", st["h1"]))
    story.append(P(
        "<b>Built from:</b> official <i>B27 Spons Brochure</i> + <i>Sample Proposal</i> "
        "(Drive links you shared) + OCR of past-sponsor logo pages + India campus-fest market pricing. "
        "<b>Fest:</b> IIT Gandhinagar · <b>4–7 February 2027</b> · ~22,000 cumulative footfall · 15,000+ unique · "
        "60,000+ brand touchpoints · 2 Pronites (6,000+/night) · 100+ partner colleges · "
        "150k+ digital impressions · 25k+ student inbox reach.",
        st["body"],
    ))
    story.append(P(
        "WARNING: The official brochure lists CATEGORIES but does <b>not</b> print rupee prices. "
        "The sample proposal leaves [Amount] blank and says pricing is flexible. "
        "Every ₹ band in this PDF is a <b>pitch-opening estimate</b> for a mid-IIT cultural fest of this scale. "
        "<b>Confirm with Blithchron (Aarav / Jay / Parishi) before you send any number to a brand.</b>",
        st["warn"],
    ))

    story.append(P("0) Official Blithchron contacts (from brochure + proposal)", st["h2"]))
    story.append(P(
        "<b>Jay Hire</b> — +91 91377 27484 — jay.hire@iitgn.ac.in<br/>"
        "<b>Parishi Shah</b> — +91 96536 51177 — parishi.shah@iitgn.ac.in<br/>"
        "<b>Aarav Malde</b> (Sponsorship Executive on sample proposal) — +91 93261 44314 — aarav.malde@iitgn.ac.in<br/>"
        "<b>Team</b> — blithchron@iitgn.ac.in · https://blithchron.iitgn.ac.in · Facebook: Blithchron",
        st["ok"],
    ))

    # HOW IT WORKS
    story.append(P("1) How sponsorship actually works (newbie crash course)", st["h2"]))
    story.append(P(
        "A college fest sells <b>attention + access + association</b>. Brands don't 'donate' — they buy a package of deliverables "
        "(logos, stalls, MC shouts, sampling rights, exclusivity). You sit in the middle: help Blithchron fill packages, "
        "help brands pick the right tier, take a commission when cash lands.<br/><br/>"
        "<b>Exclusivity</b> is the magic word. If Campa Energy pays for 'Official Energy Partner', no Monster/Cloud9/Hustle "
        "can sample energy drinks on ground. That exclusivity is why brands pay more than a plain logo.<br/><br/>"
        "<b>Category partners</b> (Beverage / Hydration / Fashion / Banking) are often more sellable than generic 'Gold' — "
        "Mood Indigo sells 'Official Beverage Partner' (Coca-Cola), 'Hip-Hop Nite Title' (Yousta), etc. "
        "Blithchron brochure lists money tiers + partnership categories; you can also propose custom exclusives "
        "(the brochure explicitly offers <b>Custom Packages</b>).<br/><br/>"
        "<b>Cash vs product (contra):</b> Water/FMCG often pay partly in stock. Banks/fintech pay cash. "
        "Your commission is usually on cash only unless agreed otherwise.",
        st["body"],
    ))

    story.append(P("2) Blithchron sponsorship ladder (exact names from their brochure)", st["h2"]))
    story.append(table(
        TIERS,
        [8*mm, 28*mm, 28*mm, 42*mm, 40*mm, 55*mm, 56*mm],
        ["#", "Tier (brochure)", "Pitch ₹ band*", "What it means", "Best brand types", "What brand gets (in practice)", "How YOU close it"],
        st,
    ))
    story.append(P(
        "*Pitch band = opening range for negotiation. Confirm with Blithchron. Market anchors: "
        "Coll-Edge 2025 guide (Tier-1 title ₹2–15L; stall ₹25k–1.5L; sampling ₹50k–4L); "
        "Vels Nakshatra Title ₹10L / Platinum ₹5L; NITK Incident Title ₹15L / Bronze ₹1L. "
        "Blithchron sits mid-IIT cultural (~22k footfall) — open below mega-fest (Mood Indigo / Antaragni) Title.",
        st["cap"],
    ))

    # Official brochure category pages (real images)
    story.append(PageBreak())
    story.append(P("2b) Official brochure pages — Sponsorship + Partnership categories (read every word)", st["h2"]))
    story.append(P(
        "These are screenshots from Blithchron's own brochure. Money tiers (left) + partnership/exclusive-style slots (right). "
        "When a brand asks 'what categories exist?', show them this ladder — then quote a ₹ band from Section 2 / cheat-sheet.",
        st["body"],
    ))
    cat_l = HIRES / "p17.png" if (HIRES / "p17.png").exists() else PAGES / "page_17.png"
    cat_r = HIRES / "p18.png" if (HIRES / "p18.png").exists() else PAGES / "page_18.png"
    story.append(two_up(
        cat_l, cat_r, st,
        "Brochure p17 — Title → Event → Pronites ladder",
        "Brochure p18 — Social / Outreach / Fashion / Print / Gifting partners",
    ))

    story.append(PageBreak())
    story.append(P("2c) Official brochure — Custom packages + Deliverables + CSR angle", st["h2"]))
    story.append(P(
        "Brochure explicitly allows <b>Custom Packages</b> (use this to invent Beverage / Energy / Hydration exclusives). "
        "Deliverables page is short — expand with Sample Proposal offerings when you write the brand one-pager. "
        "CSR page = banks &amp; Amul love this line in proposals.",
        st["body"],
    ))
    d_l = HIRES / "p19.png" if (HIRES / "p19.png").exists() else PAGES / "page_19.png"
    d_r = HIRES / "p20.png" if (HIRES / "p20.png").exists() else PAGES / "page_20.png"
    story.append(two_up(d_l, d_r, st, "Custom Packages — tailor to brand KPI", "Deliverables — Live Display / Banners / Volunteers / Social / Stalls"))
    story.append(Spacer(1, 3 * mm))
    csr = HIRES / "p21.png" if (HIRES / "p21.png").exists() else PAGES / "page_21.png"
    story.append(KeepTogether([
        brochure_img(csr, 130, 100),
        P("Paying back to society — education of poor children, cleanliness, blood donation. Quote this for bank/Amul CSR narratives.", st["cap"]),
    ]))

    story.append(PageBreak())
    story.append(P("3) Partnership / exclusive categories (brochure page + custom exclusives you invent)", st["h2"]))
    story.append(table(
        PARTNERS,
        [45*mm, 35*mm, 85*mm, 92*mm],
        ["Partnership type", "Pitch ₹ / contra", "What you sell", "Who to call"],
        st,
    ))
    story.append(P(
        "<b>Exclusivity cheat (not printed as ₹ but how big fests sell):</b> "
        "Official Beverage Partner · Official Energy Partner · Official Hydration Partner · Official Banking Partner · "
        "Online Fashion Partner · Pronites Title for Night-1 / Night-2. "
        "One brand per category. Put the lock in the MoU.",
        st["ok"],
    ))

    story.append(P("4) Deliverables checklist (brochure + sample proposal — use this in every pitch)", st["h2"]))
    story.append(P(
        "<b>From brochure 'Deliverables':</b> Live Display · Banners &amp; Hoardings · Marketing by Volunteers · "
        "Social Media Coverage · Dedicated Stalls.<br/>"
        "<b>From Sample Proposal (offerings):</b> exclusive stall (4 days) · website logo + redirect · dedicated IG/FB posts "
        "(they claim 350,000+ reach) · standees/banners · live announcements at Synchronize / Pronites / Antaragnee · "
        "CSR activity branding · flyer distribution by ground team · logo/ads on main screens · Campus Ambassador marketing "
        "across Gujarat colleges · email newsletters (20k+ visibility) · Flash mob branding in Ahmedabad &amp; Gandhinagar · "
        "after-movies/recap · logo in Sponsorship/Marketing/Events brochures · press releases &amp; media partner coverage.<br/>"
        "<b>When pitching:</b> pick 6–10 deliverables that match the tier. Don't promise Title-level LED to an Associate.",
        st["body"],
    ))

    story.append(P("5) Map brand → flagship event (from brochure event pages)", st["h2"]))
    story.append(table(
        EVENT_MAP,
        [55*mm, 100*mm, 102*mm],
        ["Blithchron property", "Brand fit", "Package to open with"],
        st,
    ))

    story.append(PageBreak())
    story.append(P("6) Past sponsors — REAL brochure logo pages (your proof on every call)", st["h2"]))
    story.append(P(
        "Screenshots below are from Blithchron brochure pages 23–29 ('Our previous Sponsors'). "
        "Say on calls: <i>'Brands like Coca-Cola, Monster, Maggi, SBI and The Souled Store have already associated with Blithchron — here's the slot that fits you.'</i>",
        st["body"],
    ))
    # Cropped logo tiles first
    logo_paths = sorted(SPONSOR_IMGS.glob("p*.png")) if SPONSOR_IMGS.exists() else []
    # Prefer a readable subset — skip tiny/odd crops if too many; show up to 30
    if logo_paths:
        story.append(P("Logo crops pulled from brochure sponsor spreads:", st["h3"]))
        story.append(logo_grid(logo_paths[:30], st, cols=6, cell_w=42, cell_h=18))
        story.append(Spacer(1, 3 * mm))

    story.append(table(
        PAST,
        [40*mm, 110*mm, 107*mm],
        ["Category", "Brands seen in brochure / public '25 posts", "How you use this in a pitch"],
        st,
    ))
    story.append(P(
        "Also publicly confirmed for Blithchron '25: <b>Central Bank of India = Title Sponsor</b>; "
        "<b>Krispy Water = Hydration Partner</b>; Renaissance; Interview Buddy.",
        st["cap"],
    ))

    # Full past-sponsor spreads (real images)
    story.append(PageBreak())
    story.append(P("6b) Brochure past-sponsor spreads (pages 23–26) — show brands this proof", st["h2"]))
    for a, b in [(23, 24), (25, 26)]:
        pa = HIRES / f"p{a:02d}.png" if (HIRES / f"p{a:02d}.png").exists() else PAGES / f"page_{a:02d}.png"
        pb = HIRES / f"p{b:02d}.png" if (HIRES / f"p{b:02d}.png").exists() else PAGES / f"page_{b:02d}.png"
        story.append(two_up(pa, pb, st, f"Brochure p{a}", f"Brochure p{b}", max_h=148))
        story.append(PageBreak())

    story.append(P("6c) Brochure past-sponsor spreads (pages 27–29) + contacts page", st["h2"]))
    for a, b in [(27, 28), (29, 30)]:
        pa = HIRES / f"p{a:02d}.png" if (HIRES / f"p{a:02d}.png").exists() else PAGES / f"page_{a:02d}.png"
        pb = HIRES / f"p{b:02d}.png" if (HIRES / f"p{b:02d}.png").exists() else PAGES / f"page_{b:02d}.png"
        story.append(two_up(pa, pb, st, f"Brochure p{a}", f"Brochure p{b}", max_h=148))
        if a == 27:
            story.append(PageBreak())

    story.append(P("7) Detailed close scripts (what to say, what to ask, what ₹ to open)", st["h2"]))
    story.append(table(
        CLOSE_SCRIPTS,
        [32*mm, 32*mm, 28*mm, 165*mm],
        ["Brand", "Package to sell", "Open with ₹", "Step-by-step close (say this / do this)"],
        st,
    ))

    story.append(PageBreak())
    story.append(P("8) Your 7-day operating plan (so you don't freeze)", st["h2"]))
    story.append(table(
        STEPS,
        [22*mm, 40*mm, 195*mm],
        ["When", "Action", "Exactly what to do"],
        st,
    ))

    story.append(P("9) Negotiation scripts — detailed versions you can rehearse", st["h2"]))

    story.append(P("<b>A. Cold open (phone / LinkedIn / walk-in):</b>", st["h3"]))
    story.append(P(
        "\"Hi [Name], I'm [Your name] working with Blithchron '27 — IIT Gandhinagar's annual cultural fest, 4–7 Feb 2027. "
        "About 22,000 footfall, two Pronites with 6,000+ a night, 100+ partner colleges across Gujarat, and 150k+ digital impressions. "
        "Past associates include Central Bank of India (Title '25), Coca-Cola, Monster Energy, Maggi, SBI and The Souled Store — "
        "their logos are in the official brochure. "
        "We're closing the <b>[Energy Partner / Official Beverage / Gold / Panache Event]</b> slot this fortnight with "
        "<b>category exclusivity</b> so no competitor samples beside you. "
        "Can I send a one-page proposal with deliverables and investment band today, and book 15 minutes tomorrow?\"",
        st["body"],
    ))

    story.append(P("<b>B. When they say 'send an email' (don't die here):</b>", st["h3"]))
    story.append(P(
        "\"Absolutely — I'll mail within the hour. Quick question so I don't waste your time: "
        "are you looking more for <b>sampling + stall</b>, <b>stage/Pronite branding</b>, or <b>Title-level naming</b>? "
        "And is campus in your Q4/Q1 budget?\" "
        "→ Then send Sample Proposal filled with company name + Amount from cheat-sheet + 6–8 deliverables only. "
        "Subject: <i>Blithchron '27 IITGN — [Energy Partner] exclusivity open · 4–7 Feb</i>. "
        "Follow up in 48h: 'Did the one-pager land? Happy to walk through in 10 mins.'",
        st["body"],
    ))

    story.append(P("<b>C. When they say 'too expensive':</b>", st["h3"]))
    story.append(P(
        "\"Understood — Title/Gold isn't mandatory. Three honest options: "
        "(1) <b>Event Sponsor</b> for Flavor Fest / Panache at ₹[50k–1.5L], "
        "(2) <b>sampling stall + 2 social posts</b> at ₹[25–80k] + stock, "
        "(3) keep category exclusivity but shrink to one Pronite night at ₹[2.5–5L]. "
        "What budget line are you working with for campus this quarter? I'll reshape the package around that number.\"",
        st["body"],
    ))

    story.append(P("<b>D. When they want only product (contra):</b>", st["h3"]))
    story.append(P(
        "\"We can do a hybrid: ₹A cash + ₹B worth of stock at MRP. Cash covers banners/LED/production; stock covers sampling. "
        "Blithchron still needs a cash floor for Pronite costs — typical energy/beverage deals close around "
        "40–60% cash + rest product. What's the maximum cash you can approve this week?\"",
        st["body"],
    ))

    story.append(P("<b>E. When they ask 'why should we pay this vs Meta ads?':</b>", st["h3"]))
    story.append(P(
        "\"Meta buys impressions. This buys <b>physical sampling + IIT association + category lock + MC shoutouts "
        "in front of 6,000 Pronite students</b> who already have purchasing power for apparel, F&amp;B, fintech and gadgets "
        "(brochure demography 17–24, high LTV). Past proof: CBI took Title; Krispy took Hydration; Coke/Monster/Maggi sampled. "
        "You're not buying a logo — you're buying the only [energy/water/cola] brand allowed on ground.\"",
        st["body"],
    ))

    story.append(P("<b>F. When they stall ('we'll decide later'):</b>", st["h3"]))
    story.append(P(
        "\"Fair — two things though: (1) category exclusivity is first-come — if Campa/Monster locks Energy, we can't offer you the same lane; "
        "(2) creatives for Pronite LED need logo files ~3–4 weeks out. "
        "Can we hold the slot with a soft yes + MoU draft by Friday, payment 50% on signing?\"",
        st["body"],
    ))

    story.append(P("<b>G. Close / ask for the money:</b>", st["h3"]))
    story.append(P(
        "\"Perfect — I'll send the MoU tonight with: package name, ₹[agreed], 50% advance to Blithchron IITGN account, "
        "exclusivity clause, deliverables list, stall size, and logo deadline. "
        "Who signs on your side — and can we schedule a 10-min call with Aarav/Jay from the fest team so you hear it from organizers too?\"",
        st["body"],
    ))

    story.append(P("<b>H. Exclusivity clause (must be in MoU):</b>", st["h3"]))
    story.append(P(
        "\"Sponsor shall be the sole brand in the [Energy Drink / Packaged Water / Sparkling Beverage / Banking / Fashion] category "
        "on Blithchron '27 premises and in official creatives labelled for that category during 4–7 February 2027. "
        "Organizer shall not accept competing brands in the same category for sampling, stall, or named partnership.\"",
        st["body"],
    ))

    story.append(P("9b) Peer-fest pricing history (so your ₹ ask feels real)", st["h2"]))
    peer = [
        ["Coll-Edge 2025 guide (India campus)", "Title Tier-1 ₹2–15L · Stall ₹25k–1.5L · Sampling ₹50k–4L", "Industry benchmark — cite freely"],
        ["Vels Nakshatra 2025 (pub. brochure)", "Title ₹10L · Associate ₹7L · Platinum ₹5L · Diamond ₹3L · Silver ₹1L", "Non-IIT but published — proves ₹1–10L is normal"],
        ["NITK Incident 2024 (slabs doc)", "Title ₹15L · Co-Sponsor ₹12L · … Bronze ₹1L", "NIT cultural — Blithchron Title should usually sit under this unless bank mega-deal"],
        ["Blithchron '25 known deals", "CBI = Title (cash; amount unpublished) · Krispy = Hydration Partner", "Use as social proof, not as a leaked rate"],
        ["Your Blithchron '27 open asks", "Title ₹10–12L · Gold ₹2–3.5L · Event ₹50k–1.5L · Energy excl. ₹1.5–6L", "Confirm with Aarav/Jay/Parishi BEFORE brand mail"],
    ]
    story.append(table(peer, [55*mm, 110*mm, 92*mm], ["Source", "Published / known bands", "How you use it"], st))

    story.append(P("10) Pricing cheat-sheet (print this page)", st["h2"]))
    cheat = [
        ["Title", "₹10–12L open (band 8–15L)", "CBI lane / Amul / Campa mega"],
        ["Co-Title", "₹5–8L", "Second bank / big F&B"],
        ["Powered By", "₹3.5–6L", "Tech / energy"],
        ["Pronites (both)", "₹4–8L", "Energy / cola / audio"],
        ["Pronites (one night)", "₹2.5–5L", "Same"],
        ["Platinum", "₹3–5L", "ITC / Nestlé / auto"],
        ["Gold", "₹2–3.5L", "Balaji / Gopal / Havmor"],
        ["Strategic", "₹1.5–2.5L", "Travel / app / KPI deals"],
        ["Core", "₹1–2L", "Regional brand"],
        ["Associate", "₹75k–1.5L", "First campus buy"],
        ["Event Sponsor", "₹50k–1.5L", "Panache / Maggi stall / bands"],
        ["Hydration exclusive", "₹80k–2L + stock", "Krispy renewal"],
        ["Beverage exclusive", "₹2–5L + stock", "Coke / Campa Cola"],
        ["Energy exclusive", "₹1.5–6L + cans", "Campa Energy / Monster / Cloud9 / Hustle"],
        ["Fashion partner", "₹50k–1.5L + merch", "Souled Store / Spykar"],
        ["Stall only", "₹25–80k", "Local QSR"],
        ["Gifting contra", "Product + ₹25–75k", "Instax / FMCG minis"],
    ]
    story.append(table(cheat, [45*mm, 55*mm, 157*mm], ["Package", "Open with", "Notes"], st))
    story.append(P(
        "Rule of thumb: never email a brand a number Blithchron hasn't blessed. Your first call every morning is Aarav/Jay/Parishi. "
        "Your second call is Krispy / Campa / Hustle / Balaji. Fill Title last unless a bank is hot.",
        st["body"],
    ))

    story.append(P("11) What NOT to do", st["h2"]))
    story.append(P(
        "• Don't invent personal Gmails of brand managers.<br/>"
        "• Don't use fake Campa/Hell/Sting 'dealership' WhatsApp numbers.<br/>"
        "• Don't pitch course-selling institutes if organizer restricted that.<br/>"
        "• Don't put two energy brands in the same proposal week.<br/>"
        "• Don't promise Mood Indigo-level deliverables Blithchron didn't list.<br/>"
        "• Don't collect money in your personal account — fest invoice only.",
        st["body"],
    ))

    story.append(P(
        "Sources: Blithchron '27 Sponsorship Brochure + Sample Proposal (your Drive files); "
        "OCR of brochure sponsor pages 23–29; Coll-Edge 2025 College Sponsorship Pricing Guide; "
        "peer fest public rate cards (Title often ₹2–10L); Mood Indigo public sponsor-tier naming for exclusivity patterns; "
        "CBI Title + Krispy Hydration public '25 announcements.",
        st["cap"],
    ))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return OUT


if __name__ == "__main__":
    p = build()
    print(p)
    print("bytes", p.stat().st_size)
