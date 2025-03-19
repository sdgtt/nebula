from fastapi.testclient import TestClient
from nebula.daemon import app

import pytest
import os

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Nebula REST API wrapper"}

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_update_config():
    board_name = "plutox"
    config_data = {"configfilename": 
                   os.path.join(os.path.dirname(__file__), "nebula_config", "nebula.yaml"),
                   "section": "board-config",
                   "field": "board-name"}
    response = client.post(f"/api/{board_name}/update-config", json=config_data)
    print(config_data)
    print(response.json())
    assert response.status_code == 200
    # assert response.json() == {"board": board_name, "config": config_data}

def test_power_cycle():
    board_name = "zynq-zed-adv7511-ad4630-24-precision"
    config_data = {"configfilename": 
                   os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-sdg-04.yaml")}
    response = client.post(f"/api/{board_name}/power-cycle", json=config_data)
    print(config_data)
    print(response.json())
    assert response.status_code == 200
    