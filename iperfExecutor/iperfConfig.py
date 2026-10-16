import json
from typing import List, Dict
from datetime import datetime, timedelta


class iPerfConfig:
    # iPerf3's long-option names (several differ in meaning from iPerf2's,
    # e.g. "-T"/"-C"/"-L" map to different flags entirely between the two
    # tools, so this table intentionally only reflects iPerf3's own CLI).
    longParameters = {
        "--port": "-p",
        "--format": "-f",
        "--interval": "-i",
        "--bind": "-B",
        "--json": "-J",
        "--server": "-s",
        "--daemon": "-D",
        "--one-off": "-1",
        "--client": "-c",
        "--udp": "-u",
        "--bitrate": "-b",
        "--time": "-t",
        "--bytes": "-n",
        "--blockcount": "-k",
        "--length": "-l",
        "--parallel": "-P",
        "--reverse": "-R",
        "--window": "-w",
        "--congestion": "-C",
        "--set-mss": "-M",
        "--no-delay": "-N",
        "--version4": "-4",
        "--version6": "-6",
        "--tos": "-S",
        "--flowlabel": "-L",
        "--zerocopy": "-Z",
        "--omit": "-O",
        "--title": "-T",
    }

    @classmethod
    def formatValidation(cls, parameters: str) -> bool:
        return parameters[0] == '[' and parameters[-1] == ']'

    @classmethod
    def parseParameters(cls, parameters: List[str]) -> Dict:
        params = {}
        for param in parameters:
            if ':' not in param:
                param = param.strip().replace(' ', ':')
            # Split only on the first ':' so values that themselves
            # contain a colon (e.g. "-c host:port") are preserved intact
            # instead of being truncated at the value's own colon.
            k, _, v = param.strip().partition(':')
            k = k.strip()
            v = v.strip()
            params[k] = v

        return params

    @classmethod
    def shortenParameters(cls, parameters: Dict) -> Dict:
        print(f'Received parameters: {parameters}')
        shortParameters = parameters
        for param in parameters.keys():
            if param in cls.longParameters.keys():
                value = shortParameters[param]
                shortParameters.pop(param)
                shortParameters[cls.longParameters[param]] = value

        print(f'Shorted parameters: {shortParameters}')
        return shortParameters

    @classmethod
    def splitClientHostPort(cls, parameters: Dict) -> Dict:
        """
        iPerf's "-c" only accepts a bare host, not "host:port". Allow the
        convenience "host:port" syntax (as used for server_ip/client_ip
        elsewhere in this system) by splitting it into a bare host plus
        an explicit "-p" parameter. An explicitly provided "-p" always
        takes precedence over a port embedded in "-c".
        """
        client_value = parameters.get('-c', '')
        if ':' in client_value:
            host, _, port = client_value.rpartition(':')
            parameters['-c'] = host
            parameters.setdefault('-p', port)

        return parameters

    # Unlike iPerf2 (where most flags applied to both roles), iPerf3
    # rejects a number of flags outright when they're given to the
    # "wrong" side (e.g. "-u"/"-t"/"-w" are client-only; the server
    # infers protocol/duration/window from whatever the client sends).
    # Since this system's own server_params/client_params were written
    # in iPerf2's dual-purpose style (and "duration" is auto-applied to
    # both sides as "-t"), server-only invocations are filtered down to
    # flags iPerf3's server actually accepts instead of erroring out.
    commonFlags = {
        '-p', '-f', '-i', '-I', '-F', '-A', '-B', '-V', '-J', '-d', '-v',
    }
    serverOnlyFlags = {'-s', '-D', '-1'}
    clientOnlyFlags = {
        '-c', '-X', '-u', '-b', '-t', '-n', '-k', '-l', '-P', '-R', '-w',
        '-C', '-M', '-N', '-4', '-6', '-S', '-L', '-Z', '-O', '-T',
    }

    @classmethod
    def filterParametersForRole(cls, parameters: Dict, isServer: bool) -> Dict:
        allowed = cls.commonFlags | (
            cls.serverOnlyFlags if isServer else cls.clientOnlyFlags)

        filtered = {}
        for key, value in parameters.items():
            if key in allowed:
                filtered[key] = value
            else:
                print(f'Dropping {key} (not valid for '
                      f'{"server" if isServer else "client"})')

        return filtered

    @classmethod
    def parseIperfJsonResult(cls, rawText: str, startTime: datetime) -> List[Dict]:
        """
        Parse iPerf3's "-J" JSON report (captured as the process's full
        stdout) into the same per-interval shape used throughout this
        system: {"timestamp", "throughput", "jitter", "packetLoss"},
        plus "retransmits" for TCP when available.

        iPerf3 only prints its JSON report once, after the test (and
        any process) finishes, so this is called with the complete
        captured output rather than parsed line-by-line like iPerf2's
        text output was.
        """
        jsonStart = rawText.find('{')
        if jsonStart == -1:
            print('No JSON object found in iPerf3 output')
            return []

        try:
            # Use raw_decode (instead of loads) so trailing non-JSON
            # text is ignored. This happens e.g. when the process is
            # SIGTERM'd mid-write (as "/Close" does): iPerf3 may still
            # print extra diagnostic lines after its JSON object.
            data, _ = json.JSONDecoder().raw_decode(rawText[jsonStart:])
        except ValueError as e:
            print(f'Failed to parse iPerf3 JSON output: {e}')
            return []

        if data.get('error'):
            print(f'iPerf3 reported an error: {data["error"]}')
            return []

        protocol = data.get('start', {}) \
                       .get('test_start', {}) \
                       .get('protocol', 'TCP')

        results = []
        for interval in data.get('intervals', []):
            summary = interval.get('sum')
            if not summary:
                continue

            second = int(summary.get('start', 0))
            timestamp = (startTime + timedelta(seconds=second)).timestamp()
            throughput = summary.get('bits_per_second', 0) / 1_000_000

            result = {
                'timestamp': timestamp,
                'throughput': throughput,
            }

            # Jitter/loss are only meaningful (and only reported by
            # iPerf3) on the receiving side of a UDP stream.
            if protocol == 'UDP' and 'jitter_ms' in summary:
                result['jitter'] = summary.get('jitter_ms', 0)
                result['packetLoss'] = summary.get('lost_percent', 0)
            else:
                result['jitter'] = 0
                result['packetLoss'] = 0

            if protocol == 'TCP' and 'retransmits' in summary:
                result['retransmits'] = summary['retransmits']

            results.append(result)

        return results
