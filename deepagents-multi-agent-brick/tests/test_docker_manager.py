"""Tests for Docker Service Manager and Incremental Port Discovery."""

import pytest
from core.docker_manager import (
    find_available_port,
    get_services_status,
    is_docker_available,
    is_port_in_use,
)


def test_is_port_in_use():
    # Typically unused high port
    assert is_port_in_use(59999) is False


def test_find_available_port():
    port = find_available_port(59000)
    assert 59000 <= port <= 59100
    assert not is_port_in_use(port)


def test_get_services_status():
    statuses = get_services_status()
    assert len(statuses) >= 2
    keys = [s["key"] for s in statuses]
    assert "qdrant" in keys
    assert "mcp_sandbox" in keys
    for s in statuses:
        assert "name" in s
        assert "default_port" in s
        assert "assigned_port" in s
        assert "status" in s


def test_is_docker_available():
    ok, msg = is_docker_available()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
