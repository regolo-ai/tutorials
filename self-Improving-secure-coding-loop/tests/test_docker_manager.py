"""Unit tests for Docker Manager & Incremental Port Discovery."""

import socket
import pytest
from core.docker_manager import (
    is_port_in_use,
    find_available_port,
    is_docker_available,
    get_services_status,
    start_service,
    REQUIRED_SERVICES,
)


def test_port_in_use_and_incremental_discovery():
    # Bind a temporary socket on a random available port
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    bound_port = server.getsockname()[1]

    try:
        # Check that is_port_in_use reports True on the bound port
        assert is_port_in_use(bound_port, host="127.0.0.1") is True

        # Check incremental discovery: starting at bound_port, it must find another free port != bound_port
        next_port = find_available_port(start_port=bound_port)
        assert next_port != bound_port
        assert next_port > bound_port
        assert is_port_in_use(next_port, host="127.0.0.1") is False

    finally:
        server.close()


def test_docker_status_inspection():
    is_avail, msg = is_docker_available()
    assert isinstance(is_avail, bool)
    assert isinstance(msg, str)

    statuses = get_services_status()
    assert len(statuses) >= 2
    keys = [s["key"] for s in statuses]
    assert "qdrant" in keys
    assert "cognee" in keys


def test_unknown_service_error():
    res = start_service("non_existent_service_xyz")
    assert res["success"] is False
    assert "Unknown service" in res["error"]
