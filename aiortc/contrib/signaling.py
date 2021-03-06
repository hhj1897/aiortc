import asyncio
import json
import os

from aiortc import RTCSessionDescription


def description_from_string(descr_str):
    descr_dict = json.loads(descr_str)
    return RTCSessionDescription(
        sdp=descr_dict['sdp'],
        type=descr_dict['type'])


def description_to_string(descr):
    return json.dumps({
        'sdp': descr.sdp,
        'type': descr.type
    })


class CopyAndPasteSignaling:
    async def close(self):
        pass

    async def receive(self):
        print('-- Please enter remote description --')
        descr_str = input()
        print()
        return description_from_string(descr_str)

    async def send(self, descr):
        print('-- Your description --')
        print(description_to_string(descr))
        print()


class TcpSocketSignaling:
    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._server = None
        self._reader = None
        self._writer = None

    async def _connect(self, server):
        if self._writer is not None:
            return

        if server:
            connected = asyncio.Event()

            def client_connected(reader, writer):
                self._reader = reader
                self._writer = writer
                connected.set()

            self._server = await asyncio.start_server(
                client_connected,
                host=self._host,
                port=self._port)
            await connected.wait()
        else:
            self._reader, self._writer = await asyncio.open_connection(
                host=self._host,
                port=self._port)

    async def close(self):
        if self._writer is not None:
            self._writer.close()
            self._reader = None
            self._writer = None
        if self._server is not None:
            self._server.close()
            self._server = None

    async def receive(self):
        await self._connect(False)
        data = await self._reader.readuntil()
        return description_from_string(data.decode('utf8'))

    async def send(self, descr):
        await self._connect(True)
        data = description_to_string(descr).encode('utf8')
        self._writer.write(data + b'\n')


class UnixSocketSignaling:
    def __init__(self, path):
        self._path = path
        self._server = None
        self._reader = None
        self._writer = None

    async def _connect(self, server):
        if self._writer is not None:
            return

        if server:
            connected = asyncio.Event()

            def client_connected(reader, writer):
                self._reader = reader
                self._writer = writer
                connected.set()

            self._server = await asyncio.start_unix_server(client_connected, path=self._path)
            await connected.wait()
        else:
            self._reader, self._writer = await asyncio.open_unix_connection(self._path)

    async def close(self):
        if self._writer is not None:
            self._writer.close()
            self._reader = None
            self._writer = None
        if self._server is not None:
            self._server.close()
            self._server = None
            os.unlink(self._path)

    async def receive(self):
        await self._connect(False)
        data = await self._reader.readuntil()
        return description_from_string(data.decode('utf8'))

    async def send(self, descr):
        await self._connect(True)
        data = description_to_string(descr).encode('utf8')
        self._writer.write(data + b'\n')


def add_signaling_arguments(parser):
    """
    Add signaling method arguments to an argparse.ArgumentParser.
    """
    parser.add_argument('--signaling', '-s', choices=[
        'copy-and-paste', 'tcp-socket', 'unix-socket'])
    parser.add_argument('--signaling-host', default='127.0.0.1',
                        help='Signaling host (tcp-socket only)')
    parser.add_argument('--signaling-port', default=1234,
                        help='Signaling port (tcp-socket only)')
    parser.add_argument('--signaling-path', default='aiortc.socket',
                        help='Signaling socket path (unix-socket only)')


def create_signaling(args):
    """
    Create a signaling method based on command-line arguments.
    """
    if args.signaling == 'tcp-socket':
        return TcpSocketSignaling(args.signaling_host, args.signaling_port)
    elif args.signaling == 'unix-socket':
        return UnixSocketSignaling(args.signaling_path)
    else:
        return CopyAndPasteSignaling()
