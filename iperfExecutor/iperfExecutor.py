import os
import signal
import subprocess
from typing import List, Dict
from datetime import datetime, timezone
from threading import Thread
from iperfExecutor.iperfConfig import iPerfConfig


class iPerf:
    isRunning = False
    executable: str = None
    rawResult: List[str] = []
    jsonResult: List[Dict] = []
    error: List[str] = []
    startTime: datetime = None
    isServer = False
    processPID: int = -1

    @classmethod
    def Initialize(cls, executable: str):
        cls.executable = executable

    @classmethod
    def Iperf(cls, parameters: List[str]):
        params = iPerfConfig.parseParameters(parameters)
        return cls.execute(params)

    @classmethod
    def Close(cls):
        if not cls.isRunning or cls.processPID == -1:
            raise RuntimeError('iPerf is not running')

        os.kill(cls.processPID, signal.SIGTERM)
        cls.processPID = -1
        cls.isRunning = False
        return 1


    @classmethod
    def LastRawResult(cls):
        if cls.isRunning:
            raise RuntimeError("iPerf is still running")

        print(f'Last Raw Result: {cls.rawResult}')
        return cls.rawResult

    @classmethod
    def LastJsonResult(cls):
        if cls.isRunning:
            raise RuntimeError("iPerf is still running")

        print(f'Last Json Result: {cls.jsonResult}')
        return cls.jsonResult

    @classmethod
    def LastError(cls):
        if cls.isRunning:
            raise RuntimeError("iPerf is still running")

        print(f'Last Error: {cls.error}')
        return cls.error


    @classmethod
    def StartDateTime(cls):
        print(f'Start Date Time: {cls.startTime}')
        return cls.startTime

    @classmethod
    def IsRunning(cls):
        print(f'Is Running: {cls.isRunning}')
        return cls.isRunning

    @classmethod
    def execute(cls, parametersDict: Dict) -> None:
        if cls.executable is None:
            raise RuntimeError('Running iPerf without executable')
        if cls.isRunning:
            raise RuntimeError('iPerf already running')

        # Shorten long parameters format
        parametersDict = iPerfConfig.shortenParameters(parametersDict)

        # Allow "-c host:port" convenience syntax by splitting it into
        # a bare host plus an explicit "-p" (iPerf itself rejects a
        # combined "host:port" value for "-c").
        parametersDict = iPerfConfig.splitClientHostPort(parametersDict)

        isServer = '-c' not in parametersDict.keys()

        # iPerf3 hard-errors if a client-only flag (e.g. "-u"/"-t"/"-w")
        # is given to the server, or vice versa. Drop anything the
        # current role doesn't accept instead of failing outright, so
        # server_params/client_params written in iPerf2's dual-purpose
        # style (or auto-populated fields like "duration") keep working.
        parametersDict = iPerfConfig.filterParametersForRole(
            parametersDict, isServer)

        # Default interval to 1s if not present
        if '-i' not in parametersDict.keys():
            parametersDict['-i'] = '1'

        # Always request JSON output: this is what parseIperfJsonResult
        # relies on instead of iPerf2's line-by-line text parsing.
        parametersDict['-J'] = ''

        if isServer:
            # Unlike iPerf2, iPerf3's server has no "-t" of its own (only
            # the client controls test duration); instead, "-1" tells the
            # server to handle exactly one client then exit on its own,
            # giving each run a clean, self-terminating lifecycle that
            # doesn't depend on when the client's first packet arrives.
            parametersDict.setdefault('-1', '')

        parameters = []
        for key, value in parametersDict.items():
            parameters.append(key)
            if len(value) != 0:
                parameters.append(value)

        params = [cls.executable, *parameters]

        print(f'Final CLI parameters: {params}')

        Thread(target=cls.async_task, args=(params,)).start()
        return None

    @classmethod
    def stdout(cls, process: subprocess.Popen):
        pipe = process.stdout

        for line in iter(pipe.readline, b''):
            try:
                line = line.decode('utf-8').rstrip()
            except Exception as e:
                line = f'DECODING EXCEPTION: {e}'

            if 'error' in line or 'failed' in line:
                cls.error.append(line)

            cls.rawResult.append(line)

    @classmethod
    def async_task(cls, params: List[str]):
        cls.isRunning = True
        cls.rawResult = []
        cls.jsonResult = []
        cls.error = []
        cls.startTime = datetime.now(timezone.utc)
        try:
            process = subprocess.Popen(params, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            cls.processPID = process.pid

            if '-c' in params:
                cls.isServer = False
                print('Client running')
            else:
                cls.isServer = True
                print('Server running')

            cls.stdout(process)
            process.wait()

            # iPerf3 only prints its "-J" JSON report once, after the
            # process finishes, so it's parsed here from the full
            # captured output rather than line-by-line while running.
            cls.jsonResult = iPerfConfig.parseIperfJsonResult(
                '\n'.join(cls.rawResult), cls.startTime)
        except Exception as e:
            print(f'Error in process: {e}')
        finally:
            cls.isRunning = False

        if not cls.isServer:
            print('Client finished')
        else:
            print('Server finished')
