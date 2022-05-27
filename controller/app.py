import os
import json
import logging
import numpy as np
from flask import Flask, request
from flask_restful import Api, Resource, reqparse
from flask_cors import CORS # disable on deployment
from gevent.pywsgi import WSGIServer
import gevent
import sse
from controller.util import timestamp_date
from controller.backend import Controller, ControllerSettings, ControllerApiHandler, UserProfile, MonitorApiHandler


def save_default_settings(path_settings):
    """Create default setting files in data path."""
    controller_settings = ControllerSettings.default()
    with open(os.path.join(path_settings, "config.json"), "w+") as f:
        json.dump(controller_settings.__dict__, f, indent=2)
    
    # save default individual user settings
    path_users = os.path.join(path_settings, "users")
    os.makedirs(path_users, exist_ok=True)

    for username in controller_settings.users:
        UserProfile.default(username).save(path_users)


def create_server(
    path_settings,
    cors=True,
):
    """Create controller server and controller state.
    """

    # create settings folder if does not exist
    path_controller_settings = os.path.join(path_settings, "config.json")
    if not os.path.exists(path_controller_settings):
        logging.info(f"Generating new default config in settings path: \"{path_settings}\"")
        save_default_settings(path_settings)
    
    # users path
    path_users = os.path.join(path_settings, "users")

    # pyvisa controller backend
    controller = Controller(
        path_settings=path_controller_settings,
        path_users=path_users,
    )

    # flask web server as controller api interface
    app = Flask(__name__)

    if cors:
        CORS(app)

    # event channels
    channel = sse.EventChannel()
    channel_controller = sse.EventChannel()
    channel_monitor = sse.EventChannel()

    # temp: for testing
    def long_repeating_task():
        i = 0
        while True:
            x = np.arange(16)
            y = np.sin(i + x)
            channel.publish({
                "x": x.tolist(),
                "y": y.tolist(),
            })
            i += 1
            gevent.sleep(0.1)

    t = gevent.spawn(long_repeating_task)

    @app.route("/subscribe")
    def subscribe():
        return channel.subscribe()

    @app.route("/publish", methods=["POST"])
    def publish():
        channel.publish(request.data)
        return "OK"

    @app.route("/")
    def index():
        return """<body><script>
    var eventSource = new EventSource('/subscribe');
    eventSource.onmessage = function(m) {
        console.log(m);
        var el = document.getElementById('messages');
        el.innerHTML += m.data;
        el.innerHTML += '</br>';
    }
    function post(url, data) {
        var request = new XMLHttpRequest();
        request.open('POST', url, true);
        request.setRequestHeader('Content-Type', 'text/plain; charset=UTF-8');
        request.send(data);
    }
    function publish() {
        var message = document.getElementById('msg').value;
        post('/publish', message);
    }
    </script>
    <input type='text' id='msg'>
    <button onclick='publish()'>send</button>
    <p id='messages'></p>
    </body>"""

    @app.route("/event/controller")
    def event_controller():
        return channel_controller.subscribe()
    
    @app.route("/event/monitor")
    def event_monitor():
        return channel_monitor.subscribe()
    
    api = Api(app)

    api.add_resource(ControllerApiHandler, "/api/controller", resource_class_kwargs={
        "channel": channel_controller,
        "monitor_channel": channel_monitor,
        "controller": controller,
    })
    api.add_resource(MonitorApiHandler, "/api/monitor", resource_class_kwargs={
        "channel": channel_monitor,
    })

    return app


def run(
    port=9000,
    path_settings="./settings",
):
    """Wrapper to run server on a port.
    """
    # setup logging
    logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.DEBUG)

    os.makedirs("logs", exist_ok=True)
    logFileHandler = logging.FileHandler(f"logs/{timestamp_date()}.log", mode="a", encoding=None, delay=False)
    logFileHandler.setLevel(logging.DEBUG)
    logFileHandler.setFormatter(logFormatter)
    rootLogger.addHandler(logFileHandler)

    logConsoleHandler = logging.StreamHandler()
    logConsoleHandler.setLevel(logging.DEBUG)
    logConsoleHandler.setFormatter(logFormatter)
    rootLogger.addHandler(logConsoleHandler)

    logging.info("============================================================")
    logging.info("RUNNING GAX 9000")
    logging.info("============================================================")
    logging.info(f"Settings path: \"{path_settings}\"")
    
    # create and run server app
    app = create_server(
        path_settings=path_settings,
    )

    # ssl cert.pem and key.pem file paths
    path_cert = os.path.join(path_settings, "ssl", "cert.pem")
    path_key = os.path.join(path_settings, "ssl", "key.pem")

    server = WSGIServer(("", port), app, certfile=path_cert, keyfile=path_key)
    logging.info(f"Controller server listening on port: {port}")
    server.serve_forever()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run gax controller server.")

    parser.add_argument(
        "path_settings",
        metavar="path_settings",
        type=str,
        help="Controller config data path"
    )
    parser.add_argument(
        "--port",
        dest="port",
        metavar="port",
        type=int,
        default=9000,
        help="Controller config data path"
    )

    args = vars(parser.parse_args())

    run(**args)
