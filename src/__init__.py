"""Study Assistant source package."""

import sys
from unittest.mock import MagicMock

# Gracefully handle Windows Application Control policy blocking native cygrpc.pyd
# ChromaDB embedded client only uses gRPC for optional OpenTelemetry exporter.
try:
    import grpc  # type: ignore[import-untyped]  # noqa: F401
except (ImportError, Exception):
    _mock_grpc = MagicMock()
    _mock_grpc.__version__ = "1.68.0"
    for _mod in [
        "grpc",
        "grpc._compression",
        "grpc._cython",
        "grpc._cython.cygrpc",
        "grpc.aio",
    ]:
        sys.modules[_mod] = _mock_grpc
