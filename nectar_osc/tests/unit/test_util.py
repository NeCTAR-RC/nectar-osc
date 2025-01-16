# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from io import StringIO
import unittest
from unittest.mock import patch

from nectar_osc.util import query_yes_no


class TestUtil(unittest.TestCase):
    def test_query_yes_no(self):
        for answer in ['y', 'yes', 'Y', 'Yes', 'YES', '']:
            with patch('sys.stdout', new=StringIO()) as fakeOutput:
                with patch('nectar_osc.util._get_input', return_value=answer):
                    self.assertTrue(query_yes_no("Some question"))
                    self.assertEqual(
                        "Some question [Y/n] ", fakeOutput.getvalue()
                    )
        for answer in ['n', 'no', 'N', 'No', 'NO']:
            with patch('sys.stdout', new=StringIO()) as fakeOutput:
                with patch('nectar_osc.util._get_input', return_value=answer):
                    self.assertFalse(query_yes_no("Some question"))
                    self.assertEqual(
                        "Some question [Y/n] ", fakeOutput.getvalue()
                    )

        # Again with a different default=None
        for answer in ['y', 'yes', 'Y', 'Yes', 'YES']:
            with patch('sys.stdout', new=StringIO()) as fakeOutput:
                with patch('nectar_osc.util._get_input', return_value=answer):
                    self.assertTrue(
                        query_yes_no("Some question", default=None)
                    )
                    self.assertEqual(
                        "Some question [y/n] ", fakeOutput.getvalue()
                    )
        for answer in ['n', 'no', 'N', 'No', 'NO']:
            with patch('sys.stdout', new=StringIO()) as fakeOutput:
                with patch('nectar_osc.util._get_input', return_value=answer):
                    self.assertFalse(
                        query_yes_no("Some question", default=None)
                    )
                    self.assertEqual(
                        "Some question [y/n] ", fakeOutput.getvalue()
                    )

        # Again with a different default='no'
        for answer in ['y', 'yes', 'Y', 'Yes', 'YES']:
            with patch('sys.stdout', new=StringIO()) as fakeOutput:
                with patch('nectar_osc.util._get_input', return_value=answer):
                    self.assertTrue(
                        query_yes_no("Some question", default='no')
                    )
                    self.assertEqual(
                        "Some question [y/N] ", fakeOutput.getvalue()
                    )
        for answer in ['n', 'no', 'N', 'No', 'NO', '']:
            with patch('sys.stdout', new=StringIO()) as fakeOutput:
                with patch('nectar_osc.util._get_input', return_value=answer):
                    self.assertFalse(
                        query_yes_no("Some question", default='no')
                    )
                    self.assertEqual(
                        "Some question [y/N] ", fakeOutput.getvalue()
                    )

        # Handling bad answers
        with patch('sys.stdout', new=StringIO()) as fakeOutput:
            with patch(
                'nectar_osc.util._get_input', side_effect=['1', 'fish', '']
            ) as mock_get:
                self.assertTrue(query_yes_no("Some question"))
                self.assertEqual(
                    (
                        "Some question [Y/n] "
                        "Please respond with 'yes' or 'no' (or 'y' or 'n')."
                        "\nSome question [Y/n] "
                        "Please respond with 'yes' or 'no' (or 'y' or 'n')."
                        "\nSome question [Y/n] "
                    ),
                    fakeOutput.getvalue(),
                )
            self.assertEqual(3, mock_get.call_count)

        with patch('sys.stdout', new=StringIO()) as fakeOutput:
            with patch(
                'nectar_osc.util._get_input', side_effect=['1', '', 'y']
            ) as mock_get:
                self.assertTrue(query_yes_no("Some question", default=None))
                self.assertEqual(
                    (
                        "Some question [y/n] "
                        "Please respond with 'yes' or 'no' (or 'y' or 'n')."
                        "\nSome question [y/n] "
                        "Please respond with 'yes' or 'no' (or 'y' or 'n')."
                        "\nSome question [y/n] "
                    ),
                    fakeOutput.getvalue(),
                )
            self.assertEqual(3, mock_get.call_count)

        # Bad default
        with self.assertRaises(ValueError):
            query_yes_no("Some question", default="weeble")
