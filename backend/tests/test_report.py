import pandas as pd

from app.services.ask import LoadedTable, _chart
from app.services.report import build_report, is_report_question


def _traffic_table() -> LoadedTable:
    frame = pd.DataFrame(
        [
            {"date": "2026-09-14", "channel": "Organic Search", "sessions": 720, "users": 560, "conversions": 25},
            {"date": "2026-09-14", "channel": "Paid Search", "sessions": 520, "users": 400, "conversions": 18},
            {"date": "2026-09-21", "channel": "Organic Search", "sessions": 680, "users": 530, "conversions": 24},
            {"date": "2026-09-21", "channel": "Paid Search", "sessions": 410, "users": 320, "conversions": 14},
        ]
    )
    return LoadedTable(
        sql_name="ga_traffic",
        source_name="Google Analytics (sample)",
        object_name="traffic",
        columns=[
            ("date", "date"),
            ("channel", "text"),
            ("sessions", "bigint"),
            ("users", "bigint"),
            ("conversions", "bigint"),
        ],
        frame=frame,
    )


def test_report_question_is_detected():
    assert is_report_question("Write a weekly marketing report with a pie chart of the mix.")
    assert not is_report_question("Which channel brought the most sessions?")


def test_report_builds_pie_ranking_and_trend():
    report = build_report("Write a weekly marketing report.", [_traffic_table()], ["Google Analytics (sample)"])
    kinds = [section.chart.type for section in report.sections if section.chart]
    assert kinds[:2] == ["pie", "bar"]
    assert "line" in kinds
    mix = report.sections[0].rows
    assert mix[0]["channel"] == "Organic Search"
    assert mix[0]["sessions"] == 1400
    assert "Organic Search" in report.summary


def test_channel_rank_rolls_up_weekly_sessions():
    from app.agent.embeddings import HashEmbedder
    from app.agent.text_to_sql import link_question

    link = link_question("Which channel brought the most sessions?", [_traffic_table()], HashEmbedder())
    assert link.intent == "rank_high"
    assert link.dimension == "channel"
    assert link.measure == "sessions"
    assert "SUM" in (link.sql or "")
    assert 'GROUP BY "channel"' in (link.sql or "")


def test_channel_mix_question_gets_a_pie_chart():
    chart = _chart(
        "Show sessions by channel",
        ["channel", "sessions"],
        [{"channel": "Organic Search", "sessions": 1400}, {"channel": "Paid Search", "sessions": 930}],
    )
    assert chart is not None
    assert chart.type == "pie"
    assert chart.category == "channel"
    assert chart.value == "sessions"
