from datetime import date

CUSTOMERS = [
    ("C001", "Maya Chen", "maya.chen@northline.example", "Northeast", "Boston", date(2024, 3, 12)),
    ("C002", "Andre Wallace", "andre.wallace@northline.example", "West", "Seattle", date(2023, 11, 2)),
    ("C003", "Priya Shah", "priya.shah@northline.example", "Midwest", "Chicago", date(2024, 6, 18)),
    ("C004", "Jonah Ellis", "jonah.ellis@northline.example", "South", "Austin", date(2025, 1, 9)),
    ("C005", "Elena Vasquez", "elena.vasquez@northline.example", "West", "Denver", date(2023, 8, 21)),
    ("C006", "Chris Dalton", "chris.dalton@northline.example", "Northeast", "Portland", date(2024, 4, 30)),
    ("C007", "Amira Hassan", "amira.hassan@northline.example", "Midwest", "Minneapolis", date(2025, 2, 14)),
    ("C008", "Leo Park", "leo.park@northline.example", "West", "Bend", date(2024, 9, 3)),
    ("C009", "Sofia Rossi", "sofia.rossi@northline.example", "Northeast", "New York", date(2023, 5, 17)),
    ("C010", "Ben Okonkwo", "ben.okonkwo@northline.example", "South", "Atlanta", date(2024, 7, 22)),
    ("C011", "Hannah Brooks", "hannah.brooks@northline.example", "Midwest", "Detroit", date(2025, 3, 11)),
    ("C012", "Noah Patel", "noah.patel@northline.example", "West", "San Francisco", date(2024, 12, 1)),
]

# product_id, sku, name, category, unit_cost, list_price
PRODUCTS = [
    ("P001", "TENT-2P", "Ridge 2-Person Tent", "Camping", "62.00", "149.00"),
    ("P002", "BAG-20", "Northline 20 Sleeping Bag", "Camping", "38.00", "89.00"),
    ("P003", "JKT-DN", "Lumen Down Jacket", "Apparel", "74.00", "189.00"),
    ("P004", "BOT-TR", "Switchback Trail Boot", "Footwear", "55.00", "140.00"),
    ("P005", "BTL-1L", "Stainless 1L Bottle", "Accessories", "8.50", "24.00"),
    ("P006", "PCK-40", "Ridgeline 40L Pack", "Packs", "48.00", "120.00"),
    ("P007", "POL-FL", "Fleece Quarter Zip", "Apparel", "22.00", "64.00"),
    ("P008", "STO-CP", "Canister Stove", "Camping", "18.00", "46.00"),
]

# order_id, customer_id, ordered_on, status, channel, [(product_id, quantity)]
ORDERS = [
    ("O001", "C009", date(2026, 8, 3), "fulfilled", "web", [("P003", 1), ("P004", 1)]),
    ("O002", "C002", date(2026, 8, 4), "fulfilled", "web", [("P001", 1), ("P002", 2), ("P008", 1)]),
    ("O003", "C005", date(2026, 8, 6), "fulfilled", "store", [("P006", 1), ("P005", 2)]),
    ("O004", "C001", date(2026, 8, 8), "fulfilled", "web", [("P007", 1)]),
    ("O005", "C009", date(2026, 8, 12), "fulfilled", "web", [("P003", 2)]),
    ("O006", "C003", date(2026, 8, 15), "fulfilled", "store", [("P008", 1), ("P005", 1)]),
    ("O007", "C002", date(2026, 8, 18), "fulfilled", "web", [("P006", 1), ("P001", 1)]),
    ("O008", "C010", date(2026, 8, 20), "fulfilled", "web", [("P004", 1)]),
    ("O009", "C006", date(2026, 8, 22), "fulfilled", "store", [("P007", 2)]),
    ("O010", "C005", date(2026, 8, 25), "fulfilled", "web", [("P003", 1), ("P007", 1)]),
    ("O011", "C012", date(2026, 8, 28), "fulfilled", "web", [("P005", 3)]),
    ("O012", "C009", date(2026, 9, 2), "fulfilled", "web", [("P006", 1), ("P002", 1)]),
    ("O013", "C002", date(2026, 9, 4), "fulfilled", "web", [("P003", 1)]),
    ("O014", "C007", date(2026, 9, 5), "fulfilled", "store", [("P008", 2)]),
    ("O015", "C004", date(2026, 9, 8), "fulfilled", "web", [("P004", 1), ("P005", 1)]),
    ("O016", "C005", date(2026, 9, 10), "fulfilled", "web", [("P001", 1), ("P002", 1), ("P008", 1)]),
    ("O017", "C011", date(2026, 9, 12), "fulfilled", "store", [("P007", 1)]),
    ("O018", "C001", date(2026, 9, 14), "fulfilled", "web", [("P005", 2), ("P008", 1)]),
    ("O019", "C010", date(2026, 9, 16), "fulfilled", "web", [("P006", 1)]),
    ("O020", "C009", date(2026, 9, 18), "fulfilled", "web", [("P004", 1), ("P003", 1)]),
    ("O021", "C003", date(2026, 9, 20), "fulfilled", "store", [("P002", 1)]),
    ("O022", "C006", date(2026, 9, 21), "fulfilled", "web", [("P001", 1)]),
    ("O023", "C008", date(2026, 9, 22), "fulfilled", "web", [("P006", 1), ("P005", 1)]),
    ("O024", "C002", date(2026, 9, 24), "fulfilled", "web", [("P002", 1), ("P008", 2), ("P005", 1)]),
    ("O025", "C012", date(2026, 9, 26), "refunded", "store", [("P007", 1)]),
    ("O026", "C005", date(2026, 9, 28), "fulfilled", "web", [("P004", 1), ("P006", 1)]),
]

