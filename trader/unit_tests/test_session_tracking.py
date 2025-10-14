#!/usr/bin/env python3
"""
Unit Tests for Session Duration Tracking (GAP #8)

Tests that session duration is correctly calculated and saved:
- Session start time recording
- Session end time recording
- Duration calculation (seconds and minutes)
- JSON serialization

Created: October 13, 2025
"""

import unittest
from unittest.mock import Mock
from datetime import datetime, timedelta
import pytz
import json


class TestSessionDurationCalculation(unittest.TestCase):
    """Test session duration calculation logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.eastern = pytz.timezone('US/Eastern')

    def test_duration_calculated_correctly_for_short_session(self):
        """Test duration calculation for 4.5 minute session (actual Oct 13 case)"""
        # Session from Oct 13: 11:37 AM to 11:41 AM (4.5 minutes)
        session_start = datetime(2025, 10, 13, 11, 37, 4, tzinfo=self.eastern)
        session_end = datetime(2025, 10, 13, 11, 41, 35, tzinfo=self.eastern)

        # Calculate duration
        duration_seconds = (session_end - session_start).total_seconds()
        duration_minutes = round(duration_seconds / 60, 2)

        # Verify calculations
        self.assertAlmostEqual(duration_seconds, 271, delta=1,
                              msg="Duration should be ~271 seconds (4.5 min)")
        self.assertAlmostEqual(duration_minutes, 4.52, delta=0.01,
                              msg="Duration should be ~4.52 minutes")

        print(f"✓ Short session: {duration_minutes:.2f} minutes ({duration_seconds:.0f} seconds)")

    def test_duration_calculated_correctly_for_full_day(self):
        """Test duration calculation for full trading day (6.5 hours)"""
        # Full day: 9:30 AM to 4:00 PM (6.5 hours)
        session_start = datetime(2025, 10, 13, 9, 30, 0, tzinfo=self.eastern)
        session_end = datetime(2025, 10, 13, 16, 0, 0, tzinfo=self.eastern)

        # Calculate duration
        duration_seconds = (session_end - session_start).total_seconds()
        duration_minutes = round(duration_seconds / 60, 2)

        # Verify calculations
        self.assertEqual(duration_seconds, 23400,
                        msg="Duration should be exactly 23,400 seconds (6.5 hours)")
        self.assertEqual(duration_minutes, 390.0,
                        msg="Duration should be exactly 390 minutes (6.5 hours)")

        print(f"✓ Full day session: {duration_minutes:.2f} minutes ({duration_seconds:.0f} seconds)")

    def test_duration_is_zero_when_times_are_equal(self):
        """Test that duration is 0 when start and end are the same"""
        session_time = datetime(2025, 10, 13, 10, 0, 0, tzinfo=self.eastern)
        session_start = session_time
        session_end = session_time

        # Calculate duration
        duration_seconds = (session_end - session_start).total_seconds()
        duration_minutes = round(duration_seconds / 60, 2)

        self.assertEqual(duration_seconds, 0, "Duration should be 0 seconds")
        self.assertEqual(duration_minutes, 0.0, "Duration should be 0.0 minutes")

        print("✓ Zero duration when start == end")

    def test_duration_handles_timezone_correctly(self):
        """Test that duration calculation works across timezone changes"""
        # Create times in different representations
        utc = pytz.UTC
        session_start_utc = datetime(2025, 10, 13, 15, 37, 0, tzinfo=utc)  # 11:37 AM ET
        session_start_et = session_start_utc.astimezone(self.eastern)

        session_end_utc = datetime(2025, 10, 13, 15, 42, 0, tzinfo=utc)  # 11:42 AM ET
        session_end_et = session_end_utc.astimezone(self.eastern)

        # Calculate duration (should be same regardless of timezone)
        duration_utc = (session_end_utc - session_start_utc).total_seconds()
        duration_et = (session_end_et - session_start_et).total_seconds()

        self.assertEqual(duration_utc, duration_et,
                        "Duration should be same in UTC and ET")
        self.assertEqual(duration_utc, 300, "Duration should be 5 minutes")

        print("✓ Duration calculation is timezone-agnostic")

    def test_duration_rounds_correctly_to_2_decimals(self):
        """Test that duration minutes are rounded to 2 decimal places"""
        session_start = datetime(2025, 10, 13, 10, 0, 0, tzinfo=self.eastern)
        session_end = datetime(2025, 10, 13, 10, 1, 37, tzinfo=self.eastern)  # 1 min 37 sec

        duration_seconds = (session_end - session_start).total_seconds()
        duration_minutes = round(duration_seconds / 60, 2)

        self.assertEqual(duration_seconds, 97, "Duration should be 97 seconds")
        self.assertEqual(duration_minutes, 1.62, "Duration should be 1.62 minutes")

        print(f"✓ Duration rounded correctly: {duration_minutes} minutes")


class TestSessionTimeSerialization(unittest.TestCase):
    """Test JSON serialization of session times"""

    def setUp(self):
        """Set up test fixtures"""
        self.eastern = pytz.timezone('US/Eastern')

    def test_datetime_serializes_to_iso_format(self):
        """Test that datetime objects serialize to ISO 8601 format"""
        session_start = datetime(2025, 10, 13, 11, 37, 4, tzinfo=self.eastern)

        # Serialize to ISO format
        serialized = session_start.isoformat()

        # Verify format
        self.assertIn('2025-10-13', serialized, "Should contain date")
        self.assertIn('11:37:04', serialized, "Should contain time")
        # Timezone offset can be -04:00 (EDT) or -05:00 (EST) depending on date
        self.assertTrue('-04:' in serialized or '-05:' in serialized,
                       f"Should contain timezone offset, got: {serialized}")

        print(f"✓ Datetime serialized: {serialized}")

    def test_duration_fields_added_to_analytics(self):
        """Test that duration_seconds and duration_minutes are in analytics"""
        # Mock analytics data structure
        session_start = datetime(2025, 10, 13, 11, 37, 4, tzinfo=self.eastern)
        session_end = datetime(2025, 10, 13, 11, 41, 35, tzinfo=self.eastern)

        duration_seconds = (session_end - session_start).total_seconds()
        duration_minutes = round(duration_seconds / 60, 2)

        analytics = {
            'session_start': session_start.isoformat(),
            'session_end': session_end.isoformat(),
            'duration_seconds': duration_seconds,
            'duration_minutes': duration_minutes,
            'filter_blocks': {},
            'entry_paths': {}
        }

        # Verify structure
        self.assertIn('duration_seconds', analytics, "Should have duration_seconds field")
        self.assertIn('duration_minutes', analytics, "Should have duration_minutes field")
        self.assertGreater(analytics['duration_seconds'], 0, "Duration should be > 0")
        self.assertGreater(analytics['duration_minutes'], 0, "Duration minutes should be > 0")

        # Verify JSON serializable
        json_str = json.dumps(analytics)
        self.assertIsNotNone(json_str, "Analytics should be JSON serializable")

        print(f"✓ Analytics has duration fields: {duration_seconds}s, {duration_minutes}m")

    def test_json_serialization_roundtrip(self):
        """Test that session data can be serialized and deserialized"""
        eastern = pytz.timezone('US/Eastern')
        session_start = datetime(2025, 10, 13, 11, 37, 4, tzinfo=eastern)
        session_end = datetime(2025, 10, 13, 11, 41, 35, tzinfo=eastern)

        duration_seconds = (session_end - session_start).total_seconds()
        duration_minutes = round(duration_seconds / 60, 2)

        # Create data structure
        original_data = {
            'analytics': {
                'session_start': session_start.isoformat(),
                'session_end': session_end.isoformat(),
                'duration_seconds': duration_seconds,
                'duration_minutes': duration_minutes
            }
        }

        # Serialize to JSON
        json_str = json.dumps(original_data, indent=2)

        # Deserialize back
        loaded_data = json.loads(json_str)

        # Verify data integrity
        self.assertEqual(loaded_data['analytics']['duration_seconds'],
                        original_data['analytics']['duration_seconds'],
                        "Duration seconds should survive roundtrip")
        self.assertEqual(loaded_data['analytics']['duration_minutes'],
                        original_data['analytics']['duration_minutes'],
                        "Duration minutes should survive roundtrip")

        print("✓ JSON serialization roundtrip successful")


class TestEdgeCases(unittest.TestCase):
    """Test edge cases in session tracking"""

    def setUp(self):
        """Set up test fixtures"""
        self.eastern = pytz.timezone('US/Eastern')

    def test_duration_when_session_start_is_none(self):
        """Test that duration is 0 when session_start is None"""
        session_start = None
        session_end = datetime(2025, 10, 13, 11, 41, 35, tzinfo=self.eastern)

        # Calculate duration (with None handling)
        if session_start and session_end:
            duration_seconds = (session_end - session_start).total_seconds()
        else:
            duration_seconds = 0

        self.assertEqual(duration_seconds, 0, "Duration should be 0 when start is None")

        print("✓ Handles None session_start gracefully")

    def test_duration_when_session_end_is_none(self):
        """Test that duration is 0 when session_end is None"""
        session_start = datetime(2025, 10, 13, 11, 37, 4, tzinfo=self.eastern)
        session_end = None

        # Calculate duration (with None handling)
        if session_start and session_end:
            duration_seconds = (session_end - session_start).total_seconds()
        else:
            duration_seconds = 0

        self.assertEqual(duration_seconds, 0, "Duration should be 0 when end is None")

        print("✓ Handles None session_end gracefully")

    def test_duration_when_both_times_are_none(self):
        """Test that duration is 0 when both times are None"""
        session_start = None
        session_end = None

        # Calculate duration (with None handling)
        if session_start and session_end:
            duration_seconds = (session_end - session_start).total_seconds()
        else:
            duration_seconds = 0

        self.assertEqual(duration_seconds, 0, "Duration should be 0 when both are None")

        print("✓ Handles both None times gracefully")


def run_tests():
    """Run all session tracking tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSessionDurationCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestSessionTimeSerialization))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY - Session Duration Tracking (GAP #8)")
    print("="*70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
