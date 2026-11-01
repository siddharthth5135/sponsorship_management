"""
Replace the CRM with manually verified leads (public sources only, researched Oct 2026).

Usage:
  python scripts/load_verified_leads.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import clear_all_data, get_conn  # noqa: E402

VERIFIED = "Verified from a public source (Oct 2026)."

EVENTS = [
    {
        "name": "Amalthea '26 — IIT Gandhinagar Technical Summit",
        "city": "Gandhinagar",
        "category": "College tech fest",
        "event_date": "2026-12-05",
        "date_label": "Late 2026 — dates to be announced",
        "planning_stage": "seeking_sponsors",
        "footfall_estimate": 10000,
        "description": "17th edition of IIT Gandhinagar's annual tech summit: EDM night, IICPC hackathon, RoboWars, "
        "Auto & Tech Expo and an industry conclave. Past partners include Boeing, Tata, ITC, Reliance, Adani, DRDO and IBM.",
        "audience": "engineering students and tech professionals from across India",
        "organizer_name": "Amalthea sponsorship team",
        "organizer_email": "amalthea@iitgn.ac.in",
        "organizer_phone": "Akshat Desai +91 63633 20158",
        "contact_role": "Also: Pratham Gupta +91 88497 67337, Shikha Singh +91 99247 41101",
        "website": "https://amalthea.iitgn.ac.in",
        "linkedin_url": "https://www.linkedin.com/company/amalthea-iit-gandhinagar",
        "source_url": "https://www.linkedin.com/posts/amalthea-iit-gandhinagar_call-for-sponsors-amalthea-26-amalthea-activity-7512127182823981056-2-P0",
        "discovery_reason": "Posted a public “Call for Sponsors” on 3 Oct 2026 — actively looking for brands right now.",
    },
    {
        "name": "CHAOS '27 — IIM Ahmedabad Cultural Fest",
        "city": "Ahmedabad",
        "category": "College cultural fest",
        "event_date": "2027-01-15",
        "date_label": "Expected mid-January 2027",
        "planning_stage": "seeking_sponsors",
        "footfall_estimate": 100000,
        "description": "IIM Ahmedabad's flagship cultural festival (2026 was the 31st edition, 16–18 Jan). "
        "Past sponsors: Campa Cola (title), Bank of Baroda, SBI. Seeks FMCG, retail, digital, media, auto, finance and lifestyle brands.",
        "audience": "students from 500+ institutes and young professionals",
        "organizer_name": "CHAOS Corporate Communications team",
        "organizer_email": "chaos-corpcomm@iima.ac.in",
        "organizer_phone": "",
        "contact_role": "Corporate Communications (sponsorship) committee",
        "website": "https://www.linkedin.com/company/chaos-iima",
        "linkedin_url": "https://www.linkedin.com/company/chaos-iima",
        "source_url": "https://www.linkedin.com/posts/chaos-iima_chaos26-iima-partnerships-activity-7394964749500915712-tbRq",
        "discovery_reason": "Publicly invites partnerships every year and lists the sponsor categories it wants. Next edition is in sponsor-signing season now.",
    },
    {
        "name": "MG Vadodara International Marathon 2027",
        "city": "Vadodara",
        "category": "Marathon / sports",
        "event_date": "2027-02-07",
        "date_label": "Sunday, 7 February 2027 (AIMS-confirmed)",
        "planning_stage": "seeking_sponsors",
        "footfall_estimate": 0,
        "description": "Vadodara's international marathon with full, half, 10K and fun-run categories. "
        "Has a dedicated sponsorship inbox, so the team actively takes sponsor enquiries.",
        "audience": "runners, families and fitness enthusiasts from Gujarat and across India",
        "organizer_name": "Vadodara Marathon sponsorship team",
        "organizer_email": "sponsorship@vadodaramarathon.com",
        "organizer_phone": "+91 93775 38392 / +91 99201 42195",
        "contact_role": "Also: Sameer Khera +91 99989 06161; info@vadodaramarathon.com",
        "website": "https://vadodaramarathon.com",
        "linkedin_url": "https://www.linkedin.com/company/vadodara-marathon",
        "source_url": "https://vadodaramarathon.com/Contact_Us",
        "discovery_reason": "Date confirmed by AIMS and a dedicated sponsorship email is published — sponsor packages are open.",
    },
    {
        "name": "TiECON Ahmedabad 2027",
        "city": "Ahmedabad",
        "category": "Startup / business conference",
        "event_date": "2027-02-19",
        "date_label": "Expected February 2027",
        "planning_stage": "planning",
        "footfall_estimate": 0,
        "description": "TiE Ahmedabad's annual entrepreneurship conference (2026 edition: 20–21 Feb) with founders, investors and "
        "business leaders from Gujarat — Gopal Snacks' MD spoke at the 2026 edition.",
        "audience": "founders, investors, CXOs and business owners",
        "organizer_name": "TiE Ahmedabad team",
        "organizer_email": "admin@ahmedabad.tie.org",
        "organizer_phone": "+91 99044 51199",
        "contact_role": "TiE Ahmedabad chapter office",
        "website": "https://tieconahmedabad.org",
        "linkedin_url": "https://www.linkedin.com/company/tie-ahmedabad",
        "source_url": "https://tieconahmedabad.org",
        "discovery_reason": "Annual conference with paid sponsor tiers; the 2027 edition is being planned now.",
    },
    {
        "name": "Ingenium 2027 — Ahmedabad University Tech Fest",
        "city": "Ahmedabad",
        "category": "College tech fest",
        "event_date": "2027-01-30",
        "date_label": "Expected late January – early February 2027",
        "planning_stage": "planning",
        "footfall_estimate": 0,
        "description": "Ahmedabad University's technical festival: a 36-hour hackathon followed by a weekend of "
        "tech competitions and workshops (2026: hackathon 17–18 Jan, events 31 Jan–1 Feb).",
        "audience": "engineering and computer-science students",
        "organizer_name": "Ingenium team",
        "organizer_email": "ingenium@ahduni.edu.in",
        "organizer_phone": "",
        "contact_role": "Student organizing committee",
        "website": "https://techingenium.com",
        "linkedin_url": "https://www.linkedin.com/company/ingenium-ahmedabad-university",
        "source_url": "https://techingenium.com/contact",
        "discovery_reason": "Recurring tech fest with a public contact email; sponsors for the next edition are signed in Nov–Dec.",
    },
    {
        "name": "Blithchron '27 — IIT Gandhinagar Cultural Fest",
        "city": "Gandhinagar",
        "category": "College cultural fest",
        "event_date": "2027-02-26",
        "date_label": "Expected February–March 2027 (to be announced)",
        "planning_stage": "planning",
        "footfall_estimate": 22000,
        "description": "IIT Gandhinagar's annual cultural festival with concerts, dance, drama and art competitions.",
        "audience": "college students from Gujarat and across India",
        "organizer_name": "Tejomay Meshram",
        "organizer_email": "",
        "organizer_phone": "",
        "contact_role": "Sponsorship & Partnership Coordinator — message Tejomay Meshram on LinkedIn, or use the website contact form",
        "website": "https://blithchron.iitgn.ac.in",
        "linkedin_url": "https://www.linkedin.com/search/results/people/?keywords=Tejomay%20Meshram%20IIT%20Gandhinagar",
        "source_url": "https://blithchron.iitgn.ac.in",
        "discovery_reason": "Large cultural fest (22,000+ attendees) with a named sponsorship coordinator.",
    },
    {
        "name": "TEDxAhmedabad University 2027",
        "city": "Ahmedabad",
        "category": "Talk / community event",
        "event_date": "2027-02-13",
        "date_label": "13 February 2027",
        "planning_stage": "planning",
        "footfall_estimate": 0,
        "description": "Licensed TEDx event at the GICT Auditorium, Navrangpura, with talks from founders, researchers and creators.",
        "audience": "students, faculty and young professionals",
        "organizer_name": "Amresh Kumar",
        "organizer_email": "",
        "organizer_phone": "",
        "contact_role": "Licensed organizer — message Amresh Kumar on LinkedIn, or via the TED event page",
        "website": "https://www.ted.com/tedx/events/69112",
        "linkedin_url": "https://www.linkedin.com/search/results/people/?keywords=Amresh%20Kumar%20TEDx%20Ahmedabad%20University",
        "source_url": "https://www.ted.com/tedx/events/69112",
        "discovery_reason": "Registered TEDx event with a confirmed date; TEDx events rely on local sponsors.",
    },
    {
        "name": "UDAAN 2027 — Rashtriya Raksha University Cultural Fest",
        "city": "Gandhinagar",
        "category": "College cultural fest",
        "event_date": "2027-04-09",
        "date_label": "Expected April 2027",
        "planning_stage": "planning",
        "footfall_estimate": 500,
        "description": "RRU Gandhinagar's cultural fest (2026: 9–10 April) with 15+ events and 500+ participants.",
        "audience": "university students",
        "organizer_name": "Eventique Club, RRU",
        "organizer_email": "eventique.club@rru.ac.in",
        "organizer_phone": "+91 84376 10938",
        "contact_role": "Student event club",
        "website": "https://udaan.rru.ac.in",
        "linkedin_url": "https://www.linkedin.com/company/rashtriya-raksha-university",
        "source_url": "https://udaan.rru.ac.in",
        "discovery_reason": "Recurring fest with a public email and phone; small, so a good first deal to practise on.",
    },
]

BRANDS = [
    {
        "name": "Wagh Bakri Tea Group",
        "city": "Ahmedabad",
        "category": "FMCG — packaged tea",
        "goal": "awareness",
        "description": "India's third-largest packaged tea company, headquartered in Ahmedabad; runs tea lounges and sponsors local events.",
        "target_categories": "College cultural fest, Marathon / sports, Startup / business conference, Talk / community event",
        "contact_name": "",
        "contact_email": "feedback@waghbakritea.com",
        "contact_phone": "+91 79 2640 9631",
        "contact_role": "General inbox — AGM Marketing is Ashav Jadawala (find on LinkedIn)",
        "website": "https://www.waghbakritea.com",
        "linkedin_url": "https://www.linkedin.com/company/wagh-bakri-tea",
        "source_url": "https://www.waghbakritea.com/contact-us/global-headquarters",
    },
    {
        "name": "Vadilal Industries",
        "city": "Ahmedabad",
        "category": "FMCG — ice cream & frozen foods",
        "goal": "sampling",
        "description": "Ahmedabad-based ice cream and frozen foods maker; a natural fit for sampling at fests and runs.",
        "target_categories": "College cultural fest, Marathon / sports, Talk / community event",
        "contact_name": "",
        "contact_email": "info@vadilalgroup.com",
        "contact_phone": "079 4808 1200",
        "contact_role": "Corporate inbox",
        "website": "https://www.vadilalgroup.com",
        "linkedin_url": "https://www.linkedin.com/company/vadilal-industries-limited",
        "source_url": "https://www.vadilalgroup.com",
    },
    {
        "name": "Havmor Ice Cream (Lotte)",
        "city": "Ahmedabad",
        "category": "FMCG — ice cream",
        "goal": "sampling",
        "description": "Ahmedabad ice cream brand owned by Lotte; strong presence across Gujarat parlours and campuses.",
        "target_categories": "College cultural fest, Talk / community event, Marathon / sports",
        "contact_name": "",
        "contact_email": "havmor@havmor.com",
        "contact_phone": "079 4020 9000",
        "contact_role": "Corporate inbox",
        "website": "https://www.havmor.com",
        "linkedin_url": "https://www.linkedin.com/company/havmor-ice-cream",
        "source_url": "https://www.havmor.com",
    },
    {
        "name": "Rasna Pvt Ltd",
        "city": "Ahmedabad",
        "category": "FMCG — instant drinks",
        "goal": "sampling",
        "description": "Ahmedabad-based maker of Rasna instant drink concentrates; ideal for hydration counters at runs and fests.",
        "target_categories": "Marathon / sports, College cultural fest, Talk / community event",
        "contact_name": "",
        "contact_email": "pak@rasnainternational.com",
        "contact_phone": "+91 79 2640 3338",
        "contact_role": "Listed for “strategic enquiries / collaborations”",
        "website": "https://www.rasnainternational.com",
        "linkedin_url": "https://www.linkedin.com/company/rasna",
        "source_url": "https://www.rasnainternational.com",
    },
    {
        "name": "Gopal Snacks",
        "city": "Rajkot",
        "category": "FMCG — namkeen & snacks",
        "goal": "sampling",
        "description": "Listed Rajkot snacks company (namkeen, gathiya, wafers); its MD spoke at TiECON Ahmedabad 2026.",
        "target_categories": "College cultural fest, Talk / community event, Marathon / sports, Startup / business conference",
        "contact_name": "",
        "contact_email": "inquiries@gopalsnacks.com",
        "contact_phone": "02827 297060",
        "contact_role": "Corporate inbox (also info@gopalsnacks.com)",
        "website": "https://www.gopalsnacks.com",
        "linkedin_url": "https://www.linkedin.com/company/gopal-snacks",
        "source_url": "https://www.gopalsnacks.com",
    },
    {
        "name": "Zydus Wellness (Glucon-D)",
        "city": "Ahmedabad",
        "category": "FMCG — health & energy drinks",
        "goal": "sampling",
        "description": "Ahmedabad-based owner of Glucon-D, Complan and Sugar Free; Glucon-D is a classic energy partner for runs and hackathons.",
        "target_categories": "Marathon / sports, College tech fest",
        "contact_name": "",
        "contact_email": "info@zyduswellness.com",
        "contact_phone": "079 4804 0000",
        "contact_role": "Corporate inbox",
        "website": "https://www.zyduswellness.com",
        "linkedin_url": "https://www.linkedin.com/company/zydus-wellness",
        "source_url": "https://www.zyduswellness.com",
    },
    {
        "name": "Unstop",
        "city": "Pan-India",
        "category": "Student platform — competitions & hiring",
        "goal": "leads",
        "description": "Student engagement and hiring platform with 3 crore+ users; partners with college fests to host competitions and drive sign-ups.",
        "target_categories": "College tech fest, College cultural fest, Startup / business conference",
        "contact_name": "",
        "contact_email": "partner@unstop.com",
        "contact_phone": "+91 93117 77388",
        "contact_role": "Partnerships inbox (sales@unstop.com for paid plans)",
        "website": "https://unstop.com",
        "linkedin_url": "https://www.linkedin.com/company/unstop",
        "source_url": "https://unstop.com",
    },
    {
        "name": "Internshala",
        "city": "Pan-India",
        "category": "Student platform — internships & training",
        "goal": "leads",
        "description": "India's largest internship and online-training platform; publicly lists an email specifically for college fest sponsorships.",
        "target_categories": "College tech fest, College cultural fest",
        "contact_name": "",
        "contact_email": "pr@internshala.com",
        "contact_phone": "",
        "contact_role": "Official contact for fest sponsorships (partnership@internshala.com for other tie-ups)",
        "website": "https://internshala.com",
        "linkedin_url": "https://www.linkedin.com/company/internshala",
        "source_url": "https://internshala.com",
    },
]


def main():
    clear_all_data()
    with get_conn() as conn:
        for e in EVENTS:
            cols = list(e.keys()) + ["notes"]
            vals = list(e.values()) + [VERIFIED]
            conn.execute(
                f"INSERT INTO events ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals
            )
        for b in BRANDS:
            cols = list(b.keys()) + ["discovery_reason", "notes"]
            vals = list(b.values()) + [
                f"Gujarat-relevant brand whose audience matches: {b['target_categories']}.",
                VERIFIED,
            ]
            conn.execute(
                f"INSERT INTO brands ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals
            )
    print(f"Loaded {len(EVENTS)} verified events and {len(BRANDS)} verified brands.")


if __name__ == "__main__":
    main()