# customer_id, segment, preferred_channel, loyalty_points
SEGMENTS = [
    ("C001", "loyal", "web", 180),
    ("C002", "vip", "web", 980),
    ("C003", "loyal", "store", 160),
    ("C004", "standard", "web", 140),
    ("C005", "vip", "web", 910),
    ("C006", "loyal", "web", 250),
    ("C007", "standard", "store", 90),
    ("C008", "standard", "web", 130),
    ("C009", "vip", "web", 1180),
    ("C010", "loyal", "web", 240),
    ("C011", "standard", "store", 70),
    ("C012", "standard", "web", 80),
]

# review_id, customer_id, product_id, rating, title, reviewed_on
REVIEWS = [
    ("R001", "C009", "P003", 5, "Warm down to the trailhead", "2026-09-19"),
    ("R002", "C002", "P001", 4, "Easy pitch in the rain", "2026-08-20"),
    ("R003", "C005", "P006", 5, "Carries a weekend load", "2026-09-12"),
    ("R004", "C006", "P007", 4, "Good layer for camp mornings", "2026-08-30"),
    ("R005", "C010", "P004", 3, "Stiff out of the box", "2026-08-27"),
    ("R006", "C001", "P008", 5, "Boils water fast", "2026-09-15"),
    ("R007", "C003", "P002", 4, "Packs smaller than expected", "2026-09-21"),
    ("R008", "C012", "P005", 5, "Does not leak in a daypack", "2026-08-29"),
]

COMMERCE_SOURCE = "Commerce PostgreSQL"
CRM_SOURCE = "Customer CRM"
CASES_SOURCE = "Service cases"
ADS_SOURCE = "Google Ads (sample)"
ANALYTICS_SOURCE = "Google Analytics (sample)"

# left source, left object, left field, right source, right object, right field, description
MAPPINGS = [
    (
        COMMERCE_SOURCE,
        "customers",
        "customer_id",
        CRM_SOURCE,
        "customer_profiles",
        "customer_id",
        "Retail customers and CRM profiles share customer_id.",
    ),
    (
        COMMERCE_SOURCE,
        "customers",
        "customer_id",
        CASES_SOURCE,
        "service_cases",
        "customer_id",
        "Service cases refer to retail customers by customer_id.",
    ),
    (
        COMMERCE_SOURCE,
        "products",
        "product_id",
        COMMERCE_SOURCE,
        "order_items",
        "product_id",
        "Order lines refer to products by product_id.",
    ),
    (
        COMMERCE_SOURCE,
        "products",
        "product_id",
        CRM_SOURCE,
        "product_reviews",
        "product_id",
        "Reviews refer to products by product_id.",
    ),
    (
        COMMERCE_SOURCE,
        "products",
        "product_id",
        CASES_SOURCE,
        "service_cases",
        "product_id",
        "Service cases refer to products by product_id.",
    ),
    (
        COMMERCE_SOURCE,
        "orders",
        "order_id",
        COMMERCE_SOURCE,
        "order_items",
        "order_id",
        "Order lines belong to orders by order_id.",
    ),
    (
        CRM_SOURCE,
        "customer_profiles",
        "customer_id",
        CRM_SOURCE,
        "product_reviews",
        "customer_id",
        "Reviews belong to CRM profiles by customer_id.",
    ),
]
