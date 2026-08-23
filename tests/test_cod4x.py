"""
Tests for b3/parsers/cod4x.py.

These exercise the real parser methods (getMap, getPlayerList,
getPlayerPings, getPlayerScores) and the two compiled regexes directly,
against status text shaped exactly like what CoD4X's SV_Status_f() emits
(non-legacy mode) - not reimplementations of the parsing logic.

Run with: pytest tests/
Adjust COD4X_PATH (env var) if cod4x.py doesn't live at the repo root.

Python 2.7 compatible: uses `imp.load_source` instead of `importlib.util`
(which does not exist in Python 2).
"""
import imp
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from _b3_stubs import install_b3_stubs

install_b3_stubs()

COD4X_PATH = os.environ.get(
    'COD4X_PATH',
    os.path.join(os.path.dirname(__file__), '..', 'cod4x.py')
)


def _load_cod4x_module():
    # imp.load_source both loads and registers the module; the first arg
    # is the name it will be given in sys.modules.
    module = imp.load_source('cod4x', COD4X_PATH)
    return module


cod4x = _load_cod4x_module()
Cod4XParser = cod4x.Cod4XParser


def make_parser(status_text=''):
    """
    Build a Cod4XParser instance without running the real __init__ chain
    (which needs a live config/rcon connection). self.write() is stubbed
    to return the given canned status text for every call.
    """
    parser = Cod4XParser.__new__(Cod4XParser)
    parser.PunkBuster = None
    parser.write = lambda *args, **kwargs: status_text
    parser.debug = lambda *args, **kwargs: None
    parser.verbose = lambda *args, **kwargs: None
    return parser


def build_status_row(slot, score, ping, playerid, steamid, name,
                      lastmsg, address, qport, rate, trailing_color=True):
    """
    Builds one player row matching CoD4X's non-legacy SV_Status_f() output:
    num score ping playerid steamid name lastmsg address qport rate
    """
    out = "%3i " % slot
    out += "%5i " % score
    out += "%4i " % ping
    out += str(playerid)
    out += " " * (20 - len(str(playerid)))
    out += str(steamid)
    out += " " * (18 - len(str(steamid)))
    out += name
    if trailing_color:
        out += "^7"
    out += " " * max(33 - len(name), 1)
    out += "%7i " % lastmsg
    out += address
    out += " " * (52 - len(address))
    out += " %5i" % qport
    out += " %5i" % rate
    return out


FULL_STATUS_HEADER = (
    "hostname: Example Test Server\n"
    "version : CoD4 X - linux-i386 build 0000 Jan  1 2000\n"
    "udp/ip  : 0.0.0.0:28960\n"
    "os      : linux\n"
    "type    : dedicated server\n"
    "map     : mp_testmap\n"
    "\n"
    "num score ping playerid            steamid           name"
    "                             lastmsg address                "
    "                              qport rate\n"
    "--- ----- ---- ------------------- ----------------- --------"
    "------------------------ ------- ------------------------------"
    "------------------------ ----- -----\n"
)


class MapRegexTests(unittest.TestCase):

    def test_matches_padded_colon_format(self):
        m = Cod4XParser._reMapNameFromStatus.match("map     : mp_testmap")
        self.assertIsNotNone(m)
        self.assertEqual(m.group('map'), 'mp_testmap')

    def test_matches_unpadded_colon_format(self):
        # base abstractParser format ("map: name") must still work
        m = Cod4XParser._reMapNameFromStatus.match("map: mp_backlot")
        self.assertIsNotNone(m)
        self.assertEqual(m.group('map'), 'mp_backlot')

    def test_does_not_match_unrelated_line(self):
        m = Cod4XParser._reMapNameFromStatus.match("hostname: some server")
        self.assertIsNone(m)


