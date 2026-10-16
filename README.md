# IPerf Agent

## Requirements

 - [Python 3.7.x](https://www.python.org)
 - [iPerf 3](https://iperf.fr)

## Installing (development)

1. Clone the repository to a known folder, e.g. in `c:\malaga-platform` 
2. Enter the folder
```bash
cd c:/malaga-platform/iPerfAgent
```
3. Create a new Python virtualenv:
```bash
pip install virtualenv
virtualenv venv
```
4. Activate the virtual environment:
- For Windows:
```powershell
venv\Scripts\Activate.bat
```
- For Linux:
```bash
source venv/bin/activate
```
5. Install Python dependencies:
```bash
pip install -r requirements.txt
```
6. Start the development server:
```bash
flask run
```
The app will start listening for requests on port 5000.
Press `Control+C` to stop the development server.

## Running with Docker

1. Build the image from the repository root (where the `Dockerfile` is):
```bash
docker build -t p4lik4ri/iperf-app:latest .
```
2. Run it. Each instance exposes two separate ports: `5000` for the
   Flask control API, and `5201` (TCP+UDP) for the actual iPerf3 test
   traffic — they must stay distinct, since iPerf3 always opens a TCP
   control channel first (even for UDP tests) and would otherwise
   conflict with Flask's own listener on the same port:
```bash
docker run -d --name iperf-app \
  -p 5000:5000 \
  -p 5201:5201 \
  -p 5201:5201/udp \
  p4lik4ri/iperf-app:latest \
  flask run -h 0.0.0.0
```
Run the same image on both the server and client hosts; which role
each one plays is decided per-request (see below), not by the
container itself.

## Configuration

The iPerfAgent instance can be configured by editing the `config.yml` file. 

The value that can be configured on `config.yml` is:
* IPERF_PATH: Location of iPerf executable



### Usage

The iPerf Agent exposes a REST API with the following endpoints:
* `/Iperf` **`(POST)`**: Executes iPerf process with the specific parameters in the request body **in JSON format**. Returns a JSON reporting the success of the execution and a message.
* `/Iperf/<pathParameters>`: Executes iPerf process with the specific parameters. Returns a JSON reporting the success of the command execution and a message.
* `/Close`: Closes iPerf process. Returns a JSON reporting the success of the process closure and a message.
* `/LastRawResult`: Retrieve the results of the previous execution. Returns a JSON reporting the success of the retrieval, a message and a list of Results (full line).
* `/LastJsonResult`: Retrieve the results of the previous execution. Returns a JSON reporting the success of the retrieval, a message and a list of Results (dictionary with parsed results).
* `/LastError`: Retrieve the errors of the last execution. Returns a JSON reporting the success of the retrieval and a message informing of the error.
* `/StartDateTime`: Retrieve the date and time of the last execution. Returns a JSON reporting the success of the retrieval, a message and a list of Errors.
* `/IsRunning`: Check if there is another execution running. Returns a JSON reporting the success of the check and a message informing if is running or not.

### Running an experiment via network-monitor

In practice you won't call `/Iperf` directly — the `network-monitor`
service orchestrates both the server and client iPerf Agent instances
for you. With both agents running (see "Running with Docker" above)
and `network-monitor` up on port `8000`, start an experiment with:
```bash
curl -X POST "http://localhost:8000/start-experiment" \
     -H "Content-Type: application/json" \
     -d '{
         "server_ip": "10.220.2.81:5000",
         "server_params": "-i 1 -u -s -p 5201",
         "client_ip": "10.45.112.115:5000",
         "client_params": "-b 3G -i 1 -u",
         "duration": 25,
         "repeat": 1
     }'
```
`server_ip`/`client_ip` are each agent's Flask control API address.
`-p 5201` in `server_params` sets the actual iPerf3 test port (shown
explicitly above); it's optional and defaults to `5201` if omitted.

## Authors

* **Gonzalo Chica Morales**
* **Bruno Garcia Garcia**

## License

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   > <http://www.apache.org/licenses/LICENSE-2.0>

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

