# gax9000: Wafer Auto-Probe Measurement Controller

Controller for MIT novels group auto probe station. Manages measurements
with B1500A Semiconductor Parameter Analyzer and Cascade Summit 12000
auto-probe station.


# Repo structure
```
gax9000/
 ├─ controller/   - Python backend instrument controller
 └─ frontend/     - JS frontend controller and monitor
```


# Setup/Installation
1.  Create python virtual environment
```
python -m venv venv
```

2.  Start environment
```
(Windows)
source venv/Scripts/active
```

3.  Install python requirements
```
pip install -r requirements.txt
```

4.  Install controller backend as a pip package (required for scripts to find `controller` as dependency):
```
pip install -e .
```

5. Install frontend web ui packages
```
cd frontend
npm install
```

# Usage
First run server using script
```
./run.sh 
```
This will by default use `./data` as the real instance data folder.
The first time the server is run, it will copy default config files
in `controller/assets/` into the data folder.

# Architecture
Python backend controller manages the instrument GPIB connections
and acts as a web server. The javascript frontend both acts to
update backend controller settings and run measurements, and 
reads real-time signals from controller web server (using SSE) and
reports measurement results.

# Issues
## Antivirus blocking SSE
Sophos antivirus (used by MIT) blocks SSE in python web apps from
regular http requests. It treats the SSE stream as a download that
needs to be scanned. It waits until a 2 MB block is downloaded before
scanning...issue is SSE events are small and unlikely to fill the 2 MB
buffer. There are 2 solutions
1.  Send a single 2 MB block before first event (to break through
    Sophos cancer).
2.  Use https (SSL/TLS)

https://stackoverflow.com/questions/62129788/on-a-machine-running-sophos-why-do-all-my-browsers-fail-to-receive-server-sent

## Generating self-signed SSL Certificate
See:
https://security.stackexchange.com/questions/74345/provide-subjectaltname-to-openssl-directly-on-the-command-line/198409#198409