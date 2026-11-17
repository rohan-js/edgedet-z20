import socket
import threading

import pytest

from client.edgedet.dashboard import BoardClient
from client.edgedet.protocol import InferenceResponse, ProtocolError, encode_response, recv_request


def test_board_client_rejects_stale_frame_and_disconnects():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)

    def server() -> None:
        connection, _ = listener.accept()
        with connection:
            request = recv_request(connection)
            connection.sendall(encode_response(InferenceResponse(0, request.frame_id + 1, 0, 0, 0, ())))

    thread = threading.Thread(target=server)
    thread.start()
    client = BoardClient(listener.getsockname()[0], listener.getsockname()[1], 2.0)
    try:
        with pytest.raises(ProtocolError, match="stale response"):
            client.infer(bytes(320 * 320 * 3), 8)
        assert client.sock is None
    finally:
        client.close()
        listener.close()
        thread.join(timeout=2.0)
