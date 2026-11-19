"""Everything tunable lives here: states, aliases, queries, keyword rules, outlet lists, thresholds.

Rules are deliberately plain regular expressions so that every keep/drop decision can be traced.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- scope
START_DATE = "2025-01-01"  # news window starts here (IST)

# Focus states get the news pipeline. Aliases are matched on a letters-only key
# (so "Uttar-Pradesh", "UttarPradesh" and "Uttar Pradesh" are the same), except
# abbreviations, which are matched case-sensitively as whole tokens.
FOCUS_STATES: dict[str, dict] = {
    "KA": {
        "name": "Karnataka",
        "names": ["Karnataka", "Karnatak"],
        "abbr": [],
        "cities": ["Bengaluru", "Bangalore", "Mysuru", "Mysore", "Mangaluru", "Mangalore", "Hubballi", "Hubli"],
        "hindi": ["कर्नाटक"],
        "hindi_cities": ["बेंगलुरु", "बेंगलूरु"],
    },
    "TG": {
        "name": "Telangana",
        "names": ["Telangana", "Telengana"],
        "abbr": [],
        "cities": ["Hyderabad", "Warangal", "Cyberabad"],
        "hindi": ["तेलंगाना"],
        "hindi_cities": ["हैदराबाद"],
    },
    "TN": {
        "name": "Tamil Nadu",
        "names": ["Tamil Nadu", "Tamilnadu"],
        "abbr": ["TN", "T.N."],
        "cities": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Trichy"],
        "hindi": ["तमिलनाडु"],
        "hindi_cities": ["चेन्नई"],
    },
    "UP": {
        "name": "Uttar Pradesh",
        "names": ["Uttar Pradesh", "Uttarpradesh"],
        "abbr": ["UP", "U.P."],
        "cities": ["Lucknow", "Noida", "Greater Noida", "Prayagraj", "Varanasi", "Kanpur", "Ghaziabad", "Gorakhpur", "Ayodhya"],
        "hindi": ["उत्तर प्रदेश", "यूपी"],
        "hindi_cities": ["लखनऊ", "नोएडा"],
    },
    "OD": {
        "name": "Odisha",
        "names": ["Odisha", "Orissa"],
        "abbr": [],
        "cities": ["Bhubaneswar", "Cuttack", "Rourkela"],
        "hindi": ["ओडिशा"],
        "hindi_cities": ["भुवनेश्वर"],
    },
}

# Cities that point at out-of-scope states (names of all states/UTs come from jurisdictions.json).
OTHER_STATE_CITIES: dict[str, list[str]] = {
    "MH": ["Mumbai", "Pune", "Nagpur"],
    "WB": ["Kolkata"],
    "GJ": ["Ahmedabad", "Gandhinagar", "Surat", "GIFT City"],
    "KL": ["Thiruvananthapuram", "Kochi", "Kozhikode"],
    "AP": ["Visakhapatnam", "Vizag", "Vijayawada", "Amaravati"],
    "RJ": ["Jaipur"],
    "MP": ["Bhopal", "Indore"],
    "BR": ["Patna"],
    "HR": ["Gurugram", "Gurgaon"],
    "AS": ["Guwahati"],
    "UK": ["Dehradun"],
    "JH": ["Ranchi"],
    "CG": ["Raipur"],
    "GA": ["Panaji"],
    "JK": ["Srinagar"],
    "HP": ["Shimla"],
}
OTHER_STATE_EXTRA_NAMES: dict[str, list[str]] = {
    "JK": ["Jammu and Kashmir", "J&K", "Kashmir"], "AN": ["Andaman"], "WB": ["Bengal"], "AP": ["Andhra"],
    "HP": ["Himachal"], "AR": ["Arunachal"],
}

# Chief Ministers, date-bounded: two focus states changed CM in 2026.
# Used only as a "state government" signal in the filter.
CHIEF_MINISTERS = [
    ("Siddaramaiah", "KA", "2023-05-20", "2026-05-28"),
    ("Shivakumar", "KA", "2026-05-28", None),  # took over after Siddaramaiah resigned (28 May 2026)
    ("Revanth Reddy", "TG", "2023-12-07", None),
    ("Stalin", "TN", "2021-05-07", "2026-05-10"),
    ("Joseph Vijay", "TN", "2026-05-10", None),
    ("Yogi Adityanath", "UP", "2017-03-19", None),
    ("Yogi", "UP", "2017-03-19", None),
    ("Majhi", "OD", "2024-06-12", None),
]

# ---------------------------------------------------------------- collection
QUERY_TEMPLATES = [
    '"{state}" AI policy',
    '"{state}" artificial intelligence government',
    '"{state}" AI MoU',
    '"{state}" AI centre of excellence',
    '"{state}" govt AI',
    '"{state}" AI mission',
]
HINDI_QUERIES = [("UP", '"उत्तर प्रदेश" एआई सरकार')]  # proof of concept
RSS_EN = "https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
RSS_HI = "https://news.google.com/rss/search?q={q}&hl=hi&gl=IN&ceid=IN:hi"
SLICE_SPLIT_AT = 95  # a quarter returning this many items is re-run month by month
SLEEP_SECONDS = 1.2
USER_AGENT = "Mozilla/5.0 (compatible; state-ai-policy-tracker/1.0)"

# ---------------------------------------------------------------- filter
# AI terms. "AI" is case-sensitive so it never matches inside ordinary words.
AI_CASE = re.compile(r"(?<![A-Za-z])(AI|A\.I\.|GenAI)(?![A-Za-z])")
AI_CI = re.compile(
    r"\b(artificial intelligence|machine learning|generative ai|gen ai|deep ?fakes?|chatbots?|large language models?|LLMs?)\b",
    re.I,
)
AI_HINDI = ["एआई", "आर्टिफिशियल इंटेलिजेंस", "कृत्रिम बुद्धिमत्ता", "डीपफेक"]  # substring match: \b fails on Devanagari vowel signs

# Strong state-government signals.
GOV_STRONG = re.compile(
    r"\b(government|govt|state-run|chief minister|minister|cabinet|department|dept|police|collector|"
    r"district administration|assembly|secretariat|KDEM|ELCOT|TNeGA|OCAC|Invest UP|T-AIM)\b",
    re.I,
)
GOV_CM = re.compile(r"(?<![A-Za-z])CM(?![A-Za-z])")  # case-sensitive
GOV_HINDI = ["सरकार", "मुख्यमंत्री", "मंत्री", "विभाग", "पुलिस", "कैबिनेट"]
# A focus state named as the actor ("Karnataka signs ...", "UP to back ...") is a government signal:
# Indian headlines often use the state's name for its government.
STATE_ACTOR_VERBS = (
    r"(govt|government|to|signs?|inks?|launch\w*|unveil\w*|approv\w*|announc\w*|introduc\w*|deploy\w*|sets? up|ties up|"
    r"partners?|plans?|rolls? out|bets?|eyes|wants|seeks|mulls|proposes?|clears?|notif\w*|allocat\w*|earmarks?|begins?|"
    r"starts?|opens?|inaugurat\w*|adopts?|frames?|drafts?|issues?|forms?|constitutes?|creates?|establish\w*|builds?|"
    r"develops?|backs?|invests?|teams up|collaborat\w*|cancels?|scraps?|terminates?|activates?|installs?|taps|uses)"
)
# Weak signals count only when a state is also named in the text.
GOV_WEAK = re.compile(r"\b(policy|policies|mission|MoU|budget|scheme|programme|initiative)\b", re.I)
GOV_WEAK_NOT = re.compile(r"\b(privacy policy|monetary policy|insurance policy|space mission)\b", re.I)

# Central-government actors. Never bare "Centre" (it matches "Centre of Excellence").
CENTRAL = re.compile(
    r"\b(IndiaAI|MeitY|Union government|Central government|Union minister|Union Cabinet|PM Modi|Prime Minister|"
    r"Ashwini Vaishnaw|Centre's)\b|\bthe Centre\b(?! (of|for)\b)"
)

# Private-sector news. Phrases, not single words; a strong government term overrides them.
EXCLUDE = re.compile(
    r"\b(share price|shares (rose|fell|surge|surged|jump|jumped|gain|gained|drop|dropped|slump|rally)|stock market|"
    r"stocks to|Sensex|Nifty|funding round|seed funding|series [abc] funding|raises \$|raised \$|raises rs|raised rs|"
    r"raises ₹|raised ₹|IPO|layoffs?|smartphone|product review|hiring spree)\b",
    re.I,
)

# ---------------------------------------------------------------- dedupe
DEDUPE_DAYS = 3          # articles must be within this many days of a cluster member
CLUSTER_SPAN_DAYS = 7    # a cluster may not span more than this
TOKEN_SET_MIN = 85       # rapidfuzz token_set_ratio when both titles have >= MIN_TOKENS distinctive tokens
RATIO_MIN = 90           # rapidfuzz ratio otherwise
MIN_TOKENS = 3
BORDERLINE_MIN = 70      # pairs scoring from here up to the merge threshold go to the review file
GENERIC_WORDS = set(
    "ai a i artificial intelligence govt government state states minister cm chief says said new to the of in for on with "
    "and a an at by from as is its it be will over into after under up out via amid".split()
)
ORGS = [
    "Microsoft", "Google", "Nvidia", "IBM", "Intel", "AMD", "AWS", "Amazon", "Meta", "OpenAI", "Anthropic", "Infosys",
    "TCS", "Wipro", "HCL", "Tech Mahindra", "Adobe", "Oracle", "Qualcomm", "Cisco", "Salesforce", "Accenture",
    "Capgemini", "Deloitte", "KPMG", "PwC", "IIT", "IISc", "IIIT", "NIT", "Nasscom", "C-DAC", "NIELIT", "Samsung",
    "Reliance", "Jio", "Airtel", "Tata", "Adani", "L&T", "Zoho", "Sarvam", "Krutrim", "Yotta", "Dell", "HP",
    "UNESCO", "UNDP", "World Bank", "Gates Foundation", "Wadhwani",
]

# ---------------------------------------------------------------- classify
CATEGORIES = [
    ("regulation_ethics", r"\b(ethic\w*|guidelines?|framework|regulat\w*|responsible ai|deep ?fakes?|data protection|code of conduct|advisory|governance policy)\b"),
    ("budget_funding", r"\b(budget|allocation|allocates?|allocated|outlay|earmark\w*)\b"),
    ("policy_mission", r"\b(polic(y|ies)|mission|strategy|roadmap|vision document|action plan)\b"),
    ("institution", r"\b(centres? of excellence|centers? of excellence|CoE|task ?force|committee|ai city|labs?|hub|institute|university|cell|council|"
                    r"data cent(re|er)s?|infrastructure|compute|GPUs?|AI park|township|ministry|cabinet berth|portfolio)\b"),
    ("partnership_mou", r"\b(MoUs?|memorandum|partnership|partners with|ties up|tie-up|collaborat\w*|agreements?|pacts?|deals?|contracts?|tenders?|join(s)? hands)\b"),
    ("skilling", r"\b(training|trains?|trained|upskill\w*|reskill\w*|skilling|skills?|course|curriculum|certification|literacy|students|teachers|hackathon|"
                 r"classes|coding|capacity[- ]building)\b"),
    ("governance_deployment", r"\b(health\w*|hospitals?|agri\w*|farmers?|crops?|paddy|police|policing|traffic|e-challans?|education|schools?|revenue|"
                              r"land records|welfare|grievances?|citizen services|e-governance|surveillance|cctv|cameras?|crowd|chatbots?|deploy\w*|"
                              r"courts?|wildlife|poaching|forests?|attendance|service delivery|governance|beneficiar\w*|emergency|dial 112|"
                              r"buses|transport|documents|feedback|public services|verif\w*|devices?)\b"),
]
# Hindi keywords per category, matched as substrings (regex word boundaries fail on Devanagari).
CATEGORIES_HINDI = {
    "regulation_ethics": ["दिशानिर्देश", "नियम", "डीपफेक"],
    "budget_funding": ["बजट"],
    "policy_mission": ["नीति", "मिशन", "रोडमैप"],
    "institution": ["सिटी", "सेंटर", "डेटा सेंटर", "लैब"],
    "partnership_mou": ["एमओयू", "समझौता", "करार"],
    "skilling": ["प्रशिक्षण", "ट्रेनिंग", "प्रज्ञा", "कौशल", "छात्र"],
    "governance_deployment": ["स्वास्थ्य", "किसान", "पुलिस", "शिक्षा"],
}
CATEGORY_LABELS = {
    "regulation_ethics": "Regulation & ethics",
    "budget_funding": "Budget & funding",
    "policy_mission": "Policy & mission",
    "institution": "Institutions & infrastructure",
    "partnership_mou": "Partnership / MoU",
    "skilling": "Skilling",
    "governance_deployment": "AI in governance",
    "other": "Other",
}
SECTORS = [
    ("health", r"\b(health\w*|hospitals?|medical|patients?)\b"),
    ("agriculture", r"\b(agri\w*|farmers?|crops?|paddy)\b"),
    ("policing", r"\b(police|policing|crime|surveillance|cctv|cameras?|traffic|e-challans?)\b"),
    ("environment", r"\b(wildlife|poaching|forests?|sanctuar\w*)\b"),
    ("transport", r"\b(buses|transport|traffic|highways?)\b"),
    ("welfare", r"\b(beneficiar\w*|welfare|pension|ration)\b"),
    ("education", r"\b(education|schools?|students|teachers|universit\w*)\b"),
    ("revenue & welfare", r"\b(revenue|land records|welfare|grievances?|citizen services|e-governance)\b"),
    ("courts", r"\b(courts?|judiciary)\b"),
]
# The stage whose verb appears FIRST in the headline wins, so "signs MoU ... to develop" is
# announced, while "to set up ..., announces CM" is proposed.
STAGES = [
    ("proposed", r"\b(to (launch|set up|setup|roll out|introduce|establish|build|develop|unveil|start|create|host|bring|get|back|install|deploy|frame|draft|formulate|come up with)|will|plans?|planning|proposes?|proposed|mulls?|draft|in talks|considering|set to|likely to|aims? to|soon|urges?|keen to|seeks?|explores?|wants)\b"),
    ("announced", r"\b(announces?|announced|unveils?|unveiled|approves?|approved|nod|clears?|cleared|signs?|signed|inks?|inked|releases?|released|notif(y|ies|ied)|bags|wins|awards?|awarded|forms|formed|constitutes?|appoints?|adopts?|adopted|passes|passed|cancels?|cancelled|scraps?|scrapped|terminates?|terminated)\b"),
    ("implemented", r"\b(launches|launched|inaugurates?|inaugurated|deploys?|deployed|rolls? out|rolled out|operational|begins?|began|goes live|went live|opens?|opened|introduces|introduced|starts|started|implements?|implemented|activates?|activated|installs?|installed|taps|uses|using)\b"),
]
# Dedupe guards: a plan never merges with a decision or delivery; a reversal never merges with the original.
DECISION_VERBS = r"\b(approves?|approved|nod|clears?|cleared|signs?|signed|inks?|inked|notif(y|ies|ied)|passes|passed|adopts?|adopted)\b"
REVERSAL = r"\b(cancel\w*|scrap\w*|terminat\w*|withdraw\w*|revok\w*|backtrack\w*|halt\w*|shelv\w*|puts? on hold)\b"
OFFICIAL_SUFFIXES = (".gov.in", ".nic.in")
MAJOR_OUTLETS = {
    "thehindu.com", "indianexpress.com", "newindianexpress.com", "timesofindia.indiatimes.com",
    "economictimes.indiatimes.com", "hindustantimes.com", "ndtv.com", "deccanherald.com", "deccanchronicle.com",
    "business-standard.com", "livemint.com", "moneycontrol.com", "thenewsminute.com", "telanganatoday.com",
    "indiatoday.in", "theprint.in", "scroll.in", "medianama.com", "odishatv.in", "sambadenglish.com",
    "orissapost.com", "odishabytes.com", "thehansindia.com", "financialexpress.com", "news18.com", "firstpost.com",
    "outlookindia.com", "ptinews.com", "aninews.in", "reuters.com", "thestatesman.com", "tribuneindia.com",
    "dtnext.in", "thehindubusinessline.com", "businesstoday.in", "zeenews.india.com", "indiatvnews.com",
    "amarujala.com", "jagran.com", "bhaskar.com", "livehindustan.com", "navbharattimes.indiatimes.com",
}

# Courts are not the state executive. Flip to include High Court AI guidelines and rulings.
INCLUDE_JUDICIARY = False

# Public repository, used for "report a correction" links on the dashboard. Leave empty to hide them.
REPO_URL = ""
