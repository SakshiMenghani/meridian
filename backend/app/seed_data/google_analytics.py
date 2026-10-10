from datetime import date

PROPERTY_ID = "123456789"
PROPERTY_NAME = "Northline Outfitters site"

WEEKS = [
    date(2026, 8, 3),
    date(2026, 8, 10),
    date(2026, 8, 17),
    date(2026, 8, 24),
    date(2026, 8, 31),
    date(2026, 9, 7),
    date(2026, 9, 14),
    date(2026, 9, 21),
]

# channel, source, medium, weekly sessions, users, conversions
CHANNELS = [
    ("Paid Search", "google", "cpc", [420, 460, 510, 490, 380, 440, 520, 410]),
    ("Organic Search", "google", "organic", [610, 640, 670, 655, 600, 690, 720, 680]),
    ("Direct", "(direct)", "(none)", [280, 270, 300, 290, 250, 310, 330, 300]),
    ("Email", "newsletter", "email", [90, 85, 120, 95, 70, 110, 140, 100]),
    ("Social", "instagram", "social", [150, 170, 160, 155, 130, 180, 210, 175]),
]

LANDING = [
    ("/tents/ridge-2p", [180, 190, 210, 200, 160, 220, 240, 200]),
    ("/boots/switchback", [140, 150, 155, 148, 120, 160, 175, 150]),
    ("/packs/ridgeline-40", [95, 100, 110, 105, 90, 120, 130, 115]),
    ("/apparel/lumen-down", [210, 220, 250, 230, 180, 260, 280, 240]),
]


def traffic_rows() -> list[dict]:
    rows = []
    for channel, source, medium, sessions in CHANNELS:
        for week, session_count in zip(WEEKS, sessions, strict=True):
            users = int(round(session_count * 0.78))
            conversions = max(1, int(round(session_count * 0.035)))
            rows.append(
                {
                    "date": week.isoformat(),
                    "channel": channel,
                    "source": source,
                    "medium": medium,
                    "sessions": session_count,
                    "users": users,
                    "conversions": conversions,
                }
            )
    return rows


def landing_rows() -> list[dict]:
    rows = []
    for path, sessions in LANDING:
        for week, session_count in zip(WEEKS, sessions, strict=True):
            rows.append(
                {
                    "date": week.isoformat(),
                    "landing_page": path,
                    "sessions": session_count,
                    "users": int(round(session_count * 0.8)),
                }
            )
    return rows
