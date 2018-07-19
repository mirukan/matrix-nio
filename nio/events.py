# -*- coding: utf-8 -*-

# Copyright © 2018 Damir Jelić <poljar@termina.org.uk>
#
# Permission to use, copy, modify, and/or distribute this software for
# any purpose with or without fee is hereby granted, provided that the
# above copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER
# RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF
# CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
# CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

from builtins import super
from logbook import Logger
from jsonschema.exceptions import SchemaError, ValidationError
from typing import *

from .api import Api
from .log import logger_group
from .schemas import validate_json, Schemas

logger = Logger('nio.responses')
logger_group.add_logger(logger)


class Event(object):
    def __init__(self, event_id, sender, server_ts):
        # type: (str, str, int) -> None
        self.event_id = event_id
        self.sender = sender
        self.server_timestamp = server_ts


class BadEvent(Event):
    def __init__(self, event_id, sender, server_ts, event_type, source):
        # type: (str, str, int, str, str) -> None
        self.source = source
        self.type = event_type
        super().__init__(event_id, sender, server_ts)

    def __str__(self):
        return "Bad event of type {}, from {}.".format(
            self.sender,
            self.type
        )

    @classmethod
    def from_dict(cls, parsed_dict):
        return cls(
            parsed_dict["event_id"],
            parsed_dict["sender"],
            parsed_dict["origin_server_ts"],
            parsed_dict["type"],
            Api.to_json(parsed_dict)
        )


class RedactedEvent(Event):
    def __init__(
        self,
        event_id,    # type: str
        sender,      # type: str
        server_ts,   # type: int
        event_type,  # type: str
        redacter,    # type: str
        reason=None  # type: Optional[str]
    ):
        # type: (...) -> None
        self.event_type = event_type
        self.redacter = redacter
        self.reason = reason
        super().__init__(event_id, sender, server_ts)

    def __str__(self):
        reason = ", reason: {}".format(self.reason) if self.reason else ""
        return "Redacted event of type {}, by {}{}.".format(
            self.event_type,
            self.redacter,
            reason
        )

    @classmethod
    def from_dict(cls, parsed_dict):
        try:
            validate_json(parsed_dict, Schemas.redacted_event)
        except (ValidationError, SchemaError):
            return BadEvent.from_dict(parsed_dict)

        redacter = parsed_dict["unsigned"]["redacted_because"]["sender"]
        content_dict = parsed_dict["unsigned"]["redacted_because"]["content"]
        reason = content_dict["reason"] if "reason" in content_dict else None

        return cls(
            parsed_dict["event_id"],
            parsed_dict["sender"],
            parsed_dict["origin_server_ts"],
            parsed_dict["type"],
            redacter,
            reason
        )


class RoomMessage(Event):
    @staticmethod
    def from_dict(parsed_dict, olm=None):
        # type: (Dict[Any, Any], Any) -> Union[Event, BadEvent]
        try:
            validate_json(parsed_dict, Schemas.room_message)
        except (SchemaError, ValidationError):
            return BadEvent.from_dict(parsed_dict)

        content_dict = parsed_dict["content"]

        if content_dict["msgtype"] == "m.text":
            return RoomMessageText.from_dict(parsed_dict)

        # TODO return unknown msgtype event
        return None


class RoomMessageText(Event):
    def __init__(
        self,
        event_id,        # type: str
        sender,          # type: str
        server_ts,       # type: int
        body,            # type: str
        formatted_body,  # type: Optional[str]
        body_format      # type: Optional[str]
    ):
        # type: (...) -> None
        super().__init__(event_id, sender, server_ts)
        self.body = body
        self.formatted_body = formatted_body
        self.format = body_format

    def __str__(self):
        # type: () -> str
        return "{}: {}".format(self.sender, self.body)

    @classmethod
    def from_dict(cls, parsed_dict):
        # type: (Dict[Any, Any]) -> Union[RoomMessageText, BadEvent]
        try:
            validate_json(parsed_dict, Schemas.room_message_text)
        except (SchemaError, ValidationError):
            return BadEvent.from_dict(parsed_dict)

        body = parsed_dict["content"]["body"]
        formatted_body = (parsed_dict["content"]["formatted_body"] if
                          "formatted_body" in parsed_dict["content"] else None)
        body_format = (parsed_dict["content"]["format"] if
                       "format" in parsed_dict["content"] else None)

        return cls(
            parsed_dict["event_id"],
            parsed_dict["sender"],
            parsed_dict["origin_server_ts"],
            body,
            formatted_body,
            body_format
        )