class PlayerRegexTests(unittest.TestCase):

    def test_live_capture_shape_zero_steamid(self):
        line = build_status_row(0, 0, 106, 1000000000000000001, 0,
                                 "TestPlayerOne", 50, "192.0.2.10:20000",
                                 29992, 25000, trailing_color=False)
        m = Cod4XParser._regPlayer.match(line.strip())
        self.assertIsNotNone(m)
        d = m.groupdict()
        self.assertEqual(d['slot'], '0')
        self.assertEqual(d['guid'], '1000000000000000001')
        self.assertEqual(d['steam'], '0')
        self.assertEqual(d['name'], 'TestPlayerOne')
        self.assertEqual(d['last'], '50')
        self.assertEqual(d['ip'], '192.0.2.10')
        self.assertEqual(d['port'], '20000')
        self.assertEqual(d['qport'], '29992')
        self.assertEqual(d['rate'], '25000')

    def test_nonzero_steamid_captured_separately(self):
        line = build_status_row(1, 10, 42, 2000000002, 90000000000000001,
                                 "TestPlayerTwo", 12, "203.0.113.20:20001",
                                 6597, 5000, trailing_color=False)
        m = Cod4XParser._regPlayer.match(line.strip())
        self.assertIsNotNone(m)
        self.assertEqual(m.group('guid'), '2000000002')
        self.assertEqual(m.group('steam'), '90000000000000001')
        self.assertEqual(m.group('name'), 'TestPlayerTwo')

    def test_trailing_color_code_is_stripped_from_name(self):
        line = build_status_row(0, 0, 106, 1000000000000000001, 0,
                                 "TestPlayerOne", 50, "192.0.2.10:20000",
                                 29992, 25000, trailing_color=True)
        m = Cod4XParser._regPlayer.match(line.strip())
        self.assertIsNotNone(m)
        self.assertEqual(m.group('name'), 'TestPlayerOne')
        self.assertNotIn('^7', m.group('name'))

    def test_lastmsg_not_leaked_into_name(self):
        line = build_status_row(0, 0, 106, 1000000000000000001, 0,
                                 "TestPlayerOne", 50, "192.0.2.10:20000",
                                 29992, 25000)
        m = Cod4XParser._regPlayer.match(line.strip())
        self.assertIsNotNone(m)
        self.assertNotIn('50', m.group('name'))
        self.assertEqual(m.group('last'), '50')

    def test_does_not_match_header_or_separator_lines(self):
        self.assertIsNone(Cod4XParser._regPlayer.match(
            "num score ping playerid            steamid           name"))
        self.assertIsNone(Cod4XParser._regPlayer.match(
            "--- ----- ---- ------------------- ----------------- ----"))
        self.assertIsNone(Cod4XParser._regPlayer.match(
            "hostname: Another Promod LIVE V2.20 Server is Born"))


class GetMapTests(unittest.TestCase):

    def test_extracts_map_from_full_status_blob(self):
        parser = make_parser(FULL_STATUS_HEADER)
        self.assertEqual(parser.getMap(), 'mp_testmap')

    def test_returns_none_when_write_returns_nothing(self):
        parser = make_parser('')
        self.assertIsNone(parser.getMap())

    def test_returns_none_when_map_line_absent(self):
        parser = make_parser("hostname: some server\nversion : x\n")
        self.assertIsNone(parser.getMap())


class GetPlayerListTests(unittest.TestCase):

    def test_parses_single_player(self):
        row = build_status_row(0, 0, 106, 1000000000000000001, 0,
                                "TestPlayerOne", 50, "192.0.2.10:20000",
                                29992, 25000)
        status = FULL_STATUS_HEADER + row + "\n"
        parser = make_parser(status)
        players = parser.getPlayerList()

        self.assertIn('0', players)
        p = players['0']
        self.assertEqual(p['guid'], '1000000000000000001')
        self.assertEqual(p['steam'], '0')
        self.assertEqual(p['name'], 'TestPlayerOne')

    def test_parses_multiple_players_in_ascending_slot_order(self):
        row0 = build_status_row(0, 0, 106, 1000000000000000001, 0,
                                 "TestPlayerOne", 50, "192.0.2.10:20000",
                                 29992, 25000)
        row1 = build_status_row(1, 25, 42, 2000000002, 90000000000000001,
                                 "TestPlayerTwo", 12, "203.0.113.20:20001",
                                 6597, 5000)
        status = FULL_STATUS_HEADER + row0 + "\n" + row1 + "\n"
        parser = make_parser(status)
        players = parser.getPlayerList()

        self.assertEqual(set(players.keys()), set(['0', '1']))
        self.assertEqual(players['1']['name'], 'TestPlayerTwo')
        self.assertEqual(players['1']['steam'], '90000000000000001')

    def test_empty_when_no_status_data(self):
        parser = make_parser('')
        self.assertEqual(parser.getPlayerList(), {})

    def test_empty_when_no_players_connected(self):
        parser = make_parser(FULL_STATUS_HEADER)
        self.assertEqual(parser.getPlayerList(), {})


class GetPlayerPingsAndScoresTests(unittest.TestCase):

    def setUp(self):
        row0 = build_status_row(0, 3, 106, 1000000000000000001, 0,
                                 "TestPlayerOne", 50, "192.0.2.10:20000",
                                 29992, 25000)
        row1 = build_status_row(1, -2, 42, 2000000002, 90000000000000001,
                                 "TestPlayerTwo", 12, "203.0.113.20:20001",
                                 6597, 5000)
        self.parser = make_parser(FULL_STATUS_HEADER + row0 + "\n" + row1 + "\n")

    def test_pings(self):
        pings = self.parser.getPlayerPings()
        self.assertEqual(pings, {'0': 106, '1': 42})

    def test_scores_including_negative(self):
        scores = self.parser.getPlayerScores()
        self.assertEqual(scores, {'0': 3, '1': -2})


if __name__ == '__main__':
    unittest.main()