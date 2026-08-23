"""
Minimal stand-ins for the b3 modules that cod4x.py imports, so the parser
module can be loaded and its parsing methods exercised without requiring
the full (Python 2 only) BigBrotherBot framework to be installed.

Only install_b3_stubs() is meant to be called from tests, before cod4x.py
is imported.
"""
import sys
import types


def install_b3_stubs():
    if 'b3' in sys.modules and getattr(sys.modules['b3'], '_is_cod4x_test_stub', False):
        return  # already installed by an earlier test module

    if 'b3' in sys.modules and not getattr(sys.modules['b3'], '_is_cod4x_test_stub', False):
        # a real b3 install is already importable - don't clobber it
        return

    b3 = types.ModuleType('b3')
    b3._is_cod4x_test_stub = True
    b3_clients = types.ModuleType('b3.clients')
    b3_functions = types.ModuleType('b3.functions')
    b3_parsers = types.ModuleType('b3.parsers')
    b3_parsers_cod4 = types.ModuleType('b3.parsers.cod4')

    class Client(object):
        """Stand-in for b3.clients.Client - only used for isinstance() checks."""
        def __init__(self, guid=None, cid=None):
            self.guid = guid
            self.cid = cid

    class Cod4Parser(object):
        """
        Minimal stand-in for b3.parsers.cod4.Cod4Parser (itself a subclass of
        the q3a AbstractParser chain). Provides just enough surface for
        Cod4XParser's own methods to run in isolation.
        """
        PunkBuster = None

        def debug(self, *args, **kwargs):
            pass

        def verbose(self, *args, **kwargs):
            pass

        def write(self, *args, **kwargs):
            return ''

    b3_clients.Client = Client
    b3_parsers_cod4.Cod4Parser = Cod4Parser
    b3_functions.time2minutes = lambda d: d
    b3_functions.minutesStr = lambda d: str(d)

    b3.clients = b3_clients
    b3.functions = b3_functions
    b3.parsers = b3_parsers
    b3_parsers.cod4 = b3_parsers_cod4

    sys.modules['b3'] = b3
    sys.modules['b3.clients'] = b3_clients
    sys.modules['b3.functions'] = b3_functions
    sys.modules['b3.parsers'] = b3_parsers
    sys.modules['b3.parsers.cod4'] = b3_parsers_cod4