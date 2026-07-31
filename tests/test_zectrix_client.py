"""Tests for Zectrix open API client."""

from dotmate.platforms.zectrix.client import ZectrixClient


class Response:
    def __init__(self, data, ok=True, status_code=None):
        self.data = data
        self.ok = ok
        self.status_code = status_code if status_code is not None else (200 if ok else 500)
        self.text = str(data)
        self.encoding = None

    def json(self):
        return self.data

    def raise_for_status(self):
        raise RuntimeError("request failed")


def test_list_devices_maps_zectrix_payload(monkeypatch):
    client = ZectrixClient("zt_secret", request_interval=0)
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return Response(
            {
                "code": 0,
                "data": [
                    {
                        "deviceId": "AA:BB:CC:DD:EE:FF",
                        "alias": "我的设备",
                        "board": "bread-compact-wifi",
                    },
                    {
                        "deviceId": " 11:22:33:44:55:66 ",
                        "alias": None,
                        "board": "bread-compact-wifi",
                    },
                    {
                        "deviceId": "   ",
                        "alias": "ignored",
                        "board": "bread-compact-wifi",
                    },
                ],
            }
        )

    monkeypatch.setattr(client, "_rate_limited_request", request)
    devices = client.list_devices()

    assert [device.id for device in devices] == [
        "AA:BB:CC:DD:EE:FF",
        "11:22:33:44:55:66",
    ]
    assert devices[0].alias == "我的设备"
    assert devices[0].model == "bread-compact-wifi"
    assert devices[0].series == "zectrix"
    assert devices[1].alias is None
    assert calls[0][0:2] == (
        "GET",
        "https://cloud.zectrix.com/open/v1/devices",
    )
    assert calls[0][2]["headers"]["X-API-Key"] == "zt_secret"


def test_list_devices_empty_data(monkeypatch):
    client = ZectrixClient("zt_secret", request_interval=0)
    monkeypatch.setattr(
        client,
        "_rate_limited_request",
        lambda method, url, **kwargs: Response({"code": 0, "data": None}),
    )
    assert client.list_devices() == []
