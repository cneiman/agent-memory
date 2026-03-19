#!/usr/bin/env python3
"""
Temporal query parser for time-aware memory search.

Detects and resolves natural language time references in search queries,
returning cleaned queries + ISO date boundaries for SQL WHERE clauses.

Uses only stdlib (datetime) — no dateutil dependency.

Usage:
    from temporal import parse_temporal

    result = parse_temporal("what did we discuss last Tuesday?")
    # {
    #     'cleaned_query': 'what did we discuss',
    #     'after': '2026-03-10',
    #     'before': '2026-03-11',
    #     'temporal_expr': 'last Tuesday'
    # }
"""

import calendar
import re
from datetime import datetime, timedelta
from typing import Optional


# Day name → weekday number (Monday=0, Sunday=6)
DAY_NAMES = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
    'mon': 0, 'tue': 1, 'tues': 1, 'wed': 2, 'thu': 3, 'thur': 3, 'thurs': 3,
    'fri': 4, 'sat': 5, 'sun': 6,
}

MONTH_NAMES = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9,
    'oct': 10, 'nov': 11, 'dec': 12,
}

NUMBER_WORDS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12,
}

# Build regex alternations
_day_names_pattern = '|'.join(sorted(DAY_NAMES.keys(), key=len, reverse=True))
_month_names_pattern = '|'.join(sorted(MONTH_NAMES.keys(), key=len, reverse=True))
_number_words_pattern = '|'.join(sorted(NUMBER_WORDS.keys(), key=len, reverse=True))


def _now() -> datetime:
    """Get current datetime. Separate function for test mocking."""
    return datetime.now()


def _last_weekday(target_weekday: int, ref: datetime) -> datetime:
    """Find the most recent past occurrence of a weekday (0=Mon, 6=Sun)."""
    current_weekday = ref.weekday()
    days_back = (current_weekday - target_weekday) % 7
    if days_back == 0:
        days_back = 7  # "last Tuesday" when today IS Tuesday means 7 days ago
    return ref - timedelta(days=days_back)


def _parse_month_day(text: str, ref: datetime) -> Optional[datetime]:
    """Parse 'March 10', 'Mar 10', 'March 10th', etc. Returns date or None."""
    # Match month name + optional day
    m = re.match(
        rf'({_month_names_pattern})\s+(\d{{1,2}})(?:st|nd|rd|th)?',
        text.strip(), re.IGNORECASE
    )
    if m:
        month = MONTH_NAMES[m.group(1).lower()]
        day = int(m.group(2))
        year = ref.year
        # If the date is in the future, use previous year
        try:
            result = datetime(year, month, day)
            if result.date() > ref.date():
                result = datetime(year - 1, month, day)
            return result
        except ValueError:
            return None

    # Just month name (no day) → "before February" means before Feb 1
    m = re.match(rf'({_month_names_pattern})$', text.strip(), re.IGNORECASE)
    if m:
        month = MONTH_NAMES[m.group(1).lower()]
        year = ref.year
        result = datetime(year, month, 1)
        if result.date() > ref.date():
            result = datetime(year - 1, month, 1)
        return result

    # ISO date: 2026-03-10
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', text.strip())
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    return None


def _parse_number(text: str) -> Optional[int]:
    """Parse a number from text — digit or word."""
    text = text.strip().lower()
    if text.isdigit():
        return int(text)
    return NUMBER_WORDS.get(text)


def parse_temporal(query: str, reference_time: datetime = None) -> dict:
    """
    Parse temporal expressions from a natural language query.

    Returns:
        {
            'cleaned_query': str,   # query with time expression removed
            'after': str | None,    # ISO date string (YYYY-MM-DD)
            'before': str | None,   # ISO date string (YYYY-MM-DD)
            'temporal_expr': str | None  # the original time expression found
        }
    """
    ref = reference_time or _now()
    today = ref.replace(hour=0, minute=0, second=0, microsecond=0)

    result = {
        'cleaned_query': query.strip(),
        'after': None,
        'before': None,
        'temporal_expr': None,
    }

    # Try each pattern in priority order (most specific first)
    # Each pattern function returns (after_date, before_date, matched_text) or None

    patterns = [
        _match_between,
        _match_since_before,
        _match_yesterday_today,
        _match_n_units_ago,
        _match_last_named_day,
        _match_this_last_period,
    ]

    for pattern_fn in patterns:
        match = pattern_fn(query, ref, today)
        if match:
            after_date, before_date, matched_text = match
            result['after'] = after_date.strftime('%Y-%m-%d') if after_date else None
            result['before'] = before_date.strftime('%Y-%m-%d') if before_date else None
            result['temporal_expr'] = matched_text.strip()
            # Remove the temporal expression from the query
            result['cleaned_query'] = _clean_query(query, matched_text)
            break

    return result


