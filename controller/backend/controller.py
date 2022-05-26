"""
Controller API

Handle read/write wafer and controller config from client ui.
"""
import time
import os
import logging
import traceback
import json
import gevent
import pyvisa
from flask_restful import Api, Resource, reqparse
from controller.sse import EventChannel


class UserGlobalSettings():
    """Saved user global config settings."""
    def __init__(
        self,
        username,
        die_size_x=10000,
        die_size_y=10000,
        die_offset_x=0,
        die_offset_y=0,
        current_die_x=0,
        current_die_y=0,
        device_x=0,
        device_y=0,
        device_row=0,
        device_col=0,
        data_folder="",
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
        self.device_row = device_row
        self.device_col = device_col
        self.data_folder = data_folder
    
    def default(username):
        """Default settings."""
        return UserGlobalSettings(
            username=username,
        )


class UserProfile():
    """Contain all user settings. Used as an intermediate cache
    before periodically saving dirty settings to disk."""
    def __init__(
        self,
        global_settings,
        program_settings = {},
        measurement_settings = {}
    ):
        self.global_settings = global_settings
        self.program_settings = program_settings
        self.measurement_settings = measurement_settings
        self.dirty_global_settings = False
        self.dirty_program_settings = set()     # set of dirty program name strings
        self.dirty_measurement_settings = set() # set of dirty measurement sweep name strings
    
    def default(username):
        """Create user profile with default settings."""
        return UserProfile(
            global_settings=UserGlobalSettings.default(username),
            program_settings={}, # TODO
            measurement_settings={}, # TODO
        )
    
    def save(self, path):
        """Save settings to path.
        Inputs:
        - path: Folder containing all individual user folders, e.g. "settings/users/".
        Returns:
        - True if any settings were dirty and saved, False if not.
        """
        path_user = os.path.join(path, self.global_settings.username)
        os.makedirs(path_user, exist_ok=True)

        did_update = False

        path_global_settings = os.path.join(path_user, "settings.json")
        path_program_settings_dir = os.path.join(path_user, "programs")
        path_measurement_settings_dir = os.path.join(path_user, "measurements")

        if self.dirty_global_settings or not os.path.exists(path_global_settings):
            with open(path_global_settings, "w+") as f:
                json.dump(self.global_settings.__dict__, f, indent=2)
            did_update = True

        # NOTE: here we only save names of program and measurement settings
        # that were dirty (as in used by the user). So these are all lazily saved.
        # If the user never uses a program, its settings will never be saved.
        
        if len(self.dirty_program_settings) > 0:
            if not os.path.exists(path_program_settings_dir):
                os.makedirs(path_program_settings_dir, exist_ok=True)
            
            for program_name, program_settings in self.program_settings.items():
                # TODO
                pass
            did_update = True
            
        if len(self.dirty_measurement_settings) > 0:
            if not os.path.exists(path_measurement_settings_dir):
                os.makedirs(path_measurement_settings_dir, exist_ok=True)
            
            for measurement_name, measurement_settings in self.measurement_settings.items():
                # TODO
                pass
            did_update = True
        
        # clear dirty flags
        self.dirty_global_settings = False
        self.dirty_program_settings = set()
        self.dirty_measurement_settings = set()
        
        return did_update

    def load(path_users, username):
        """Return new user profile settings object from data in path.
        If files are missing, this will create default settings objects.
        Inputs:
        - path_users: Folder for all users, e.g. "settings/users/"
        - username: Name of user to load settings for. User settings path
            is by joining `path_users + username`.
        """
        # derive username from directory in path
        path = os.path.join(path_users, username)

        path_global_settings = os.path.join(path, "settings.json")
        path_program_settings_dir = os.path.join(path, "programs")
        path_measurement_settings_dir = os.path.join(path, "measurements")
        
        if os.path.exists(path_global_settings):
            with open(path_global_settings, "r") as f:
                global_settings = UserGlobalSettings(**json.load(f))
        else:
            global_settings = UserGlobalSettings.default(username)
        
        return UserProfile(
            global_settings=global_settings,
            program_settings={}, # TODO
            measurement_settings={}, # TODO
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
        # repeating task to save user settings
        self.task_save_user_settings = gevent.spawn(self._task_save_user_settings)
    
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
            if os.path.exists(path_user):
                self.users[username] = UserProfile.load(self.path_users, username)
            else: # generate default user settings
                logging.info(f"Creating default user settings for {username} at: {path_user}")
                self.users[username] = UserProfile.default(username)
                self.users[username].save(self.path_users)
        
        return self.users[username].global_settings

    def save_user_settings(self):
        """Saves dirty user settings to .json files storage."""
        for username, user in self.users.items():
            if user.save(self.path_users):
                logging.info(f"Saved user settings: {username}")
        
    def _task_save_user_settings(self):
        """Internal task that runs in gevent greenlet to periodically
        save dirty user settings."""
        while True:
            self.save_user_settings()
            gevent.sleep(10.0) # currently hardcoded save every 10s
    
    def set_user_setting(self, user, setting, value):
        """Set user global setting.
        This will mark the user settings as dirty.
        """
        if user in self.users:
            if hasattr(self.users[user].global_settings, setting):
                self.users[user].global_settings.__setattr__(setting, value)
                self.users[user].dirty_global_settings = True
            else:
                logging.warn(f"set_user_setting() Invalid setting: {setting}")
        else:
            logging.warn(f"set_user_setting() Invalid user: {user}")

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
            "set_user_setting": self.set_user_setting,
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
    
    def set_user_setting(self, user, setting, value):
        """Update a user setting to new value."""
        self.controller.set_user_setting(user, setting, value)
    
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
        