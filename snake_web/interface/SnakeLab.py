"""Read captured high-score games through Snake Lab's versioned ZMQ interface."""

import os
from uuid import UUID, uuid4

import zmq

from snake_web.constants.DSnakeLab import DSnakeLab


class SnakeLabQueryError(RuntimeError):
    def __init__(self, error):
        super().__init__(f"Snake Lab query failed: {error}")
        self.code = error.get("code") if isinstance(error, dict) else None


class SnakeLab:
    def __init__(self, endpoint=None):
        self.endpoint = endpoint or os.environ.get('SNAKE_LAB_ENDPOINT', DSnakeLab.ENDPOINT)

    def get_highscore_frames(self, run_id: str) -> list[dict] | None:
        """Retrieve and validate a complete captured game; None means no capture."""
        UUID(run_id)
        try:
            payload = self._request("simulation.highscore_frames", {"run_id": run_id})
        except SnakeLabQueryError as error:
            if error.code == "frames_unavailable":
                return None
            raise
        frames = payload.get("frames")
        if payload.get("run_id") != run_id or not isinstance(frames, list) or not frames:
            raise ValueError("Snake Lab response has invalid high-score frames")
        episode = None
        grid_size = None
        for step, frame in enumerate(frames):
            if (not isinstance(frame, dict) or type(frame.get("version")) is not int
                    or frame["version"] != 1 or type(frame.get("step")) is not int
                    or frame["step"] != step or type(frame.get("episode")) is not int
                    or frame["episode"] < 1):
                raise ValueError("Snake Lab response has invalid frame metadata")
            board = frame.get("board")
            if not isinstance(board, dict) or set(board) != {
                "grid_size", "snake_head", "snake_body", "food", "direction", "score"
            }:
                raise ValueError("Snake Lab response has invalid board fields")
            size = board["grid_size"]
            if (not isinstance(size, list) or len(size) != 2
                    or any(type(n) is not int or n <= 0 for n in size)):
                raise ValueError("Snake Lab response has invalid grid dimensions")
            if step == 0:
                episode, grid_size = frame["episode"], size
            if frame["episode"] != episode or size != grid_size:
                raise ValueError("Snake Lab response mixes games or grid dimensions")
            if not isinstance(board["snake_body"], list):
                raise ValueError("Snake Lab response has invalid snake body")
            positions = [board["snake_head"], *board["snake_body"]]
            if board["food"] is not None:
                positions.append(board["food"])
            for position in positions:
                if (not isinstance(position, list) or len(position) != 2
                        or any(type(n) is not int for n in position)
                        or not (0 <= position[0] < size[0] and 0 <= position[1] < size[1])):
                    raise ValueError("Snake Lab response has invalid board coordinates")
            direction = board["direction"]
            if (not isinstance(direction, list) or len(direction) != 2
                    or any(type(n) is not int for n in direction)
                    or direction not in ([1, 0], [-1, 0], [0, 1], [0, -1])
                    or type(board["score"]) is not int or board["score"] < 0):
                raise ValueError("Snake Lab response has invalid direction or score")
        return frames

    def _request(self, method: str, payload: dict) -> dict:
        request_id = str(uuid4())
        request = {
            "protocol_version": DSnakeLab.PROTOCOL_VERSION,
            "request_id": request_id,
            "method": method,
            "payload": payload,
        }
        with zmq.Context() as context:
            with context.socket(zmq.REQ) as socket:
                socket.setsockopt(zmq.LINGER, 0)
                socket.setsockopt(zmq.SNDTIMEO, DSnakeLab.TIMEOUT_MS)
                socket.setsockopt(zmq.RCVTIMEO, DSnakeLab.TIMEOUT_MS)
                socket.connect(self.endpoint)
                socket.send_json(request)
                response = socket.recv_json()

        if not isinstance(response, dict):
            raise ValueError("Snake Lab response must be an object")
        version = response.get("protocol_version")
        if type(version) is not int or version != DSnakeLab.PROTOCOL_VERSION:
            raise ValueError("Snake Lab response has an unsupported protocol version")
        if response.get("request_id") != request_id:
            raise ValueError("Snake Lab response request_id does not match")
        if response.get("status") == "error":
            raise SnakeLabQueryError(response.get("error"))
        if response.get("status") != "ok":
            raise ValueError("Snake Lab response has an invalid status")
        payload = response.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("Snake Lab response payload must be an object")
        return payload
