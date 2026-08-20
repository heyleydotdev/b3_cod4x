#
# BigBrotherBot(B3) (www.bigbrotherbot.net)
# Copyright (C) 2005 Michael "ThorN" Thornton
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#
# CHANGELOG:
#           0.1 - Initial release
#           0.2 - Added support for B3Hide plugin, force ID64
#           0.3 - Add player status methods
#           0.4 - Correct status parsing regexes

__author__ = 'Leiizko, heyleydotdev'
__version__ = '0.4'


import b3.clients
import b3.functions
import b3.parsers.cod4
import re


class Cod4X18Parser(b3.parsers.cod4.Cod4Parser):
    gameName = 'cod4'
    IpsOnly = False
    _guidLength = 0

    _reMapNameFromStatus = re.compile(r'^map\s*:\s*(?P<map>.+)$', re.IGNORECASE)

    _regPlayer = re.compile(
        r'^\s*(?P<slot>[0-9]+)\s+'
        r'(?P<score>[0-9-]+)\s+'
        r'(?P<ping>[0-9]+)\s+'
        r'(?P<guid>[0-9]+)\s+'
        r'(?P<steam>[0-9]+)\s+'
        r'(?P<name>.*?)\s+'
        r'(?P<last>[0-9]+)\s+'
        r'(?P<ip>(?:(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.){3}'
        r'(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])):?'
        r'(?P<port>-?[0-9]{1,5})\s*'
        r'(?P<qport>-?[0-9]{1,5})\s+'
        r'(?P<rate>[0-9]+)$',
        re.IGNORECASE
    )

    _commands = {
        'message': 'tell %(cid)s %(message)s',
        'say': 'say %(message)s',
        'set': 'set %(name)s "%(value)s"',
        'kick': 'kick %(cid)s %(reason)s ',
        'ban': 'permban %(cid)s %(reason)s ',
        'unban': 'unban %(guid)s',
        'tempban': 'tempban %(cid)s %(duration)sm %(reason)s',
        'kickbyfullname': 'kick %(cid)s'
    }

    def startup(self):
        """
        Called after the parser is created before run().
        """
        self.clients.newClient(
            '-1',
            guid='WORLD',
            name='World',
            hide=True,
            pbid='WORLD'
        )
        self.write('sv_usesteam64id  1', maxRetries=3)

    def unban(self, client, reason='', admin=None, silent=False, *kwargs):
        """
        Unban a client.
        :param client: The client to unban
        :param reason: The reason for the unban
        :param admin: The admin who unbanned this client
        :param silent: Whether or not to announce this unban
        """
        result = self.write(self.getCommand('unban', guid=client.guid))

        if admin:
            admin.message(result)

    def tempban(self, client, reason='', duration=2, admin=None, silent=False, *kwargs):
        """
        Tempban a client.
        :param client: The client to tempban
        :param reason: The reason for this tempban
        :param duration: The duration of the tempban
        :param admin: The admin who performed the tempban
        :param silent: Whether or not to announce the tempban
        """
        duration = b3.functions.time2minutes(duration)

        if isinstance(client, b3.clients.Client) and not client.guid:
            # client has no guid, kick instead
            return self.kick(client, reason, admin, silent)

        elif isinstance(client, str) and re.match('^[0-9]+$', client):
            self.write(
                self.getCommand('tempban', cid=client, reason=reason)
            )
            return

        elif admin:
            banduration = b3.functions.minutesStr(duration)
            variables = self.getMessageVariables(
                client=client,
                reason=reason,
                admin=admin,
                banduration=banduration
            )
            fullreason = self.getMessage('temp_banned_by', variables)

        else:
            banduration = b3.functions.minutesStr(duration)
            variables = self.getMessageVariables(
                client=client,
                reason=reason,
                banduration=banduration
            )
            fullreason = self.getMessage('temp_banned', variables)

        duration = 43200 if int(duration) > 43200 else int(duration)

        self.write(
            self.getCommand(
                'tempban',
                cid=client.cid,
                reason=reason,
                duration=duration
            )
        )

        if not silent and fullreason != '':
            self.say(fullreason)

        self.queueEvent(
            self.getEvent(
                'EVT_CLIENT_BAN_TEMP',
                {
                    'reason': reason,
                    'duration': duration,
                    'admin': admin
                },
                client
            )
        )

        client.disconnect()

    def getPlayerPings(self, filter_client_ids=None):
        """
        Returns a dict having players' id for keys and players' ping for values.
        :param filter_client_ids: If filter_client_id is an iterable, only return values for the given client ids.
        """
        data = self.write('status')

        if not data:
            return {}

        players = {}

        for line in data.split('\n'):
            m = re.match(self._regPlayerShort, line)

            if not m:
                m = re.match(self._regPlayer, line.strip())

            if m:
                players[str(m.group('slot'))] = int(m.group('ping'))

        return players

    def getPlayerScores(self):
        """
        Returns a dict having players' id for keys and players' scores for values.
        """
        data = self.write('status')

        if not data:
            return {}

        players = {}

        for line in data.split('\n'):
            # self.debug('Line: ' + line + "-")
            m = re.match(self._regPlayerShort, line)

            if not m:
                m = re.match(self._regPlayer, line.strip())

            if m:
                players[str(m.group('slot'))] = int(m.group('score'))

            # elif '------' not in line and 'map: ' not in line and 'num score ping' not in line:
            #     self.verbose('getPlayerScores() = Line did not match format: %s' % line)

        return players

    def getPlayerList(self, maxRetries=None):
        """
        Query the game server for connected players.
        Return a dict having players' id for keys and players' data as another dict for values.
        """
        if self.PunkBuster:
            return self.PunkBuster.getPlayerList()

        else:
            data = self.write('status', maxRetries=maxRetries)

            if not data:
                return {}

            players = {}
            lastslot = -1

            for line in data.split('\n')[3:]:
                m = re.match(self._regPlayer, line.strip())

                if m:
                    d = m.groupdict()

                    if int(m.group('slot')) > lastslot:
                        lastslot = int(m.group('slot'))
                        d['pbid'] = None
                        players[str(m.group('slot'))] = d

                    else:
                        self.debug(
                            'Duplicate or incorrect slot number - '
                            'client ignored %s last slot %s' %
                            (m.group('slot'), lastslot)
                        )

        return players

    def getMap(self):
        """
        Return the current map/level name.
        """
        data = self.write('status')
        if not data:
            return None

        for line in data.split('\n'):
            m = re.match(self._reMapNameFromStatus, line.strip())
            if m:
                return str(m.group('map'))

        return None
