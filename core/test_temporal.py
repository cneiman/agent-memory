#!/usr/bin/env python3
"""
Tests for the temporal query parser.

Run: python3 -m pytest test_temporal.py -v
  or: python3 test_temporal.py
"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

# Ensure we can import from same directory
sys.path.insert(0, str(Path(__file__).parent))

from temporal import parse_temporal, build_temporal_sql


# Fixed reference time: Wednesday 2026-03-18 14:30:00
REF_TIME = datetime(2026, 3, 18, 14, 30, 0)


class TestParseTemporalYesterday(unittest.TestCase):
    """Test 'yesterday' parsing."""

    def test_what_happened_yesterday(self):
        r = parse_temporal("what happened yesterday", REF_TIME)
        self.assertEqual(r['after'], '2026-03-17')
        self.assertEqual(r['before'], '2026-03-18')
        self.assertEqual(r['temporal_expr'], 'yesterday')
        self.assertNotIn('yesterday', r['cleaned_query'].lower())

    def test_yesterday_standalone(self):
        r = parse_temporal("yesterday", REF_TIME)
        self.assertEqual(r['after'], '2026-03-17')
        self.assertEqual(r['before'], '2026-03-18')

    def test_things_from_yesterday(self):
        r = parse_temporal("things from yesterday", REF_TIME)
        self.assertEqual(r['after'], '2026-03-17')
        self.assertEqual(r['temporal_expr'], 'yesterday')
        self.assertIn('things', r['cleaned_query'])


class TestParseTemporalToday(unittest.TestCase):
    """Test 'today' parsing."""

    def test_what_happened_today(self):
        r = parse_temporal("what happened today", REF_TIME)
        self.assertEqual(r['after'], '2026-03-18')
        self.assertEqual(r['before'], '2026-03-19')
        self.assertEqual(r['temporal_expr'], 'today')


class TestParseTemporalLastWeek(unittest.TestCase):
    """Test 'last week' parsing."""

    def test_decisions_last_week(self):
        r = parse_temporal("decisions last week", REF_TIME)
        # Last week: Mon Mar 9 to Sun Mar 15 (before Mon Mar 16)
        self.assertEqual(r['after'], '2026-03-09')
        self.assertEqual(r['before'], '2026-03-16')
        self.assertEqual(r['temporal_expr'], 'last week')
        self.assertEqual(r['cleaned_query'], 'decisions')

    def test_what_happened_last_week(self):
        r = parse_temporal("what happened last week?", REF_TIME)
        self.assertEqual(r['after'], '2026-03-09')
        self.assertEqual(r['before'], '2026-03-16')
        self.assertNotIn('last week', r['cleaned_query'].lower())


class TestParseTemporalThisWeek(unittest.TestCase):
    """Test 'this week' parsing."""

    def test_changes_this_week(self):
        r = parse_temporal("changes this week", REF_TIME)
        # This week: Mon Mar 16 onward (Wed is ref)
        self.assertEqual(r['after'], '2026-03-16')
        self.assertIsNone(r['before'])
        self.assertEqual(r['temporal_expr'], 'this week')


class TestParseTemporalLastMonth(unittest.TestCase):
    """Test 'last month' parsing."""

    def test_events_last_month(self):
        r = parse_temporal("events last month", REF_TIME)
        # Last month: Feb 2026
        self.assertEqual(r['after'], '2026-02-01')
        self.assertEqual(r['before'], '2026-03-01')
        self.assertEqual(r['temporal_expr'], 'last month')


class TestParseTemporalThisMonth(unittest.TestCase):
    """Test 'this month' parsing."""

    def test_notes_this_month(self):
        r = parse_temporal("notes this month", REF_TIME)
        self.assertEqual(r['after'], '2026-03-01')
        self.assertIsNone(r['before'])
        self.assertEqual(r['temporal_expr'], 'this month')


class TestParseTemporalNAgo(unittest.TestCase):
    """Test 'N days/weeks/months ago' parsing."""

    def test_meeting_3_days_ago(self):
        r = parse_temporal("meeting 3 days ago", REF_TIME)
        # 3 days ago from Mar 18 = Mar 15
        self.assertEqual(r['after'], '2026-03-15')
        self.assertEqual(r['before'], '2026-03-16')
        self.assertEqual(r['temporal_expr'], '3 days ago')
        self.assertEqual(r['cleaned_query'], 'meeting')

    def test_discussion_2_weeks_ago(self):
        r = parse_temporal("discussion 2 weeks ago", REF_TIME)
        # 2 weeks ago from Mar 18 = week of Mar 4
        # Mar 4 is a Wednesday, start of that week (Monday) = Mar 2
        self.assertEqual(r['after'], '2026-03-02')
        self.assertEqual(r['before'], '2026-03-09')

    def test_five_days_ago_word(self):
        r = parse_temporal("notes from five days ago", REF_TIME)
        # 5 days ago from Mar 18 = Mar 13
        self.assertEqual(r['after'], '2026-03-13')
        self.assertEqual(r['before'], '2026-03-14')

    def test_1_month_ago(self):
        r = parse_temporal("projects 1 month ago", REF_TIME)
        # 1 month ago from March = February
        self.assertEqual(r['after'], '2026-02-01')
        self.assertEqual(r['before'], '2026-03-01')


class TestParseTemporalLastNamedDay(unittest.TestCase):
    """Test 'last Tuesday' etc."""

    def test_last_tuesday(self):
        # Ref is Wednesday Mar 18
        r = parse_temporal("what did we discuss last Tuesday?", REF_TIME)
        # Last Tuesday from Wed Mar 18 = Tue Mar 17... wait, that's yesterday
        # Actually "last Tuesday" should be the most recent Tuesday before today
        # From Wednesday, that's yesterday (Mar 17)? No...
        # Hmm. "last Tuesday" when today is Wednesday:
        # Current weekday = 2 (Wednesday), target = 1 (Tuesday)
        # days_back = (2 - 1) % 7 = 1
        # But we set days_back = 7 if days_back == 0, so 1 day back → Mar 17
        # Wait, but "last Tuesday" from a Wednesday should probably be the PREVIOUS Tuesday
        # which is Mar 10, not yesterday Mar 17 (which would be "this past Tuesday" or just "Tuesday").
        # The current implementation returns 1 day back, which is yesterday.
        # This is debatable — "last Tuesday" is ambiguous when the day just passed.
        # Let me check: if today is Wednesday, "last Tuesday" = yesterday or last week's Tuesday?
        # Common English: "last Tuesday" from a Wednesday typically means yesterday.
        # But some people mean the week before. Let's go with the simpler/more common: 1 day back.
        self.assertEqual(r['after'], '2026-03-17')
        self.assertEqual(r['before'], '2026-03-18')
        self.assertEqual(r['temporal_expr'], 'last Tuesday')
        self.assertIn('discuss', r['cleaned_query'])
        self.assertNotIn('Tuesday', r['cleaned_query'])

    def test_last_friday(self):
        # From Wed Mar 18, last Friday = Mar 13
        r = parse_temporal("what changed since last Friday?", REF_TIME)
        # "since last Friday" → after = Mar 13
        self.assertEqual(r['after'], '2026-03-13')
        self.assertIsNone(r['before'])

    def test_last_wednesday_same_day(self):
        # "last Wednesday" when today IS Wednesday → 7 days ago = Mar 11
        r = parse_temporal("meeting last Wednesday", REF_TIME)
        self.assertEqual(r['after'], '2026-03-11')
        self.assertEqual(r['before'], '2026-03-12')

    def test_last_monday(self):
        # From Wed Mar 18, last Monday = Mar 16
        r = parse_temporal("standup last Monday", REF_TIME)
        self.assertEqual(r['after'], '2026-03-16')
        self.assertEqual(r['before'], '2026-03-17')


class TestParseTemporalSinceBefore(unittest.TestCase):
    """Test 'since X', 'before X' parsing."""

    def test_since_march_10(self):
        r = parse_temporal("deployments since March 10", REF_TIME)
        self.assertEqual(r['after'], '2026-03-10')
        self.assertIsNone(r['before'])
        self.assertIn('deployments', r['cleaned_query'])

    def test_before_february(self):
        r = parse_temporal("old decisions before February", REF_TIME)
        self.assertEqual(r['before'], '2026-02-01')
        self.assertIsNone(r['after'])

    def test_since_last_week(self):
        r = parse_temporal("updates since last week", REF_TIME)
        # "since last week" → after = start of last week (Mon Mar 9)
        self.assertEqual(r['after'], '2026-03-09')

    def test_since_yesterday(self):
        r = parse_temporal("errors since yesterday", REF_TIME)
        self.assertEqual(r['after'], '2026-03-17')

    def test_after_march_15(self):
        r = parse_temporal("commits after March 15", REF_TIME)
        self.assertEqual(r['after'], '2026-03-15')


class TestParseTemporalBetween(unittest.TestCase):
    """Test 'between X and Y' parsing."""

    def test_between_dates(self):
        r = parse_temporal("meetings between March 1 and March 15", REF_TIME)
        self.assertEqual(r['after'], '2026-03-01')
        self.assertEqual(r['before'], '2026-03-16')  # +1 day for inclusive end
        self.assertIn('meetings', r['cleaned_query'])

    def test_between_with_th(self):
        r = parse_temporal("events between March 5th and March 10th", REF_TIME)
        self.assertEqual(r['after'], '2026-03-05')
        self.assertEqual(r['before'], '2026-03-11')


class TestParseTemporalNoTemporal(unittest.TestCase):
    """Test queries with no temporal expression."""

    def test_plain_query(self):
        r = parse_temporal("what's the weather", REF_TIME)
        self.assertIsNone(r['after'])
        self.assertIsNone(r['before'])
        self.assertIsNone(r['temporal_expr'])
        self.assertEqual(r['cleaned_query'], "what's the weather")

    def test_deployment_query(self):
        r = parse_temporal("how to deploy", REF_TIME)
        self.assertIsNone(r['temporal_expr'])
        self.assertEqual(r['cleaned_query'], 'how to deploy')

    def test_empty_query(self):
        r = parse_temporal("", REF_TIME)
        self.assertIsNone(r['temporal_expr'])


class TestParseTemporalEdgeCases(unittest.TestCase):
    """Edge cases — 'last' without temporal meaning, etc."""

    def test_last_item_no_temporal(self):
        r = parse_temporal("the last item", REF_TIME)
        # "last" here is not temporal — no day/week/month follows
        self.assertIsNone(r['temporal_expr'])
        self.assertEqual(r['cleaned_query'], 'the last item')

    def test_last_resort_no_temporal(self):
        r = parse_temporal("last resort options", REF_TIME)
        self.assertIsNone(r['temporal_expr'])

    def test_at_last_no_temporal(self):
        r = parse_temporal("at last we finished", REF_TIME)
        self.assertIsNone(r['temporal_expr'])

    def test_lasting_no_temporal(self):
        r = parse_temporal("lasting impact of the change", REF_TIME)
        self.assertIsNone(r['temporal_expr'])

    def test_case_insensitive(self):
        r = parse_temporal("notes LAST WEEK", REF_TIME)
        self.assertEqual(r['after'], '2026-03-09')
        self.assertEqual(r['temporal_expr'], 'LAST WEEK')

    def test_mixed_case_yesterday(self):
        r = parse_temporal("Yesterday notes", REF_TIME)
        self.assertEqual(r['after'], '2026-03-17')


class TestBuildTemporalSQL(unittest.TestCase):
    """Test SQL clause builder."""

    def test_after_only(self):
        sql, params = build_temporal_sql('2026-03-10', None)
        self.assertIn('created_at >= ?', sql)
        self.assertEqual(params, ['2026-03-10'])

    def test_before_only(self):
        sql, params = build_temporal_sql(None, '2026-03-15')
        self.assertIn('created_at < ?', sql)
        self.assertEqual(params, ['2026-03-15'])

    def test_both(self):
        sql, params = build_temporal_sql('2026-03-10', '2026-03-15')
        self.assertIn('created_at >= ?', sql)
        self.assertIn('created_at < ?', sql)
        self.assertEqual(len(params), 2)

    def test_neither(self):
        sql, params = build_temporal_sql(None, None)
        self.assertEqual(sql, '')
        self.assertEqual(params, [])

    def test_custom_column(self):
        sql, params = build_temporal_sql('2026-03-10', None, 'updated_at')
        self.assertIn('updated_at >= ?', sql)

    def test_starts_with_and(self):
        sql, params = build_temporal_sql('2026-03-10', None)
        self.assertTrue(sql.strip().startswith('AND'))


class TestCleanedQueryQuality(unittest.TestCase):
    """Verify cleaned queries are usable for search."""

    def test_no_trailing_question_mark(self):
        r = parse_temporal("what happened yesterday?", REF_TIME)
        self.assertFalse(r['cleaned_query'].endswith('?'))

    def test_no_double_spaces(self):
        r = parse_temporal("what did we discuss last Tuesday?", REF_TIME)
        self.assertNotIn('  ', r['cleaned_query'])

    def test_meaningful_residual(self):
        r = parse_temporal("decisions made this week", REF_TIME)
        self.assertIn('decisions', r['cleaned_query'])
        self.assertIn('made', r['cleaned_query'])

    def test_since_leaves_query(self):
        r = parse_temporal("errors since yesterday", REF_TIME)
        self.assertIn('errors', r['cleaned_query'])
        self.assertNotIn('since', r['cleaned_query'])


if __name__ == '__main__':
    unittest.main()
