"""
Controller API

Handle read/write wafer and controller config from client ui.
"""
import time
import os
import logging
import traceback
import json
import pyvisa
from flask_restful import Api, Resource, reqparse
from controller.sse import EventChannel


class UserProfile():
    """Saved user settings."""
    def __init__(
        self,
        username,
        die_size_x,
        die_size_y,
        die_offset_x,
        die_offset_y,
        current_die_x,
        current_die_y,
        device_x,
        device_y,
        data_folder,
    ):
        self.username = username
        self.die_size_x = die_size_x
        self.die_size_y = die_size_y
        self.die_offset_x = die_offset_x
        self.die_offset_y = die_offset_y
        self.current_die_x = current_die_x
        self.current_die_y = current_die_y
        self.device_x = device_x
        self.device_y = device_y
        self.data_folder = data_folder
    
    def default(username):
        """Default settings."""
        return UserProfile(
            username=username,
            die_size_x=10000,
            die_size_y=10000,
            die_offset_x=0,
            die_offset_y=0,
            current_die_x=0,
            current_die_y=0,
            device_x=0,
            device_y=0,
            data_folder="",
        )


class ControllerSettings():
    """Global controller settings. These are saved each time
    value is changed.
    """
    def __init__(
        self,
        gpib_b1500: int,
        gpib_cascade: int,
        users: list,
    ):
        self.gpib_b1500 = gpib_b1500
        self.gpib_cascade = gpib_cascade
        self.users = users

    def default():
        """Return a default settings object."""
        return ControllerSettings(
            gpib_b1500=16,
            gpib_cascade=22,
            users=["public"],
        )


class Controller():
    def __init__(
        self,
        path_settings: str,
        path_users: str,
    ):
        """Singleton controller for managing instrument resources.
        """
        # py visa resource manager
        self.resource_manager = pyvisa.ResourceManager()
        # b1500 parameter analyzer instrument
        self.instrument_b1500 = None
        # cascade instrument
        self.instrument_cascade = None
        # controller global settings
        self.path_settings = path_settings
        # do initial controller settings load
        self.load_settings()
        # controller user settings path
        self.path_users = path_users
        # user settings, maps username: str => UserProfile: class
        self.users = {}

    def load_settings(self):
        """Load controller settings from file."""
        with open(self.path_settings, "r") as f:
            self.settings = ControllerSettings(**json.load(f))
    
    def save_settings(self):
        """Save controller settings to file."""
        with open(self.path_settings, "w+") as f:
            json.dump(self.settings.__dict__, f, indent=2)

    def get_user_settings(self, username):
        """Get user settings.
        If it doesn't exist, load data from saved user `settings.json`.
        If saved settings json file does not exist, save default user
        settings first.
        """
        if username not in self.users:
            path_user = os.path.join(self.path_users, username)
            path_user_settings = os.path.join(path_user, "settings.json")
            if os.path.exists(path_user_settings):
                with open(path_user_settings, "r") as f:
                    self.users[username] = UserProfile(**json.load(f))
            else: # generate default user settings
                logging.info(f"Creating default user settings for {username} at: {path_user_settings}")
                self.users[username] = UserProfile.default(username)
                os.makedirs(path_user, exist_ok=True)
                with open(path_user_settings, "w+") as f:
                    json.dump(self.users[username].__dict__, f, indent=2)
        
        return self.users[username]

    def connect_b1500(self, gpib: int):
        """Connect to b1500 instrument resource through GPIB
        and return identification string."""
        addr = f"GPIB0::{gpib}::INSTR"
        self.instrument_b1500 = self.resource_manager.open_resource(addr)
        return self.instrument_b1500.query("*IDN?")

    def disconnect_b1500(self):
        """Disconnect from b1500 instrument."""
        pass

    def connect_cascade(self, gpib: int):
        """Connect to cascade instrument resource through GPIB
        and return identification string."""
        addr = f"GPIB0::{gpib}::INSTR"
        self.instrument_cascade = self.resource_manager.open_resource(addr)
        return self.instrument_cascade.query("*IDN?")

    def disconnect_cascade(self):
        """Disconnect from cascade instrument."""
        pass


class ControllerApiHandler(Resource):
    def __init__(
        self,
        channel: EventChannel,
        controller: Controller,
    ):
        # SSE event channel for pushing data responses to frontend
        self.channel = channel
        # instrument controller class
        self.controller = controller
        # put request handlers
        self.put_handlers = {
            "connect_b1500": self.connect_b1500,
            "disconnect_b1500": self.disconnect_b1500,
            "set_b1500_gpib_address": self.set_b1500_gpib_address,
            "connect_cascade": self.connect_cascade,
            "disconnect_cascade": self.disconnect_cascade,
            "get_user_settings": self.get_user_settings,
        }
    
    def connect_b1500(self, gpib_address):
        idn = self.controller.connect_b1500(gpib_address)
        logging.info(f"Connected (GPIB: {gpib_address}): {idn}")
        self.channel.publish({
            "msg": "connect_b1500_idn",
            "data": {
                "idn": idn,
            },
        })

    def disconnect_b1500(self):
        self.controller.disconnect_b1500()
        self.channel.publish({
            "msg": "disconnect_b1500",
            "data": {},
        })

    def set_b1500_gpib_address(self, gpib_address):
        """Set B1500 GPIB address setting."""
        self.controller.settings.gpib_b1500 = gpib_address
        self.controller.save_settings()
    
    def connect_cascade(self, gpib_address):
        idn = self.controller.connect_cascade(gpib_address)
        logging.info(f"Connected (GPIB: {gpib_address}): {idn}")
        self.channel.publish({
            "msg": "connect_cascade_idn",
            "data": {
                "idn": idn,
            },
        })
    
    def disconnect_cascade(self):
        self.controller.disconnect_cascade()
        self.channel.publish({
            "msg": "disconnect_cascade",
            "data": {},
        })

    def set_cascade_gpib_address(self, gpib_address):
        """Set Cascade GPIB address setting."""
        self.controller.settings.gpib_cascade = gpib_address
        self.controller.save_settings()
    
    def get_user_settings(self, user):
        """Get user settings."""
        user_settings = self.controller.get_user_settings(user)
        self.channel.publish({
            "msg": "set_user_settings",
            "data": {
                "settings": user_settings.__dict__,
            },
        })
    
    def get(self):
        """Returns global controller config settings."""
        # reload controller settings on page load
        self.controller.load_settings()
        return {
            "gpib_b1500": self.controller.settings.gpib_b1500,
            "gpib_cascade": self.controller.settings.gpib_cascade,
            "users": self.controller.settings.users
        }

    def put(self):
        """Main handler for updating global config or user profile data.
        Put requests are all in format:
            {
                "msg": "request_event",
                "data": { ... },
            }
        where "msg" routes to the event handler and "data" contains
        the event handler function inputs.
        """
        parser = reqparse.RequestParser()
        parser.add_argument("msg", type=str)
        parser.add_argument("data", type=dict)

        try:
            args = parser.parse_args()
            logging.info(f"PUT {args}")
            if args["msg"] in self.put_handlers:
                kwargs = args["data"]
                self.put_handlers[args["msg"]](**kwargs)
        except Exception as exception:
            logging.error(exception)
            logging.error(traceback.format_exc())
        