def _clean_query(query: str, temporal_expr: str) -> str:
    """Remove the temporal expression from the query and clean up."""
    # Escape special regex chars in the expression
    escaped = re.escape(temporal_expr)
    # Remove the expression (case-insensitive)
    cleaned = re.sub(escaped, '', query, count=1, flags=re.IGNORECASE).strip()
    # Clean up leftover punctuation/connectors
    cleaned = re.sub(r'\s*\?\s*$', '', cleaned)  # trailing ?
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)    # double spaces
    # Remove trailing prepositions/connectors left behind
    cleaned = re.sub(r'\s+(from|since|before|after|on|in|during)\s*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(' ,;')
    return cleaned


# ============ Pattern Matchers ============
# Each returns (after_date, before_date, matched_text) or None


def _match_between(query: str, ref: datetime, today: datetime):
    """Match 'between X and Y'."""
    pattern = re.compile(
        r'between\s+(.+?)\s+and\s+(.+)',
        re.IGNORECASE
    )
    m = pattern.search(query)
    if not m:
        return None

    start_text = m.group(1).strip()
    end_text = m.group(2).strip().rstrip('?.! ')

    start_date = _parse_month_day(start_text, ref)
    end_date = _parse_month_day(end_text, ref)

    if start_date and end_date:
        matched = m.group(0).rstrip('?.! ')
        return (start_date, end_date + timedelta(days=1), matched)

    return None


def _match_since_before(query: str, ref: datetime, today: datetime):
    """Match 'since X', 'before X', 'after X'."""
    # "since last week", "since March 10", "since yesterday"
    since_pattern = re.compile(
        r'(?:since|after)\s+(.+?)(?:\s*[?.!]?\s*$)',
        re.IGNORECASE
    )
    before_pattern = re.compile(
        r'before\s+(.+?)(?:\s*[?.!]?\s*$)',
        re.IGNORECASE
    )

    m_since = since_pattern.search(query)
    m_before = before_pattern.search(query)

    after_date = None
    before_date = None
    matched_text = None

    if m_since:
        date_text = m_since.group(1).strip().rstrip('?. ')
        resolved = _resolve_date_expr(date_text, ref, today)
        if resolved:
            after_date = resolved
            matched_text = m_since.group(0).strip()

    if m_before:
        date_text = m_before.group(1).strip().rstrip('?. ')
        resolved = _resolve_date_expr(date_text, ref, today)
        if resolved:
            before_date = resolved
            if matched_text:
                matched_text = matched_text + ' ' + m_before.group(0).strip()
            else:
                matched_text = m_before.group(0).strip()

    if after_date or before_date:
        return (after_date, before_date, matched_text)

    return None


def _match_yesterday_today(query: str, ref: datetime, today: datetime):
    """Match 'yesterday', 'today'."""
    m = re.search(r'\byesterday\b', query, re.IGNORECASE)
    if m:
        yesterday = today - timedelta(days=1)
        return (yesterday, today, 'yesterday')

    m = re.search(r'\btoday\b', query, re.IGNORECASE)
    if m:
        tomorrow = today + timedelta(days=1)
        return (today, tomorrow, 'today')

    return None


def _match_n_units_ago(query: str, ref: datetime, today: datetime):
    """Match 'N days/weeks/months ago'."""
    pattern = re.compile(
        rf'(\d+|{_number_words_pattern})\s+(day|days|week|weeks|month|months)\s+ago',
        re.IGNORECASE
    )
    m = pattern.search(query)
    if not m:
        return None

    n = _parse_number(m.group(1))
    if n is None:
        return None

    unit = m.group(2).lower().rstrip('s')  # normalize: days→day, weeks→week

    if unit == 'day':
        target = today - timedelta(days=n)
        return (target, target + timedelta(days=1), m.group(0))
    elif unit == 'week':
        # "2 weeks ago" → the week starting 2 weeks back
        target_start = today - timedelta(weeks=n)
        # Start of that week (Monday)
        target_start = target_start - timedelta(days=target_start.weekday())
        target_end = target_start + timedelta(days=7)
        return (target_start, target_end, m.group(0))
    elif unit == 'month':
        # Go back N months
        month = ref.month - n
        year = ref.year
        while month <= 0:
            month += 12
            year -= 1
        last_day = calendar.monthrange(year, month)[1]
        target_start = datetime(year, month, 1)
        target_end = datetime(year, month, last_day) + timedelta(days=1)
        return (target_start, target_end, m.group(0))

    return None


def _match_last_named_day(query: str, ref: datetime, today: datetime):
    """Match 'last Tuesday', 'on Monday', etc."""
    pattern = re.compile(
        rf'\blast\s+({_day_names_pattern})\b',
        re.IGNORECASE
    )
    m = pattern.search(query)
    if m:
        day_name = m.group(1).lower()
        target_weekday = DAY_NAMES[day_name]
        target = _last_weekday(target_weekday, today)
        return (target, target + timedelta(days=1), m.group(0))

    # Also match "on Tuesday" (implies most recent)
    pattern2 = re.compile(
        rf'\bon\s+({_day_names_pattern})\b',
        re.IGNORECASE
    )
    m2 = pattern2.search(query)
    if m2:
        day_name = m2.group(1).lower()
        target_weekday = DAY_NAMES[day_name]
        target = _last_weekday(target_weekday, today)
        return (target, target + timedelta(days=1), m2.group(0))

    return None


def _match_this_last_period(query: str, ref: datetime, today: datetime):
    """Match 'this week', 'last week', 'this month', 'last month'."""
    m = re.search(r'\bthis\s+week\b', query, re.IGNORECASE)
    if m:
        monday = today - timedelta(days=today.weekday())
        return (monday, None, m.group(0))

    m = re.search(r'\blast\s+week\b', query, re.IGNORECASE)
    if m:
        this_monday = today - timedelta(days=today.weekday())
        last_monday = this_monday - timedelta(days=7)
        return (last_monday, this_monday, m.group(0))

    m = re.search(r'\bthis\s+month\b', query, re.IGNORECASE)
    if m:
        first_of_month = today.replace(day=1)
        return (first_of_month, None, m.group(0))

    m = re.search(r'\blast\s+month\b', query, re.IGNORECASE)
    if m:
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        first_of_last_month = last_month_end.replace(day=1)
        return (first_of_last_month, first_of_this_month, m.group(0))

    return None


def _resolve_date_expr(text: str, ref: datetime, today: datetime) -> Optional[datetime]:
    """Resolve a date expression used after 'since'/'before'/'after'.

    Handles: 'yesterday', 'last week', 'last Tuesday', 'March 10', '2026-03-10',
    'last Friday', 'last month', 'N days ago', etc.
    """
    text_lower = text.lower().strip()

    if text_lower == 'yesterday':
        return today - timedelta(days=1)

    if text_lower == 'today':
        return today

    # "last week" → start of last week
    if text_lower == 'last week':
        this_monday = today - timedelta(days=today.weekday())
        return this_monday - timedelta(days=7)

    # "last month" → start of last month
    if text_lower == 'last month':
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        return last_month_end.replace(day=1)

    # "last <day>"
    day_match = re.match(rf'last\s+({_day_names_pattern})', text_lower)
    if day_match:
        target_weekday = DAY_NAMES[day_match.group(1)]
        return _last_weekday(target_weekday, today)

    # "N days/weeks/months ago"
    ago_match = re.match(
        rf'(\d+|{_number_words_pattern})\s+(day|days|week|weeks|month|months)\s+ago',
        text_lower
    )
    if ago_match:
        n = _parse_number(ago_match.group(1))
        unit = ago_match.group(2).rstrip('s')
        if n and unit == 'day':
            return today - timedelta(days=n)
        elif n and unit == 'week':
            return today - timedelta(weeks=n)
        elif n and unit == 'month':
            month = ref.month - n
            year = ref.year
            while month <= 0:
                month += 12
                year -= 1
            return datetime(year, month, 1)

    # Month + day: "March 10", "Mar 10th"
    date = _parse_month_day(text, ref)
    if date:
        return date

    return None


def build_temporal_sql(after: Optional[str], before: Optional[str],
                       date_column: str = 'created_at') -> tuple[str, list]:
    """
    Build SQL WHERE clause fragment for temporal filtering.

    Returns (sql_fragment, params) to be AND'd with existing query.
    The sql_fragment starts with ' AND ' if non-empty.
    """
    clauses = []
    params = []

    if after:
        clauses.append(f"{date_column} >= ?")
        params.append(after)

    if before:
        clauses.append(f"{date_column} < ?")
        params.append(before)

    if not clauses:
        return ('', [])

    sql = ' AND ' + ' AND '.join(clauses)
    return (sql, params)
