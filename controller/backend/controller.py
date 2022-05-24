"""
Controller API

Handle read/write wafer and controller config from client ui.
"""
import time
import traceback
import json
import pyvisa
from flask_restful import Api, Resource, reqparse
from controller.sse import EventChannel


class Controller():
    def __init__(self):
        """Singleton controller for managing instrument resources.
        """
        # py visa resource manager
        self.resource_manager = pyvisa.ResourceManager()
        # b1500 parameter analyzer instrument
        self.instrument_b1500 = None
        # cascade instrument
        self.instrument_cascade = None

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
            "connect_cascade": self.connect_cascade,
            "disconnect_cascade": self.disconnect_cascade,
        }
    
    def connect_b1500(self, gpib_address):
        idn = self.controller.connect_b1500(gpib_address)
        print(idn)

    def disconnect_b1500(self):
        self.controller.disconnect_b1500()

    def connect_cascade(self, gpib_address):
        idn = self.controller.connect_cascade(gpib_address)
        print(idn)
    
    def disconnect_cascade(self):
        self.controller.disconnect_cascade()
    
    def get(self):
        # print("SLEEP?")
        # time.sleep(4)
        # print("WAKE")
        return {
            "resultStatus": "SUCCESS",
            "message": "Hello Api Handler",
        }

    def put(self):
        parser = reqparse.RequestParser()
        parser.add_argument("msg", type=str)
        parser.add_argument("data", type=dict)

        try:
            args = parser.parse_args()
            print(f"PUT {args}")
            if args["msg"] in self.put_handlers:
                kwargs = args["data"]
                self.put_handlers[args["msg"]](**kwargs)
        except Exception as exception:
            print(exception)
            print(traceback.format_exc())
        

    def post(self):
        print(self)

        parser = reqparse.RequestParser()
        parser.add_argument("type", type=str)
        parser.add_argument("message", type=str)

        args = parser.parse_args()

        print(args)
        # note: post req from frontend needs to match strings here

        request_type = args["type"]
        request_json = args["message"]
        # ret_status, ret_msg = ReturnData(request_type, request_json)

        # currently just returning the req straight
        ret_status = request_type
        ret_msg = request_json

        if ret_msg:
            message = f"Your Message Requested: {ret_msg}"
        else:
            message = "No Msg"

        return {
            "status": "Success",
            "message": message,
        }