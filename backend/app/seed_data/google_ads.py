from datetime import date

CUSTOMER_ID = "1111111111"
CUSTOMER_NAME = "Northline Outfitters"
SAMPLE_AS_OF = date(2026, 10, 10)

CAMPAIGNS = [
    ("G001", "Summer Trail Push", "SEARCH"),
    ("G002", "Ridge Apparel", "SHOPPING"),
    ("G003", "Trail Boot Launch", "SEARCH"),
    ("G004", "Weekend Pack Promo", "DISPLAY"),
]

# week_start, campaign_id, impressions, clicks, cost_dollars, conversions, conversion_value
WEEKLY_STATS = [
    (date(2026, 8, 3), "G001", 8200, 210, 420.00, 9, 980.00),
    (date(2026, 8, 3), "G002", 5400, 130, 310.00, 6, 720.00),
    (date(2026, 8, 3), "G003", 4100, 95, 260.00, 4, 510.00),
    (date(2026, 8, 3), "G004", 6900, 70, 180.00, 2, 190.00),
    (date(2026, 8, 10), "G001", 8600, 230, 450.00, 10, 1040.00),
    (date(2026, 8, 10), "G002", 5100, 120, 295.00, 5, 640.00),
    (date(2026, 8, 10), "G003", 3900, 88, 240.00, 3, 420.00),
    (date(2026, 8, 10), "G004", 7200, 74, 188.00, 2, 175.00),
    (date(2026, 8, 17), "G001", 9100, 250, 480.00, 11, 1180.00),
    (date(2026, 8, 17), "G002", 5600, 140, 330.00, 7, 790.00),
    (date(2026, 8, 17), "G003", 4300, 102, 275.00, 5, 560.00),
    (date(2026, 8, 17), "G004", 7000, 68, 170.00, 1, 120.00),
    (date(2026, 8, 24), "G001", 8800, 240, 465.00, 10, 1100.00),
    (date(2026, 8, 24), "G002", 5300, 125, 300.00, 6, 700.00),
    (date(2026, 8, 24), "G003", 4000, 90, 250.00, 4, 490.00),
    (date(2026, 8, 24), "G004", 6800, 66, 165.00, 2, 160.00),
    (date(2026, 8, 31), "G001", 9400, 120, 390.00, 8, 860.00),
    (date(2026, 8, 31), "G002", 5000, 80, 250.00, 4, 480.00),
    (date(2026, 8, 31), "G003", 3700, 60, 210.00, 3, 390.00),
    (date(2026, 8, 31), "G004", 6400, 40, 140.00, 1, 95.00),
    (date(2026, 9, 7), "G001", 10200, 140, 430.00, 9, 970.00),
    (date(2026, 9, 7), "G002", 5800, 90, 275.00, 5, 610.00),
    (date(2026, 9, 7), "G003", 4200, 55, 220.00, 3, 410.00),
    (date(2026, 9, 7), "G004", 7100, 35, 150.00, 1, 110.00),
    (date(2026, 9, 14), "G001", 11000, 160, 470.00, 11, 1210.00),
    (date(2026, 9, 14), "G002", 6100, 70, 260.00, 4, 540.00),
    (date(2026, 9, 14), "G003", 4500, 70, 235.00, 4, 470.00),
    (date(2026, 9, 14), "G004", 7300, 45, 155.00, 2, 140.00),
    (date(2026, 9, 21), "G001", 9800, 110, 400.00, 8, 890.00),
    (date(2026, 9, 21), "G002", 5400, 85, 255.00, 5, 580.00),
    (date(2026, 9, 21), "G003", 4100, 50, 205.00, 2, 310.00),
    (date(2026, 9, 21), "G004", 6600, 30, 130.00, 1, 90.00),
]


def campaign_rows() -> list[dict]:
    names = {campaign_id: (name, channel) for campaign_id, name, channel in CAMPAIGNS}
    rows = []
    for week_start, campaign_id, impressions, clicks, cost, conversions, value in WEEKLY_STATS:
        name, channel = names[campaign_id]
        rows.append(
            {
                "campaign_id": campaign_id,
                "campaign_name": name,
                "campaign_type": channel,
                "date": week_start.isoformat(),
                "impressions": impressions,
                "clicks": clicks,
                "cost": f"{cost:.2f}",
                "cost_micros": int(round(cost * 1_000_000)),
                "conversions": conversions,
                "conversion_value": f"{value:.2f}",
            }
        )
    return rows
