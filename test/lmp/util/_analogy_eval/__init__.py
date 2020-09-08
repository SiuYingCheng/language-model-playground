r"""Test `lmp.util._analogy_eval.py`.

Usage:
    python -m unittest test.lmp.util._analogy_eval.__init__
"""

# built-in modules

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import inspect
import unittest


class TestUtilGenerateSequence(unittest.TestCase):
    r"""Test case for `lmp.util._analogy_eval.py`."""

    def test_signature(self):
        r"""Ensure signature consistency."""
        msg = 'Inconsistent module signature.'

        try:
            # pylint: disable=C0415
            import lmp
            import lmp.util._analogy_eval
            # pylint: enable=C0415

            # pylint: disable=W0212
            self.assertTrue(
                inspect.ismodule(lmp.util._analogy_eval),
                msg=msg
            )
            # pylint: enable=W0212
        except ImportError:
            self.fail(msg=msg)

    def test_module_attributes(self):
        r"""Declare required module attributes."""
        msg1 = 'Missing module attribute `{}`.'
        msg2 = 'Module attribute `{}` must be a function.'
        msg3 = 'Inconsistent module signature.'
        examples = (
            'analogy_inference',
            'analogy_eval',
        )

        try:
            # pylint: disable=C0415
            import lmp
            import lmp.util._analogy_eval
            # pylint: enable=C0415

            # pylint: disable=W0212
            for attr in examples:
                self.assertTrue(
                    hasattr(lmp.util._analogy_eval, attr),
                    msg=msg1.format(attr)
                )
                self.assertTrue(
                    inspect.isfunction(
                        getattr(lmp.util._analogy_eval, attr)
                    ),
                    msg=msg2.format(attr)
                )
            # pylint: enable=W0212
        except ImportError:
            self.fail(msg=msg3)


if __name__ == '__main__':
    unittest.main()