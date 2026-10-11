import re
from datetime import date

from app.agent.llm import chat_json, model_name
from app.agent.profile import good_dimension, good_measure, humanize, kind_of, time_column

WRITER_SYSTEM = """You write answers for Meridian, a data assistant used by non-technical people.
You receive the question, the planner's assumptions, and the result rows of one or more queries.
Use only names and numbers that appear in that JSON. Do not invent metrics, dates, causes, or recommendations.
Write numbers with thousands separators and no trailing ".0" (3,246 or 1,438.50); show ratios below 1 as percentages (0.052 as 5.2%).
Lead with the direct answer. Mention an assumption only if it changes how the number should be read.
Do not speculate about why, and do not comment on rows that were not returned.
If the rows are empty, say plainly that no matching rows were found.
Return JSON: {"answer": "1 to 3 plain sentences, no markdown", "points": ["0 to 4 short facts taken from the rows"]}"""


def pretty(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        if abs(value) < 1:
            return f"{value:.4f}".rstrip("0")
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    text = str(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        parsed = date.fromisoformat(text)
        return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
    return text


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def draft_answer(sections: list[dict], assumptions: list[str]) -> tuple[str, list[str]]:
    if not sections:
        return "No query could be run for this question.", []
    first = sections[0]
    answer, points = _describe_result(first)
    for extra in sections[1:3]:
        line, _ = _describe_result(extra)
        points.append(f"{extra['title']}: {line}")
    if assumptions:
        answer += " " + " ".join(item.rstrip(".") + "." for item in assumptions[:2])
    return answer, points[:5]


def _describe_result(section: dict) -> tuple[str, list[str]]:
    rows, columns = section["rows"], section["columns"]
    if not rows:
        return "No matching rows were found.", []
    if len(rows) == 1 and len(columns) == 1:
        return f"{humanize(columns[0]).capitalize()}: {pretty(rows[0][columns[0]])}.", []
    labels = [name for name in columns if not is_number(rows[0].get(name))]
    label = next((name for name in labels if not name.lower().endswith("_id")), labels[0] if labels else None)
    value = next((name for name in columns if name != label and is_number(rows[0].get(name))), None)
    if len(rows) == 1:
        facts = ", ".join(f"{humanize(name)} {pretty(rows[0][name])}" for name in columns[:6])
        return f"One row matched: {facts}.", []
    if label and value:
        numbers = [row.get(value) for row in rows if is_number(row.get(value))]
        points = [f"{pretty(row[label])}: {pretty(row[value])}" for row in rows[:4]]
        if numbers == sorted(numbers, reverse=True):
            answer = f"{pretty(rows[0][label])} leads with {pretty(rows[0][value])} {humanize(value)}"
            answer += f", followed by {pretty(rows[1][label])} ({pretty(rows[1][value])}). {len(rows)} rows returned."
        else:
            answer = f"{len(rows)} rows returned, with {humanize(value)} for each {humanize(label)}."
        return answer, points
    return f"{len(rows)} rows returned{' (more were available)' if section.get('truncated') else ''}.", []


def polish(question: str, assumptions: list[str], sections: list[dict], draft: str, points: list[str]) -> tuple[str, list[str], str | None]:
    if not sections:
        return draft, points, None
    data = chat_json(
        WRITER_SYSTEM,
        {
            "question": question,
            "assumptions": assumptions,
            "results": [
                {"title": item["title"], "columns": item["columns"], "rows": item["rows"][:30]}
                for item in sections
            ],
        },
    )
    if not data or not str(data.get("answer") or "").strip():
        return draft, points, None
    text = str(data["answer"]).strip()
    new_points = [str(item).strip() for item in (data.get("points") or []) if str(item).strip()][:4]
    allowed = _allowed_values(sections, assumptions, question)
    if any(value not in allowed for value in _values(" ".join([text, *new_points]))):
        return draft, points, None
    return text, new_points, model_name()


NUMBER = re.compile(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?")


def _values(text: str) -> set[float]:
    found = set()
    for match in NUMBER.findall(text):
        try:
            found.add(round(float(match.replace(",", "")), 2))
        except ValueError:
            continue
    return found


def _allowed_values(sections: list[dict], assumptions: list[str], question: str) -> set[float]:
    raw: set[float] = set(_values(question)) | _values(" ".join(assumptions))
    raw |= set(range(0, 11))
    for section in sections:
        raw |= _values(section["title"])
        raw |= set(range(0, len(section["rows"]) + 1))
        for row in section["rows"]:
            for value in row.values():
                if is_number(value):
                    raw.add(float(value))
                    if abs(value) < 1:
                        raw.add(float(value) * 100)
                elif value is not None:
                    raw |= _values(str(value))
        numeric = [name for name in section["columns"] if section["rows"] and is_number(section["rows"][0].get(name))]
        for name in numeric:
            values = [float(row[name]) for row in section["rows"] if is_number(row.get(name))]
            total = sum(values)
            raw.add(total)
            if total:
                raw |= {item / total * 100 for item in values}
            if values:
                raw.add(total / len(values))
            for left in values:
                for right in values[:10]:
                    raw.add(abs(left - right))
    allowed: set[float] = set()
    for value in raw:
        for digits in (0, 1, 2):
            allowed.add(round(value, digits))
    return allowed


def describe(profiles: list[dict]) -> tuple[str, list[str]]:
    if not profiles:
        return "No tables were loaded from the selected sources.", []
    sources = sorted({profile["source"] for profile in profiles})
    total = sum(profile["rows"] for profile in profiles)
    answer = (
        f"{', '.join(sources)} {'has' if len(sources) == 1 else 'have'} {len(profiles)} "
        f"table{'s' if len(profiles) != 1 else ''} with {total:,} rows loaded."
    )
    points = [_table_line(profile) for profile in profiles[:6]]
    return answer, points


def _table_line(profile: dict) -> str:
    parts = [f"{humanize(profile['object']).capitalize()} ({profile['rows']:,} rows)"]
    when = time_column(profile)
    if when and when.get("min"):
        parts.append(f"from {pretty(when['min'])} to {pretty(when['max'])}")
    numbers = [humanize(column["name"]) for column in profile["columns"] if kind_of(column) == "number" and not column["name"].lower().endswith("_id")]
    if numbers:
        parts.append("measures " + ", ".join(numbers[:4]))
    dimension = good_dimension(profile)
    if dimension and dimension.get("values"):
        parts.append(f"split by {humanize(dimension['name'])} ({', '.join(dimension['values'][:4])})")
    return "; ".join(parts) + "."


def starter_questions(profiles: list[dict], links: list) -> list[str]:
    questions: list[str] = []
    for profile in sorted(profiles, key=lambda item: item["rows"], reverse=True):
        dimension, measure, when = good_dimension(profile), good_measure(profile), time_column(profile)
        thing = humanize(profile["object"])
        if dimension and measure:
            questions.append(f"Which {humanize(dimension['name'])} has the highest total {humanize(measure['name'])} in {thing}?")
        if measure and when:
            questions.append(f"How did {humanize(measure['name'])} change over time in {thing}?")
        if len(questions) >= 4:
            break
    if links:
        link = links[0]
        questions.append(
            f"Combine {humanize(link.left_table.split('_', 1)[-1])} with {humanize(link.right_table.split('_', 1)[-1])} and show the top 5."
        )
    questions.append("What is in this data?")
    seen: list[str] = []
    for question in questions:
        if question not in seen:
            seen.append(question)
    return seen[:6]
