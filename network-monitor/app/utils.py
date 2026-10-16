'''
Common utils module
'''

import logging
import os
import httpx
from pydantic import BaseModel


class ExperimentData(BaseModel):
    """
    Model for endpoint input data
    """
    server_ip: str
    server_params: str
    client_ip: str
    client_params: str
    duration: int = 20
    repeat: int = 1


def parse_input_string(input_string: str) -> dict:
    """
    Parse input string into a dictionary.

    Example:
        Input: '-i 1 -t 20 -u -s'
        Output: {"-i": 1, "-t": "20", "-u": "", "-s": ""}
    """
    if not input_string:
        return {}

    parts = input_string.split()
    result = {}
    i = 0

    while i < len(parts):
        key = parts[i]
        if key.startswith('-'):  # It's a key (flag)
            # Check if the next element is a value or another flag
            if i + 1 < len(parts) and not parts[i + 1].startswith('-'):
                value = parts[i + 1]
                i += 1
            else:
                value = ""  # No value, assign an empty string
            result[key] = int(value) if value.isdigit() else value
        i += 1

    return result


def params_dict_to_string(params: dict) -> str:
    """
    Serialize a parsed params dict back into an iPerf CLI-style string.
    """
    return " ".join(
        f"{flag} {value}" if value != "" else flag
        for flag, value in params.items()
    )


def set_duration_param(params: str, duration: int) -> str:
    """
    Override (or append) the "-t" flag in an iPerf parameter string so
    it reflects the given duration in seconds.
    """
    parsed = parse_input_string(params)
    parsed["-t"] = int(duration)
    return params_dict_to_string(parsed)


def split_host_port(address: str) -> tuple:
    """
    Split a "host" or "host:port" address into (host, port). "port" is
    None when the address doesn't include one.
    """
    host, _, port = address.partition(":")
    return host, (port or None)


# iPerf3's own conventional default port. "server_ip"/"client_ip" are
# the Flask control API's address (commonly port 5000), which iPerf3
# can't also share for its test traffic (it always opens a TCP control
# channel first, even for UDP tests, so reusing the same port would
# conflict with Flask's own listener). This is used as the iPerf test
# port whenever "server_params" doesn't set "-p" explicitly.
DEFAULT_IPERF_PORT = "5201"


def apply_server_target(server_params: str, client_params: str,
                         server_ip: str) -> tuple:
    """
    Business logic: "server_ip" is the single source of truth for where
    the iPerf test itself runs, so callers never need to repeat its
    host again inside server_params/client_params. This derives the
    host from "server_ip" and always sets it as "-c" in client_params.
    The port is resolved once (an explicit "-p" already in
    server_params wins, otherwise DEFAULT_IPERF_PORT is used) and
    applied identically to both server_params and client_params, so the
    two sides can never end up with mismatched ports.
    """
    host, _ = split_host_port(server_ip)

    server_dict = parse_input_string(server_params)
    client_dict = parse_input_string(client_params)

    port = server_dict.get("-p") or DEFAULT_IPERF_PORT
    server_dict["-p"] = port

    client_dict["-c"] = host
    client_dict["-p"] = port

    return (params_dict_to_string(server_dict),
            params_dict_to_string(client_dict))


def is_reverse_mode(client_params: str) -> bool:
    """
    Check whether "-R" (reverse mode) is set in the client params.
    In reverse mode the server sends and the client receives, so the
    client becomes the host that actually measures the test results.
    """
    return "-R" in parse_input_string(client_params)


def compute_loop_duration(duration: int) -> int:
    """
    Business logic: the loop duration is the base experiment duration
    plus a 2s buffer, so callers never need to pass it explicitly.
    """
    return int(duration) + 2


def get_app_logger():
    """
    Set up and return the application logger.
    """
    logger = logging.getLogger('iperf')
    if not logger.hasHandlers():
        logger.setLevel(logging.DEBUG)

        # Define log format
        formatter = logging.Formatter(
            '%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d:%H:%M:%S'
        )

        # Console stream handler
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger



def compile_experiment_data() -> ExperimentData:
    """
    Compile experiment data from environment variables.
    Defaults are used if environment variables are not set.
    Flags that can be used in iPerf3:
        "--bitrate": "-b",
        "--bind": "-B",
        "--client": "-c",
        "--format": "-f",
        "--interval": "-i",
        "--length": "-l",
        "--set-mss": "-M",
        "--no-delay": "-N",
        "--port": "-p",
        "--parallel": "-P",
        "--reverse": "-R",
        "--tos": "-S",
        "--time": "-t",
        "--udp": "-u",
        "--window": "-w"
    """
    server_ip = os.getenv("iPERF_SERVER_IP", "iperf-server:5000")
    client_ip = os.getenv("iPERF_CLIENT_IP", "iperf-client:5000")
    server_params = os.getenv("iPERF_SERVER_PARAMS", "-i 1 -t 20 -u -s")
    client_params = os.getenv("iPERF_CLIENT_PARAMS", f"-c {server_ip} -b 5M -u -t 18")
    duration = int(os.getenv("iPERF_DURATION", 20))
    repeat = int(os.getenv("iPERF_REPEAT", 1))

    return ExperimentData(
        server_ip=server_ip,
        server_params=server_params,
        client_ip=client_ip,
        client_params=client_params,
        duration=duration,
        repeat=repeat
    )


async def exp_runner():
    """
    Caller function to invoke the start-experiment endpoint.
    Logs the experiment data and handles potential request errors.
    """
    logger = get_app_logger()
    experiment_data = compile_experiment_data()
    logger.info("Initial data: %s", experiment_data.model_dump_json())

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url="http://localhost:8000/start-experiment",
                json=experiment_data.model_dump()
            )
            logger.info("Response status: %s", response.status_code)
            logger.info("Response content: %s", response.text)
    except httpx.TimeoutException as e:
        logger.error("Request timed out: %s", str(e))
    except httpx.RequestError as e:
        logger.error("Request error occurred: %s", str(e))
    except Exception as e:
        logger.error("Unexpected error: %s", str(e))
