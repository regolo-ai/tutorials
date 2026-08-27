"""Unit tests for Docker Service Manager and Dynamic Port Conflict Resolution."""

import socket
from unittest.mock import MagicMock, patch
import pytest

from core.docker_manager import (
    find_available_port,
    get_service_status,
    get_services_status,
    is_docker_available,
    is_port_in_use,
)


def test_is_port_in_use_free():
    """Verify that an unoccupied high port returns False."""
    # Bind and find a free port then release it
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]

    # Port is now closed
    assert is_port_in_use(free_port) is False


def test_is_port_in_use_occupied():
    """Verify that an active listening port returns True."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        busy_port = s.getsockname()[1]
        assert is_port_in_use(busy_port) is True


def test_find_available_port_increments_on_conflict():
    """Verify that find_available_port moves to the next free port if start_port is occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s1:
        s1.bind(("127.0.0.1", 0))
        s1.listen(1)
        busy_port = s1.getsockname()[1]

        # Searching starting from busy_port should find a different port
        found_port = find_available_port(busy_port)
        assert found_port > busy_port
        assert is_port_in_use(found_port) is False


def test_get_services_status():
    """Verify that get_services_status returns structured state for postgres and cognee."""
    status_map = get_services_status()
    assert "postgres" in status_map
    assert "cognee" in status_map
    assert "port" in status_map["postgres"]
    assert "status" in status_map["postgres"]
