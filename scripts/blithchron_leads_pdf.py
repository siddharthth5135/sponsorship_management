"""Generate Blithchron '27 sponsor-lead PDF from verified public contacts only."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = (
    Path(__file__).resolve().parent.parent
    / "exports"
    / "Blithchron27_Sponsor_Leads_Oct2026.pdf"
)

NAVY = colors.HexColor("#0f172a")
BLUE = colors.HexColor("#1d4ed8")
SOFT = colors.HexColor("#f1f5f9")
LINE = colors.HexColor("#cbd5e1")
GREEN = colors.HexColor("#065f46")
AMBER = colors.HexColor("#92400e")

# Table A: 55 high-conversion / reachable pitches. No course-selling institutes.
# Contact fields are public inboxes / published phones / named public roles — not invented DMs.
HIGH = [
    # Past-partner / proven Blithchron path
    ["1", "Krispy Water (Giribala Ayurved LLP)", "Hydration / alkaline water — Ahmedabad–Gandhinagar",
     "Suniel Nayak, CEO", "info@krispywater.com", "+91 99249 64118",
     "WAS Blithchron '25 Hydration Partner. Fastest yes — ask to renew + upgrade stall.",
     "₹40k–1.5L or product", "https://krispywater.com"],
    ["2", "Central Bank of India", "PSU bank — 2025 Title Sponsor",
     "Gandhinagar / Ahmedabad Zonal / Corporate Communications",
     "customercare@centralbank.co.in", "1800 22 1911 / local zonal office",
     "Title sponsor last edition. Pitch student-account + brand-recall, not a cold logo buy.",
     "Title / associate", "Walk-in CBI Gandhinagar zonal + LinkedIn CBI Corporate Communications"],
    ["3", "Amul (GCMMF, Anand)", "Gujarat dairy — campus parlour + sampling",
     "Corporate / Retail franchise desk", "gcmmf@amul.coop · retail@amul.coop",
     "+91 2692 258506 / 022 6852 6666 (parlour)",
     "Home-state IIT cultural fest. Pitch Amul parlour kiosk + chocolate/ice-cream sampling.",
     "₹1–4L or parlour+product", "https://amul.com/contact-us"],
    ["4", "Balaji Wafers Pvt Ltd", "Rajkot FMCG snacks — Gujarat youth staple",
     "Corporate inbox (ask for Brand / Trade Marketing)", "contact@balajiwafers.com",
     "+91 281 2783755 / +91 70690 14141",
     "Local giant, still approachable. Pitch sampling + stall, not title. Mention 22k IITGN footfall.",
     "₹1–3L + stock", "https://www.balajiwafers.com/pages/contact"],
    ["5", "Gopal Snacks Ltd", "Rajkot listed namkeen — spoke at TiECON",
     "Corporate / inquiries (ask Brand Manager)", "info@gopalsnacks.com · inquiries@gopalsnacks.com",
     "02827 297060 / +91 85112 12345",
     "Listed Gujarat snack brand hunting youth visibility. Pitch associate + sampling, not title.",
     "₹1–3L", "https://www.gopalnamkeen.com/contact"],
    ["6", "Havmor Ice Cream (Lotte)", "Ahmedabad-HQ ice cream — 72k outlets",
     "HQ inbox; VP Marketing Rishabh Verma (LinkedIn)", "havmor@havmor.com",
     "+91 79 3090 9000",
     "HQ is in Ahmedabad. Feb–Mar fest = ice-cream weather. Pitch scooping stall + branding.",
     "₹80k–2.5L + product", "https://www.havmor.com"],
    ["7", "Vadilal Ice Creams", "Ahmedabad-HQ ice cream",
     "CMO Ravi Makwana (LinkedIn) / brand parlours", "info@vadilalgroup.com · ice.vadilal@yahoo.com",
     "+91 79 2656 4018 / 079 3015 3325",
     "Same as Havmor — local HQ, youth SKUs. Ask for Gujarat Brand / Parlour team.",
     "₹80k–2.5L", "https://vadilalicecreams.com"],
    ["8", "Cloud9 Energy Drink", "Indian energy drink #2 — campus sampling machine",
     "CMO Vibin Thomas / VP Mktg Mannoj Chawla (LinkedIn)", "info@thecloud9corp.com",
     "1800 266 9669",
     "Fits Blithchron energy-drink preference. Pitch Pronite / gaming / dance-stage hydration.",
     "₹1.5–4L + cans", "https://cloud9beverages.com"],
    ["9", "Hustle Energy (Radiohead Brands)", "Indian energy drink — named trade desk",
     "Sushant Mehta, Trade inquiries", "sushant.mehta@radioheadbrands.com · hustle@radioheadbrands.com",
     "+91 95992 25334 (trade, no WhatsApp)",
     "Rare: a named energy-drink trade contact. Pitch IITGN cultural + sampling rights.",
     "₹1–3L + stock", "https://hustleenergydrink.com/pages/contactus"],
    ["10", "Sipora / Thanda Shanda", "Delhi energy / flavoured drink — marketing inbox",
     "Marketing desk", "mkt@siporabeverages.com", "+91 98702 48247",
     "Smaller energy brand — they answer marketing mail. Easy to convince vs Red Bull HQ.",
     "₹50k–1.5L + stock", "https://www.siporabeverages.com/contact-us.html"],
    ["11", "Red Bull India", "Global energy — owns campus culture",
     "India sponsorship desk (official form)", "customercare.india@redbull.com + official form",
     "Use form (not random LinkedIn spam)",
     "Harder close, huge brand. Use official India sponsorship form. Pitch dance/Pronite, not stall-only.",
     "Product + activation (cash rare)",
     "https://contact.redbull.com/hc/in-en/requests/new?ticket_form_id=29142927090834"],
    ["12", "Monster Energy India", "Energy drink — filings list India entity",
     "India entity (route to brand / events)", "Angela.Lovas@Monsterenergy.com (entity email on ROC)",
     "Mumbai registered office",
     "Treat as legal/entity email — ask to forward to India Brand / Events. Parallel: LinkedIn Monster India Marketing.",
     "Product + activation", "Company filing / LinkedIn Monster Energy India"],
    ["13", "Paper Boat (Hector Beverages)", "Youth drinks — SNITCH/campus-style activations",
     "Brand inbox; AVP Mktg Shubham Meena (LinkedIn)", "paperboat@hectorbeverages.com",
     "1860 425 4425",
     "Non-alcoholic, campus-safe. Pitch sampling wall + merch, not energy. Easy narrative.",
     "₹1–3L + product", "Hector Beverages public contact"],
    ["14", "La Pino'z Pizza", "QSR — Gujarat dense; franchise + brand stall",
     "Franchise / brand enquiry", "info@lapinozpizza.in · support@lapinozpizza.in",
     "82382 35444 / 0176-2509231",
     "High conversion: Ahmedabad–Gandhinagar outlets want IIT weekend traffic. Pitch food stall + branding.",
     "₹50k–2L or stall-only", "https://lapinozpizza.in/contact-us"],
    ["15", "The Souled Store", "Youth apparel — already has college/corporate desk",
     "Corporate / college merchandise", "corporate@thesouledstore.com · connect@thesouledstore.com",
     "022-3965 3110 (Mon–Fri 11–6)",
     "They already sell college merch. Pitch official Blithchron merch + stall, revenue share.",
     "Merch deal / ₹50k–1.5L", "https://www.thesouledstore.com"],
    ["16", "Arogyam Juice", "Ahmedabad cold-press — founder answers",
     "Founder inbox", "arogyamjuice@gmail.com", "+91 88660 06692",
     "Small, local, sampling-ready. Easy first cheque while you chase Campa/Amul.",
     "₹10–50k + juice", "https://arogyamjuice.com"],
    ["17", "Wawa Bakery", "Ahmedabad bakery + college kiosk format",
     "Franchise / brand", "contact@wawabakery.com", "+91 99099 03550",
     "They sell campus kiosks. Pitch Blithchron as a 3-day pop-up, not a logo ad.",
     "₹20–80k", "https://wawabakery.com"],
    ["18", "Cool N Fresh", "Ahmedabad dairy-shake franchise",
     "Franchise inbox", "info@coolnfresh.in", "+91 98250 60577",
     "Youth shake brand. Pitch stall + sampling near Pronite queue.",
     "₹20–80k", "https://www.coolnfresh.in"],
    ["19", "Santushti Shakes & More", "Vadodara 45+ outlet shake brand",
     "Corporate HQ", "info@santushtishakes.com", "+91 99241 98933",
     "Mid-size Gujarat F&B. Will understand IITGN footfall. Offer stall + branding.",
     "₹25–1L", "https://santushtishakes.com"],
    ["20", "Ajwa Food Products", "Surat syrups / premix — MD reachable",
     "Wasim Merchant, MD", "info@ajwafoodproducts.com", "+91 98259 68882",
     "SME owner inbox. Pitch sampling of shakes/syrups at food street.",
     "₹15–60k + product", "https://ajwafoodproduct.com"],
    ["21", "Dairyfun Ice Cream", "Surat SME ice cream — owner mail",
     "Owner inbox", "dairyfunsurat@gmail.com", "+91 98793 63128",
     "Small maker. Cheap stall, high reply odds. Good for filling food-partner slots.",
     "₹10–40k + product", "https://dairyfunicecream.com"],
    ["22", "Khushboo Ice Cream", "Rajkot regional ice cream",
     "Brand inbox", "khushbooice@yahoo.com", "+91 85000 17000",
     "Saurashtra brand wanting Ahmedabad–Gandhinagar visibility.",
     "₹15–70k", "https://www.khushbooicecream.in"],
    ["23", "Maharana Foods", "Bardoli namkeen since 1982",
     "Corporate inbox", "info@maharanafoods.com", "+91 96383 71919",
     "Regional snack — more reachable than Haldiram. Pitch sampling packs.",
     "₹20–80k", "https://maharanafoods.com"],
    ["24", "The Project Cafe", "Ahmedabad cafe with collaborations inbox",
     "Collaborations", "tpco@theprojectcafe.in", "+91 63598 87607",
     "They ask for collabs. Pitch after-party / artist lounge, not title.",
     "₹10–40k or contra", "Public collaborations inbox"],
    ["25", "Shanti's Cereals", "Rajkot breakfast / youth snack FMCG",
     "Corporate inbox", "info@shantis.com", "+91 93113 18973",
     "Pitch breakfast/energy-bar sampling at morning events + merch.",
     "₹25–1L", "https://www.shantis.in"],
    ["26", "TopSpin Club", "Ahmedabad sports club — student memberships",
     "Club desk", "help@topspinclub.in", "+91 99306 63000",
     "Not a fest regular, but student-membership leads convert. Cheap stall.",
     "₹15–60k", "https://support.topspinclub.in"],
    ["27", "Paragraph Coworking", "SG Highway coworking — student/startup desks",
     "Hello / corporate", "hello@paragraph.business · corporate@paragraph.business",
     "+91 98251 10514",
     "Pitch IIT founders + alumni lounge branding. Small cheque, fast yes.",
     "₹10–50k", "https://paragraph.business"],
    ["28", "FreshQo (Good Ant)", "Ahmedabad produce retail — franchise mgr",
     "Bhargav Shah, Franchise Manager", "freshqo@goodant.io", "+91 91732 24828",
     "Local retail. Only if you need a cheap Gujarat logo for the brochure.",
     "₹10–40k", "https://freshqo.in"],
    ["29", "Varun Beverages Ltd (Pepsi / Sting)", "PepsiCo bottler — Sting energy + Pepsi",
     "Gujarat Area / Regional Sales (LinkedIn 'VBL Ahmedabad')",
     "Official domains only: @rjcorp.in / @varunbeverages.com",
     "+91 124 464 3100 (Gurgaon HQ) — then ask Gujarat sales",
     "THIS is how you get Sting on campus. Ignore fake 'Sting dealership' WhatsApps. Find VBL Gujarat ASM on LinkedIn.",
     "Product + activation", "https://www.varunbeverages.com"],
    ["30", "Hindustan Coca-Cola / Thums Up", "Coke system — Thums Up XForce youth SKU",
     "Gujarat bottler sales + Coca-Cola India brand (LinkedIn)",
     "Use official Coca-Cola India 'Contact us' + local HCCB sales",
     "Local HCCB depot (Ahmedabad) — ask Sales Manager",
     "Pitch Thums Up XForce (new zero-sugar youth SKU), not classic Thums Up title.",
     "Product + activation", "HCCB Ahmedabad depot / LinkedIn"],
    ["31", "Tata Consumer (Tata Salt / Teaplus / Soulfull)", "Tata youth + pantry brands",
     "Nidhi Verma, Head IR & Corporate Communications (public)",
     "nidhi.verma@tataconsumer.com (IR/comms — ask to route Brand)",
     "Tata Consumer website / investors page",
     "Ask her office to route to Soulfull / Himalayan / ready-to-eat brand manager.",
     "₹2–6L (slower)", "https://www.tataconsumer.com/investors"],
    ["32", "AU Small Finance Bank", "Jaipur–Gujarat bank — campus-active",
     "Corporate Communications / Ahmedabad cluster head (LinkedIn)",
     "customercare@aubank.in (ask for Brand / Campus)",
     "Local AU branch GM Gandhinagar + LinkedIn 'AU Bank Marketing'",
     "They already run campus hiring. Pitch student savings + UPI + stall, like CBI did.",
     "₹1–4L", "https://www.aubank.in"],
    ["33", "IDFC FIRST Bank", "Youth/digital bank — campus accounts",
     "Brand / Student banking (LinkedIn)", "Use official 'Write to us' + LinkedIn Brand",
     "Local branch + 1800 419 4332",
     "Pitch FIRST Wow / student account. Faster than SBI/HDFC title process.",
     "₹1.5–5L", "https://www.idfcfirstbank.com"],
    ["34", "Bandhan Bank", "Expanding in Gujarat — youth accounts",
     "Ahmedabad cluster / Corporate Comms", "Official contact form + cluster head LinkedIn",
     "Local branch manager first",
     "Easier than HDFC. Pitch associate + account-opening desk.",
     "₹80k–2.5L", "https://bandhanbank.com"],
    ["35", "Kotak 811 / Kotak Mahindra Bank", "Youth digital account product",
     "811 product / Youth marketing (LinkedIn)", "Official Kotak 'Contact' + 811 team LinkedIn",
     "1860 266 2666 then ask Brand",
     "811 is built for students. Pitch QR + stall, not title.",
     "₹1–4L", "https://www.kotak.com"],
    ["36", "PhonePe", "UPI — campus QR / rewards",
     "Campus / Partnerships (LinkedIn 'PhonePe partnerships')",
     "Use PhonePe business / merchant + partnerships LinkedIn",
     "No public CMO mail — do not use support@ for this",
     "Pitch official UPI partner + Pronite QR. Conversion = activation, not cash title.",
     "Activation / contra", "LinkedIn PhonePe Campus or Partnerships"],
    ["37", "Jio / JioCinema / JioHotstar", "Reliance youth + cricket surround",
     "Jio Marketing / campus (LinkedIn) + RCPL if bundled with Campa",
     "Do not use random jio@ mails — LinkedIn Jio Marketing India",
     "Reliance Retail / Jio center lead locally",
     "Best as a bundle with Campa Energy (same group). One meeting, two logos.",
     "Activation", "LinkedIn + Jio store cluster manager"],
    ["38", "Airtel Thanks / Airtel Payments Bank", "Telecom youth packs",
     "Gujarat Circle Marketing (LinkedIn 'Airtel Gujarat')",
     "Circle office, not wecare@airtel.com",
     "Airtel Gujarat circle office Ahmedabad",
     "Circle marketing buys campus. Walk-in circle office beats national inbox.",
     "₹1–4L", "Airtel Gujarat Circle, Ahmedabad"],
    ["39", "boAt (Imagine Marketing)", "Audio / wearables — campus merch king",
     "Brand / Campus (LinkedIn) + care for routing",
     "care@boat-lifestyle.com (ask Brand Partnerships)",
     "Official site contact",
     "Pitch earphone sampling + Pronite. They historically buy campuses.",
     "₹1–4L + product", "https://www.boat-lifestyle.com"],
    ["40", "Noise (Nexxbase)", "Wearables — student smartwatch",
     "Brand partnerships (LinkedIn)", "support@gonoise.com (ask Brand / Campus)",
     "Official site",
     "Same play as boAt. Offer lucky-draw smartwatch at Pronite.",
     "₹80k–3L + units", "https://www.gonoise.com"],
    ["41", "Wow! Momo", "QSR — college food street regular",
     "Brand / local franchisee Ahmedabad–Gandhinagar",
     "Official website contact / local outlet owner first",
     "Nearest outlet manager + brand LinkedIn",
     "Start with the local franchisee — they can say yes to a stall this week.",
     "Stall / ₹30–80k", "Local outlet + wowmomo.com"],
    ["42", "The Belgian Waffle Co.", "Dessert QSR — fest food street",
     "Franchise / local Ahmedabad partner",
     "Official franchise mail on site + local owner",
     "Local outlet",
     "Same as Wow Momo — local owner first, brand later.",
     "Stall / ₹25–70k", "Official site franchise page"],
    ["43", "Domino's (Jubilant FoodWorks)", "Pizza — IIT weekend delivery + stall",
     "Gujarat Area Manager (LinkedIn) / JFL marketing",
     "investor@jublfood.com is IR only — use Area Manager",
     "Nearest Domino's SG Highway / Gandhinagar owner",
     "Highest-odds pizza: local store funds a stall for IIT weekend volume.",
     "Stall + 500 pizzas", "Local store + LinkedIn JFL Gujarat"],
    ["44", "McDonald's (Westlife — west India)", "QSR — youth",
     "Westlife marketing / local restaurant manager",
     "investor.relations@westlife.co.in is IR — route Brand",
     "Nearest McD Ahmedabad GM",
     "Local GM can do coupon + branding faster than Westlife HQ.",
     "Coupons + stall", "Westlife / local McD"],
    ["45", "Burger King India (QSR Brands)", "QSR — student value meals",
     "Local restaurant + brand marketing LinkedIn",
     "Official BK India contact form",
     "Nearest BK Ahmedabad",
     "Value-meal coupons for 22k students. Local GM first.",
     "Coupons / ₹40–1.2L", "Local BK + brand form"],
    ["46", "Haldiram's / Bikano", "National snacks — Gujarat trade",
     "Gujarat distributor + brand marketing",
     "Official Haldiram / Bikano contact pages",
     "Ahmedabad C&F / distributor (ask Kirana wholesale)",
     "Distributor often funds sampling. Faster than Delhi brand office.",
     "₹50k–2L + stock", "Local C&F + official contact"],
    ["47", "Parle Products", "Hide & Seek / Hide&Seek + Monaco youth",
     "West region sales (LinkedIn Parle)",
     "Official parleproducts.com contact",
     "West region office",
     "Pitch Hide & Seek / Melody sampling. Old-school trade will understand IIT fest.",
     "Product + ₹50k–1.5L", "https://www.parleproducts.com"],
    ["48", "ITC (Bingo / Sunfeast / YiPPee)", "FMCG youth SKUs",
     "Gujarat Area Brand / Trade Marketing (LinkedIn)",
     "Official ITC 'Contact us' — ask Foods Division Gujarat",
     "ITC Gujarat branch",
     "Bingo/YiPPee are campus SKUs. Area TM can approve a sampling van.",
     "Product + activation", "ITC Foods Gujarat"],
    ["49", "Dabur (Real / Hajmola / Réal Activ)", "Youth F&B inside Dabur",
     "Brand manager Real/Hajmola (LinkedIn)",
     "Official dabur.com contact — ask Brand Real",
     "Dabur India",
     "Hajmola + Real Activ sampling at food street. Safer than energy if they cap caffeine later.",
     "₹1–3L + stock", "https://www.dabur.com"],
    ["50", "Marico (Saffola / Set Wet / Livon)", "Set Wet / youth grooming",
     "Set Wet brand manager (LinkedIn)",
     "Official marico.com contact",
     "Marico",
     "Set Wet is a cultural-fest classic (fashion show / Pronite). Pitch Panache + Pronite.",
     "₹1–3L + product", "https://marico.com"],
    ["51", "Emami (HE / Zandu / Kesh King youth)", "HE deodorant — fest staple",
     "HE brand / activation agency",
     "Official emamiltd.in contact",
     "Emami",
     "HE historically buys college fashion + music. Pitch Panache.",
     "₹80k–2.5L", "https://www.emamiltd.in"],
    ["52", "Wild Stone / McNROE", "Deo / grooming — campus sampling",
     "Brand activation (LinkedIn McNROE)",
     "Official McNROE / Wild Stone contact",
     "McNROE Consumer Products",
     "Same as HE. Fashion night + sampling. Mid-ticket, high yes-rate vs Unilever.",
     "₹50k–2L + cans", "McNROE official"],
    ["53", "Royal Enfield / Hero / TVS (youth two-wheeler)", "Two-wheeler — IIT boys + display",
     "Ahmedabad dealer Principal + brand campus (LinkedIn)",
     "Dealer first (they fund display bikes)",
     "Gandhinagar / Ahmedabad main dealer",
     "Dealer pays for a bike display + lucky draw. Brand HQ is optional.",
     "Display + ₹50k–2L", "Main dealer + brand campus team"],
    ["54", "Asian Paints / Berger (youth décor / Ace)", "Home + youth décor",
     "Gujarat depot / Ace outdoor",
     "Official contact + depot",
     "Local depot",
     "Only if they want wall/street-art (Aerosol). Otherwise skip.",
     "Contra paint + ₹50k", "Local depot"],
    ["55", "Reliance Retail / Trends / Smart", "Retail — student fashion",
     "Trends store manager + RCPL brand",
     "Store cluster manager (walk-in) + LinkedIn Reliance Retail Marketing",
     "Nearest Trends / Smart Bazaar",
     "Bundle with Campa (same group). Offer fashion-show wardrobe + voucher.",
     "Vouchers + stall", "Reliance Retail cluster"],
]

# Table B: newly launched / re-launched national brands hunting youth marketing NOW
BIG_NEW = [
    ["1", "Campa Energy (RCPL / Reliance)", "Energy drink launched for youth; IPL 2025 debut; Zero Sugar Citrus Kick rolling out",
     "Megha Raturi — CMO, Reliance Consumer Products (public interviews). Ketan Mody — COO RCPL.",
     "LinkedIn: Megha Raturi. Ignore fake 'Campa dealership' WhatsApp/emails (not @ril.com / official RCPL).",
     "IPL + Ram Charan pipeline — they NEED on-ground youth beyond cricket. IITGN cultural is a clean campus story.",
     "Energy Partner / Pronite. Ask for Gujarat sampling van + 2,000 cans.",
     "Highest-priority big pitch this month."],
    ["2", "Campa Cola (relaunch under Reliance)", "Relaunched 2023–25; IPL presenting; still buying share vs Coke/Pepsi",
     "Same RCPL desk as Campa Energy (one meeting).",
     "LinkedIn RCPL Brand / Megha Raturi. Walk-in Reliance Retail marketing if needed.",
     "They already buy cricket; campus is the cheap complement. CHAOS IIMA has used Campa historically as title-type F&B.",
     "Beverage Partner (cola) if Energy is taken by Cloud9/Hustle.",
     "Do Campa Cola + Campa Energy as one RCPL deck."],
    ["3", "Thums Up XForce", "New zero-sugar 'Thunder in a Can' youth SKU (2025); 1L+ pre-bookings story",
     "Coca-Cola India Brand Thums Up + HCCB Gujarat sales",
     "HCCB Ahmedabad sales manager (LinkedIn) — not consumer care.",
     "Built to fight Campa on youth. They will listen to an IIT cultural sampling plan.",
     "Can sampling + Pronite backdrop.",
     "If Campa says no, this is the counter-pitch."],
    ["4", "Coke Zero / Sprite Zero ₹10 packs", "First-time ₹10 diet packs in India to fight Campa (2025)",
     "HCCB Gujarat + Coca-Cola India Sparkling",
     "Same HCCB ASM as XForce",
     "They are in share-war mode. Campus sampling is how ₹10 packs get trial.",
     "Food-street exclusive fizz.",
     "Bundle Sprite Zero with dance/heat, Coke Zero with Pronite."],
    ["5", "Pepsi Black / Sting (via VBL)", "Sting is the mass energy drink students already drink; VBL executes India",
     "Varun Beverages Gujarat Area Sales Manager",
     "Only @varunbeverages.com / @rjcorp.in. HQ +91 124 464 3100 then 'Gujarat sales'.",
     "Sting is the easiest energy yes after Campa/Cloud9 — if you find the ASM, not a broker WhatsApp.",
     "Energy / Sting zone + Pepsi fountain.",
     "Warn organizer: fake Sting dealership scams are everywhere."],
    ["6", "Campa Spinner Sports Drink / Gluco Energy", "RCPL sports-drink line sitting next to Campa Energy",
     "Same Megha Raturi / RCPL brand team",
     "One deck, three SKUs: Cola + Energy + Sports",
     "Sports drink fits dance + sports side-events inside Blithchron.",
     "Hydration/sports if Krispy already took water.",
     "Lets RCPL own more inventory without a second meeting."],
    ["7", "Paper Boat Nata (new chew-cube drink, 2025)", "New SKU; they already did SNITCH store youth activations",
     "Hector Beverages brand / paperboat@hectorbeverages.com",
     "1860 425 4425 + LinkedIn Shubham Meena / Arnab Hazra",
     "New SKU = they need trial. Cultural fest > another retail popup.",
     "Sampling wall + merch.",
     "Safer 'no-energy' option if organizers cap caffeine."],
    ["8", "Soulfull / Tata Soulfull oats (Tata Consumer youth)", "Tata pushing youth breakfast / millet snacks",
     "Route via nidhi.verma@tataconsumer.com → Soulfull brand",
     "Tata Consumer IR/comms is the public named route",
     "New-ish Tata youth brand still buying awareness.",
     "Morning events + artist hospitality.",
     "Slower than Campa, but Tata logo helps the brochure."],
    ["9", "Reliance Independence / Bombay Creamery (RCPL ice cream)", "RCPL ice-cream push alongside Campa",
     "RCPL foods / same Reliance Consumer desk",
     "Do not use random 'Independence FMCG franchise' numbers from LinkedIn farms",
     "If you are already in front of RCPL for Campa, add ice-cream stall.",
     "Ice-cream stall vs Havmor.",
     "Only as a bundle — don't cold-call franchise spam numbers."],
    ["10", "JioHotstar / JioCinema youth (Reliance)", "Streaming wars; youth IPL + campus",
     "Jio Marketing / campus alliances (LinkedIn)",
     "Bundle in the RCPL/Campa meeting",
     "They need Gen-Z beyond cricket ads. Fest livestream / QR trial is the hook.",
     "Digital / QR partner.",
     "One Reliance meeting: Campa + Trends + Jio."],
    ["11", "Maggi / Nestlé youth SKUs (Hot Heads / cup)", "Nestlé periodically pushes spicy youth Maggi",
     "Nestlé India Foods / Gujarat sales (LinkedIn)",
     "Official nestle.in contact + CNF",
     "Cup Maggi sampling is a proven fest mechanic. Ask Gujarat sales, not Vevey.",
     "Night-hunger stall near Pronite.",
     "Product-heavy, cash-light — easy organizer yes."],
    ["12", "Epigamia / Drums Food (if still pushing youth cups)", "Yogurt / protein — student breakfast",
     "Brand partnerships (LinkedIn Epigamia)",
     "Official site contact",
     "Protein + IIT audience is a clean story. Confirm current Gujarat distribution first.",
     "Breakfast sampling.",
     "Only pitch if SKUs are on Ahmedabad shelves."],
    ["13", "Yogabar / RiteBite", "Energy bars — fest + sports",
     "Brand / campus (LinkedIn)",
     "Official yogabars.in / ritebite contact",
     "Bar sampling is cheap and fits 'energy' without a drink fight.",
     "Goodie-bag + stall.",
     "Use if energy-drink slot is already sold."],
    ["14", "Prime Hydration (if / when India distributor is live)", "Global youth drink — only if a real India distributor exists",
     "Official India distributor (verify; ignore Instagram 'Prime dealership')",
     "Do not pay anyone claiming Prime master-franchise on WhatsApp",
     "Only include in the live pitch if you can name a real importer this week.",
     "Hydration if legal stock exists in Gujarat.",
     "SKIP until stock is in Ahmedabad modern trade."],
    ["15", "Slice / Fi / Jupiter (neo-banks still buying students)", "Student banking apps",
     "Campus / growth (LinkedIn)",
     "Official careers/partnerships pages",
     "They buy campuses when raising or launching a student card. Check which one is live in Gujarat.",
     "App-install stall.",
     "Verify the product is still on-mission before you promise the organizer."],
]


def styles():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=18, textColor=NAVY, spaceAfter=6, leading=22,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=13, textColor=BLUE, spaceBefore=10, spaceAfter=6, leading=16,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName="Helvetica",
            fontSize=8.5, leading=11.5, textColor=NAVY, alignment=TA_JUSTIFY, spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"], fontName="Helvetica",
            fontSize=7.5, leading=10, textColor=colors.HexColor("#334155"),
        ),
        "th": ParagraphStyle(
            "th", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=7, leading=9, textColor=colors.white, alignment=TA_CENTER,
        ),
        "td": ParagraphStyle(
            "td", parent=base["BodyText"], fontName="Helvetica",
            fontSize=6.6, leading=8.6, textColor=NAVY, alignment=TA_LEFT,
        ),
        "cap": ParagraphStyle(
            "cap", parent=base["BodyText"], fontName="Helvetica-Oblique",
            fontSize=7.5, textColor=colors.HexColor("#64748b"), spaceBefore=4, spaceAfter=8,
        ),
        "foot": ParagraphStyle(
            "foot", parent=base["BodyText"], fontName="Helvetica",
            fontSize=7, textColor=colors.HexColor("#64748b"), alignment=TA_CENTER,
        ),
    }


def P(text, st):
    return Paragraph(str(text).replace("\n", "<br/>"), st)


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, landscape(A4)[1] - 14 * mm, landscape(A4)[0], 14 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(12 * mm, landscape(A4)[1] - 9 * mm, "SponsorDesk  ·  Blithchron '27 IIT Gandhinagar  ·  Sponsor leads")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(landscape(A4)[0] - 12 * mm, landscape(A4)[1] - 9 * mm, "Public contacts only  ·  29 Oct 2026")
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, landscape(A4)[0], 8 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(12 * mm, 3 * mm, "Not for forwarding as 'verified personal emails'. Named people = public roles. Fake dealership WhatsApps excluded.")
    canvas.drawRightString(landscape(A4)[0] - 12 * mm, 3 * mm, f"Page {doc.page}")
    canvas.restoreState()


def table(data, col_w, header, st):
    rows = [[P(h, st["th"]) for h in header]]
    for row in data:
        rows.append([P(c, st["td"]) for c in row])
    t = Table(rows, colWidths=col_w, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.25, LINE),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
    ]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), SOFT))
    t.setStyle(TableStyle(style_cmds))
    return t


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    st = styles()
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=landscape(A4),
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=18 * mm,
        bottomMargin=12 * mm,
        title="Blithchron '27 — High-conversion sponsor leads",
        author="SponsorDesk",
    )
    story = []
    story.append(P("Blithchron '27 — IIT Gandhinagar Cultural Fest", st["h1"]))
    story.append(P(
        "<b>What this PDF is:</b> 55 brands you can actually pitch this week for Blithchron (energy / F&amp;B / bank / youth lifestyle), "
        "plus 15 newly launched or relaunched national brands (Campa Energy, Thums Up XForce, Sting/VBL, Paper Boat Nata, etc.). "
        "<b>What it is not:</b> course-selling institutes, JEE/NEET coaching, coding bootcamps, or invented personal Gmails of brand managers.",
        st["body"],
    ))
    story.append(P("How we scored (so you don't waste the organizer)", st["h2"]))
    story.append(P(
        "<b>Event:</b> IITGN flagship cultural fest, Palaj, Gandhinagar. ~22,000 students from Ahmedabad / Vadodara / Surat / Gandhinagar. "
        "Pronites, Panache (fashion), Antaragnee, String Theory, Synchronize. Dates TBC, typically Feb–Mar (use 2027 edition). "
        "Organizer named in CRM: <b>Tejomay Meshram — Sponsorship &amp; Partnership Coordinator</b> "
        "(LinkedIn: Tejomay Meshram IIT Gandhinagar). Site: blithchron.iitgn.ac.in.<br/>"
        "<b>Restrictions you gave:</b> energy-drink / supportive brands <b>wanted</b>. Educational brands that sell courses <b>out</b>. "
        "Everything else open.<br/>"
        "<b>History we used:</b> Blithchron '25 publicly thanked <b>Central Bank of India (Title)</b>, <b>Krispy Water (Hydration Partner)</b>, "
        "Renaissance, Interview Buddy. Krispy Water's own site still lists IITGN Blithchron 2025. That is your warmest renewal.<br/>"
        "<b>Why these convert:</b> (1) Gujarat HQ or Gujarat trade (Amul, Balaji, Gopal, Havmor, Vadilal, Krispy). "
        "(2) Named public desk or founder phone. (3) Youth SKU that needs trial, not a locked IPL-only title. "
        "(4) Local QSR/dealer who can say yes without Mumbai brand committee.",
        st["body"],
    ))
    story.append(P("This-week call order (do these first)", st["h2"]))
    story.append(P(
        "<b>1. Krispy Water</b> 99249 64118 / info@krispywater.com — renew hydration.<br/>"
        "<b>2. Campa Energy</b> — LinkedIn Megha Raturi (CMO, RCPL). One deck: Energy + Cola + sports drink. "
        "Do <i>not</i> mail random @campabeverageril.com dealership farms.<br/>"
        "<b>3. Hustle Energy</b> — Sushant Mehta +91 95992 25334 / sushant.mehta@radioheadbrands.com (published trade desk).<br/>"
        "<b>4. Cloud9</b> — info@thecloud9corp.com / 1800 266 9669 + LinkedIn Vibin Thomas.<br/>"
        "<b>5. Amul</b> — gcmmf@amul.coop + retail@amul.coop / 02692-258506 — parlour + sampling.<br/>"
        "<b>6. Balaji + Gopal</b> — Rajkot snack giants, public phones on their sites.<br/>"
        "<b>7. Havmor + Vadilal</b> — both HQ in Ahmedabad; walk-in is possible.<br/>"
        "<b>8. Central Bank</b> — last year's title; zonal office, not a cold national RFP.<br/>"
        "<b>9. La Pino'z + local Domino's/Wow Momo</b> — food street, local owner yes in days.<br/>"
        "<b>10. VBL Gujarat ASM</b> — only real path to Sting/Pepsi. Official domains @rjcorp.in / @varunbeverages.com.",
        st["body"],
    ))
    story.append(P(
        "Table A — 55 high-conversion / reachable pitches (no course-selling education brands). "
        "Ask = suggested package. Ticket = cash or contra you can honestly open with.",
        st["h2"],
    ))
    header_a = ["#", "Brand", "Why this brand", "Right person / desk", "Email (public)", "Phone", "How you close", "Open with", "Source"]
    # landscape usable ~277mm
    col_a = [10*mm, 32*mm, 36*mm, 38*mm, 40*mm, 28*mm, 42*mm, 24*mm, 27*mm]
    story.append(table(HIGH, col_a, header_a, st))
    story.append(P(
        "Sources: official contact pages (Amul, Balaji, Gopal, La Pino'z, Krispy Water, Hustle, Sipora, Souled Store, VBL IR), "
        "company filings (Monster India entity email), public C-suite interviews (Megha Raturi / Ketan Mody — RCPL), "
        "and Gujarat SME inboxes already verified in SponsorDesk. Personal inboxes that are not published were not invented.",
        st["cap"],
    ))

    story.append(PageBreak())
    story.append(P("Table B — Newly launched / relaunched national brands hunting youth marketing", st["h2"]))
    story.append(P(
        "These are the 'Campa and friends' set: brands that spent 2025–26 buying IPL, zero-sugar, energy, or Gen-Z trial. "
        "They have budget — but the <b>real door</b> is a named public marketer or the Gujarat bottler/ASM, not a consumer helpline. "
        "Fake dealership WhatsApp numbers for Campa / Hell / Prime / Sting were deliberately left out.",
        st["body"],
    ))
    header_b = ["#", "Brand / SKU", "Why they are buying NOW", "Decision maker (public)", "How to reach (real)", "Insight", "Ask", "Note"]
    col_b = [10*mm, 38*mm, 42*mm, 42*mm, 42*mm, 42*mm, 32*mm, 29*mm]
    story.append(table(BIG_NEW, col_b, header_b, st))
    story.append(P(
        "Table B sources: ET BrandEquity / Exchange4Media (Campa Energy IPL + Megha Raturi, Ketan Mody); "
        "Business Standard (Coke/Pepsi ₹10 zero-sugar vs Campa); Thums Up XForce launch coverage; "
        "Hector Beverages / Paper Boat public email; VBL official domain warning on varunbeverages.com; "
        "Krispy Water site (Blithchron '25 hydration partner).",
        st["cap"],
    ))

    story.append(P("Rules so you don't burn the organizer", st["h2"]))
    story.append(P(
        "1. <b>Never</b> promise Red Bull / Monster / Campa as confirmed until a written yes. Put Krispy + snacks + QSR in the brochure first.<br/>"
        "2. <b>Energy slot:</b> sell exclusive (Campa Energy <i>or</i> Cloud9 <i>or</i> Hustle <i>or</i> Sting). Two energy brands on one Pronite looks desperate.<br/>"
        "3. <b>No course brands</b> in this book — even if they reply faster. That was your restriction.<br/>"
        "4. For every national brand, the first call is <b>Gujarat trade / ASM / local owner</b>. HQ is the second call.<br/>"
        "5. If a number or email is not in this PDF, we did not have a public source. Don't 'guess' a brand-manager Gmail.<br/>"
        "6. Tejomay Meshram (Blithchron partnerships) should see only the top 12 before you spray 55 emails.<br/>"
        "7. Open line that works: <i>IITGN Blithchron, ~22k students, cultural + Pronite, we already have a hydration history with Krispy — "
        "we are locking one energy + one snack + one QSR this week. Can you take sampling rights?</i>",
        st["body"],
    ))
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return OUT


if __name__ == "__main__":
    path = build()
    print(path)
    print("bytes", path.stat().st_size)
