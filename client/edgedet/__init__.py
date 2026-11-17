"""EdgeDet-Z20 host client and virtual-board utilities."""

from .protocol import Detection, FrameRequest, InferenceResponse, ProtocolError

__all__ = ["Detection", "FrameRequest", "InferenceResponse", "ProtocolError"]
