"""Tests for the /roll dice parser.

roll_dice() is the one piece of real logic that runs on every chat line, so it
gets the most coverage. Most assertions use dN where N == 1, which makes the
random component deterministic without seeding.
"""

import random

import pytest

from mudfinder import roll_dice


def total(roll_string):
    """roll_dice always appends ' ' + roll_type; strip that for plain rolls."""
    return roll_dice(roll_string).rstrip(" ")


class TestConstants:
    def test_bare_number(self):
        assert total("20") == "20"

    def test_leading_plus(self):
        assert total("+5") == "5"

    def test_negative(self):
        assert total("-3") == "-3"

    def test_addition(self):
        assert total("2+3") == "5"

    def test_subtraction_of_constants(self):
        assert total("10-4") == "6"

    def test_multiplication(self):
        assert total("2*3") == "6"

    @pytest.mark.parametrize("symbol", ["*", "x", "X", "×"])
    def test_multiplication_symbols_are_equivalent(self, symbol):
        assert total("2%s3" % symbol) == "6"

    def test_division_returns_a_float(self):
        # Documents current behaviour: division is not integer division, so
        # the result carries a decimal point.
        assert total("10/2") == "5.0"

    @pytest.mark.parametrize("symbol", ["/", "÷"])
    def test_division_symbols_are_equivalent(self, symbol):
        assert total("10%s2" % symbol) == "5.0"


class TestDice:
    def test_single_d1_is_deterministic(self):
        assert total("1d1") == "1"

    def test_implicit_count_defaults_to_one(self):
        assert total("d1") == "1"

    def test_multiple_dice_are_summed(self):
        assert total("5d1") == "5"

    def test_dice_plus_modifier(self):
        assert total("2d1+3") == "5"

    def test_dice_minus_modifier(self):
        assert total("2d1-1") == "1"

    def test_constant_minus_dice(self):
        assert total("5-1d1") == "4"

    def test_two_dice_terms(self):
        assert total("1d1+1d1") == "2"

    def test_dice_times_constant(self):
        assert total("2d1*3") == "6"

    def test_zero_dice_rolls_nothing(self):
        assert total("0d6") == "0"

    @pytest.mark.parametrize("sides", [2, 6, 8, 20, 100])
    def test_single_die_stays_in_range(self, sides):
        for _ in range(50):
            assert 1 <= int(total("1d%d" % sides)) <= sides

    def test_many_dice_stay_in_range(self):
        for _ in range(50):
            assert 3 <= int(total("3d6")) <= 18

    def test_seeded_rolls_are_reproducible(self):
        random.seed(1234)
        first = total("4d20+7")
        random.seed(1234)
        assert total("4d20+7") == first


class TestWhitespaceAndJunk:
    def test_leading_space_is_ignored(self):
        # This is the exact shape the chat handler passes in: it slices off
        # "/roll" and keeps the separating space.
        assert total(" 2d1+3") == "5"

    def test_surrounding_whitespace_is_ignored(self):
        assert total("  1d1  ") == "1"

    def test_non_dice_characters_are_filtered_out(self):
        assert total("abc") == "0"

    def test_empty_string(self):
        assert total("") == "0"


class TestRollType:
    def test_quoted_label_is_appended(self):
        assert roll_dice('1d1 "Attack"') == "1 Attack"

    def test_label_only(self):
        assert roll_dice('"Perception"') == "0 Perception"

    def test_unlabelled_roll_still_has_trailing_space(self):
        # Callers rely on the return value being str; the trailing separator is
        # present whether or not a label was supplied.
        assert roll_dice("1d1") == "1 "


class TestShowTotals:
    def test_bang_expands_individual_dice(self):
        assert roll_dice("2d1!") == "+1+1=2 "

    def test_bang_with_modifier(self):
        assert roll_dice("1d1+3!") == "+1+3=4 "

    def test_without_bang_only_the_total_is_returned(self):
        assert roll_dice("2d1") == "2 "


class TestMultipleRolls:
    def test_comma_separates_independent_rolls(self):
        assert roll_dice("1d1,1d1") == "1, 1 "

    def test_three_rolls(self):
        assert roll_dice("1d1,2d1,3d1") == "1, 2, 3 "

    def test_label_applies_to_the_whole_line(self):
        assert roll_dice('1d1,1d1 "Damage"') == "1, 1 Damage"


class TestKnownGaps:
    """Current behaviour that is arguably wrong, pinned so a fix is deliberate."""

    def test_zero_sided_die_raises(self):
        # A player typing "/roll 1d0" raises out of the chat handler rather
        # than returning an error message.
        with pytest.raises(ValueError):
            roll_dice("1d0")
