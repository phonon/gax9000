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

4. Install frontend packages
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