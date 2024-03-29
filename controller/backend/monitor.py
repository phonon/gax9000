"""
Monitor API

Handle viewing and sending current measurement data results
to client monitor.
"""
import gevent
from flask_restful import Api, Resource, reqparse


class MonitorApiHandler(Resource):
    def __init__(self, channel):
        # SSE event channel for pushing data responses to frontend
        self.channel = channel
    
    def get(self):
        print("SLEEP?")
        gevent.sleep(4)
        print("WAKE")

        return {
            "resultStatus": "SUCCESS",
            "message": "Hello Api Handler",
        }

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