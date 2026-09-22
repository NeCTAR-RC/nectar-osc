#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#

from io import StringIO
import os
import sys
import unittest
from unittest.mock import patch

from nectar_osc import config
from nectar_osc import identity

filename = os.path.realpath(
    os.path.join(os.path.dirname(__file__), 'nectar-osc.conf')
)

config.init(filename)


class TestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        identity.clear_caches()

    def capture_stdout(self):
        """Redirect sys.stdout to a StringIO for the rest of the test.

        Returns the StringIO; use getvalue() to inspect what was printed.
        Calling this again in the same test returns the same StringIO.
        """
        if isinstance(sys.stdout, StringIO):
            return sys.stdout
        out = StringIO()
        patcher = patch('sys.stdout', new=out)
        patcher.start()
        self.addCleanup(patcher.stop)
        return out
