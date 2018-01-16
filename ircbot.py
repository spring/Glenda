#! /usr/bin/env python

import sys
import pprint

from io import StringIO

import irc.bot
import irc.strings
from irc.client import ip_numstr_to_quad, ip_quad_to_numstr


class IrcBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channels, domain, username, nickname, server, password, client, rooms, rooms_id, bot_owner,
                 port=6667):

        spec = irc.bot.ServerSpec(server, port=port, password=password)
        irc.bot.SingleServerIRCBot.__init__(self, [spec], nickname, nickname)

        self.pp = pprint.PrettyPrinter(indent=4)

        self.domain = domain

        self.bot_owner = bot_owner
        self.username = username

        self.channel_list = channels

        self.client = client
        self.rooms = rooms
        self.rooms_id = rooms_id

        for name, room in self.rooms.items():
            self.rooms[name].add_listener(self.on_matrix_msg)

        self.client.start_listener_thread()

    def on_matrix_msg(self, room, event):

        if event['type'] == "m.room.message":
            if event['sender'] != f"@{self.username}:{self.domain}":
                if event['content']['msgtype'] == "m.image":
                    
                    # self.pp.pprint(event)

                    for channel, room_id in self.rooms_id.items():
                        if event['room_id'] in room_id[1]:
                            url = f"https://{self.domain}/_matrix/media/v1/download/{self.domain}/"
                            mxc_url = event['content']['url']
                            pic_code = mxc_url[-24:]
                            pic_url = f"{url}{pic_code}"
                            sender = event['sender'].split(":", 1)[0]
                            msg = f"<{sender}> {pic_url}"

                            self.connection.privmsg(channel, msg)

                if event['content']['msgtype'] == "m.text":
                    for channel, room_id in self.rooms_id.items():
                        if event['room_id'] in room_id[1]:
                            buf = StringIO(event['content']['body'])
                            for line in buf.read().splitlines():
                                sender = event['sender'].split(":", 1)[0]
                                self.connection.privmsg(channel, f"<{sender}> {line}")

                if event['content']['msgtype'] == "m.emote":
                    for channel, room_id in self.rooms_id.items():
                        if event['room_id'] in room_id[1]:
                            buf = StringIO(event['content']['body'])
                            for line in buf.read().splitlines():
                                sender = event['sender'].split(":", 1)[0]
                                self.connection.privmsg(channel, f"<<{sender}>> {line}")
        else:
            print(event['type'])

    def on_nicknameinuse(self, c, e):
        # c.nick(c.get_nickname() + "_")
        print(f"nick {c.get_nickname()} name in used")
        sys.exit(1)

    def on_welcome(self, c, e):
        for channel in self.channel_list:
            c.join(channel)

    def on_privmsg(self, c, e):
        self.do_command(e, e.arguments[0])

    def on_pubmsg(self, c, e):

        msg = e.arguments[0]
        source = e.source.split("!", 1)[0]

        print(msg, source)

        if "Nightwatch" in source:
            self.rooms[f"{e.target}"].send_text(f"{msg}")
        else:
            self.rooms[f"{e.target}"].send_text(f"[{source}] {msg}")

        return

    def on_action(self, c, e):

        msg = e.arguments[0]
        source = e.source.split("!", 1)[0]

        if "Nightwatch" in source:
            self.rooms[f"{e.target}"].send_text(f"*{msg}")
        else:
            self.rooms[f"{e.target}"].send_text(f"*{source} {msg}")

    def on_dccmsg(self, c, e):
        # non-chat DCC messages are raw bytes; decode as text
        text = e.arguments[0].decode('utf-8')
        c.privmsg("You said: " + text)

    def on_dccchat(self, c, e):
        if len(e.arguments) != 2:
            return
        args = e.arguments[1].split()
        if len(args) == 4:
            try:
                address = ip_numstr_to_quad(args[2])
                port = int(args[3])
            except ValueError:
                return
            self.dcc_connect(address, port)

    def do_command(self, e, cmd):
        nick = e.source.nick
        c = self.connection

        if cmd == "disconnect":
            if nick == self.bot_owner:
                self.disconnect()
            else:
                c.privmsg(nick, "you are not the bot owner")

        elif cmd == "die":
            if nick == self.bot_owner:
                self.die()
            else:
                c.privmsg(nick, "you are not the bot owner")

        elif cmd == "stats":
            for chname, chobj in self.channels.items():
                c.privmsg(nick, "--- Channel statistics ---")
                c.privmsg(nick, "Channel: {0}".format(chname))
                users = sorted(chobj.users())
                c.privmsg(nick, "Users: {0}".format(", ".join(users)))
                opers = sorted(chobj.opers())
                c.privmsg(nick, "Opers: {0}".format(", ".join(opers)))
                voiced = sorted(chobj.voiced())
                c.privmsg(nick, "Voiced: {0}".format(", ".join(voiced)))

        elif cmd == "dcc":
            if nick == self.bot_owner:
                dcc = self.dcc_listen()
                c.ctcp("DCC", nick, "CHAT chat {0} {1}".format(
                    ip_quad_to_numstr(dcc.localaddress),
                    dcc.localport))
            else:
                c.privmsg(nick, "you are not the bot owner")

        else:
            c.privmsg(nick, "Not understood: {0}".format(cmd))
