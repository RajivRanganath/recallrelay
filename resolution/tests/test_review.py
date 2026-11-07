import copy
import json
from pathlib import Path
import unittest

from resolution.backend.errors import InvalidInput
from resolution.backend.review import review
from resolution.backend.validation import validate_contract

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'contracts/fixtures/resolution-request.json').read_text())


def request(**changes):
    data = copy.deepcopy(FIXTURE)
    data['remedy_conditions_met'] = True
    for path, value in changes.items():
        section, _, field = path.partition('__')
        (data[section] if field else data)[field or section] = value
    return data


class ReviewTests(unittest.TestCase):
    def test_eligible_with_conditions_met_awaits_approval_for_remaining_balance(self):
        result = review(request(order__previously_refunded_minor=1000))
        validate_contract('resolution-response', result)
        self.assertEqual((result['status'], result['proposed_amount_minor']), ('awaiting_approval', 3000))
        self.assertEqual(result['citations'], ['confirmed-label'])
        self.assertIsNone(result['operation_id'])
        self.assertEqual(result['mode'], 'mock')

    def test_unconfirmed_remedy_conditions_never_reach_approval(self):
        result = review(copy.deepcopy(FIXTURE))  # fixture has remedy_conditions_met false
        self.assertEqual((result['status'], result['proposed_amount_minor']), ('manual_required', 0))

    def test_manual_for_old_foreign_currency_multi_unit_or_fully_refunded(self):
        for change in ({'order__age_days': 181}, {'order__currency': 'EUR'}, {'order__quantity': 2},
                       {'order__previously_refunded_minor': 4000}, {'order__previously_refunded_minor': 5000}):
            with self.subTest(change):
                result = review(request(**change))
                self.assertEqual((result['status'], result['proposed_amount_minor']), ('manual_required', 0))

    def test_needs_information_and_excluded_never_propose_money(self):
        for decision, status in (('needs_information', 'needs_information'), ('excluded', 'excluded')):
            data = request()
            data['assessment']['decision'] = decision
            result = review(data)
            validate_contract('resolution-response', result)
            self.assertEqual((result['status'], result['proposed_amount_minor']), (status, 0))

    def test_mismatched_cases_are_rejected(self):
        data = request()
        data['assessment']['case_id'] = 'other-case'
        with self.assertRaises(InvalidInput):
            review(data)


if __name__ == '__main__':
    unittest.main()
