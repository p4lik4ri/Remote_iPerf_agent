'''
API to set and run network performance.
Works with Open5Genesis iPerf flask based app
Access iperf servers and configure one as server and one as client 
Expected environment variables:
    server_ip: the ip of the flask server to expose iperf server
    server_params: iperf server configuration str
    client_ip: the ip of the flask client to execute iperf client
    client_params: iperf client configuration str
    repeat: numer of experiment loops
'''

import asyncio
import os
import json
import httpx
from fastapi import APIRouter, HTTPException
import app.utils as utils
from app.influxdb import write_to_influxdb


# File to store results
RESULTS_FILE = "experiment_results.json"

# Initialize the results file
if not os.path.exists(RESULTS_FILE):
    with open(RESULTS_FILE, "w") as f:
        json.dump([], f)

router = APIRouter()

logger = utils.get_app_logger()



############### App endpoints ###############
@router.post("/start-experiment")
async def start_experiment(experiment_data: utils.ExperimentData):
    """Start the experiment using provided data."""
    results = []

    try:
        # Business logic: normalize "-t" in both param strings from the
        # single "duration" field (client gets a 2s head start to finish).
        server_params = utils.set_duration_param(
            experiment_data.server_params, experiment_data.duration)
        client_params = utils.set_duration_param(
            experiment_data.client_params, experiment_data.duration - 2)

        # Business logic: "server_ip" is the single source of truth for
        # the iPerf test's host/port, so callers never need to repeat
        # it as "-c"/"-p" inside server_params/client_params.
        server_params, client_params = utils.apply_server_target(
            server_params, client_params, experiment_data.server_ip)

        # Reset any lingering iPerf process (e.g. a previous run that
        # never received traffic and got stuck "running" forever) on
        # both hosts before starting, so this call isn't rejected with
        # "iPerf already running".
        await close_iperf(experiment_data.server_ip)
        await close_iperf(experiment_data.client_ip)

        # In reverse mode ("-R") the client receives and measures the
        # test, so results must be polled from the client instead.
        results_host = (
            experiment_data.client_ip
            if utils.is_reverse_mode(client_params)
            else experiment_data.server_ip
        )

        for _ in range(experiment_data.repeat):  #  tRepeathe loop
            # Request 1: Send data to iperf server
            iperf_server_dict = utils.parse_input_string(server_params)
            logger.info("Server Conf: %s", iperf_server_dict)
            async with httpx.AsyncClient() as client:
                response_a = await client.post(
                    f"http://{experiment_data.server_ip}/Iperf",
                    json=iperf_server_dict)
                if response_a.status_code != 200:
                    logger.error("Failed to connect to %s",
                                 experiment_data.server_ip)
                    raise HTTPException(
                        status_code=response_a.status_code,
                        detail=f"Failed to connect to {experiment_data.server_ip}.")

            # Request 2: Send data to the iperf client
            async with httpx.AsyncClient() as client:
                iperf_client_dict = utils.parse_input_string(client_params)
                logger.info("Client Conf: %s",iperf_client_dict)
                response_b = await client.post(
                    f"http://{experiment_data.client_ip}/Iperf",
                    json=iperf_client_dict)
                if response_b.status_code != 200:
                    logger.error("Failed to connect to %s",
                                 experiment_data.client_ip)
                    raise HTTPException(
                        status_code=response_b.status_code,
                        detail=f"Failed to connect to {experiment_data.client_ip}.")

            experiment_duration = utils.compute_loop_duration(
                experiment_data.duration)
            await asyncio.sleep(experiment_duration)

            result = await wait_for_results(
                results_host, max_wait=max(40, experiment_data.duration))
            results.append(result)

            # Persist and push to InfluxDB immediately after each repeat,
            # instead of waiting for every repeat to finish.
            with open(RESULTS_FILE, "w") as f:
                json.dump(results, f)
            write_to_influxdb({"results": [result]})

        return {"status": "Experiment completed", "results": results}

    except HTTPException:
        # Preserve the original status code/detail (e.g. 403, 408)
        # instead of masking it behind a generic 500.
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


async def close_iperf(host: str):
    """
    Best-effort reset: close any lingering iPerf process on the host.
    A previous run that never received traffic can hang forever on the
    receiving side, leaving it stuck "running" and blocking new runs
    with a 403. Swallow failures since the host may simply not be
    running anything, which is not an error in this context.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"http://{host}/Close")
            logger.info("Close %s: %s", host, response.text)
    except Exception as e:
        logger.warning("Could not reach %s to close iPerf: %s", host, e)


# Add this helper function for waiting until results are ready
async def wait_for_results(server_a_ip: str, max_wait: int = 40):
    """
    Wait until iPerf finishes and the results are ready.

    iPerf2's server-side "-t" timer only starts counting once the first
    flow actually begins, not when the server process itself launches.
    Any delay before the client's first packet arrives (network RTT,
    OS/process scheduling, etc.) pushes the server's real completion
    time out by the same amount, so the retry budget here is generous
    and independent of the experiment's own "duration" to avoid
    declaring a false timeout while the test is still legitimately
    finishing up.
    """
    retries = max(max_wait // 2, 1)
    for _ in range(retries):  # Retry every 2 seconds up to max_wait total
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"http://{server_a_ip}/LastJsonResult")
            if response.status_code == 200:
                return response.json()  # Return results when available
            elif "iPerf is still running" in response.text:
                print("iPerf is still running, waiting...")
                await asyncio.sleep(2)  # Wait 2 seconds before retrying
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Unexpected error: {response.text}",
                )
    raise HTTPException(status_code=408,
                        detail="Timed out waiting for iPerf to finish.")


@router.get("/get-all-results")
async def get_all_results():
    """Return all results from the results file."""
    try:
        with open(RESULTS_FILE, "r") as f:
            results = json.load(f)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Could not read results: {str(e)}") from e
