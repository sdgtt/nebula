import os
import subprocess

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/")
@app.get("/api")
def root():
    return {"message": "Nebula REST API wrapper"}

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/{board}/update-config")
def update_config(board: str, config: dict):
    # get params
    configfilename = config.get("configfilename", "/etc/default/nebula")
    section = config.get("section")
    field = config.get("field")
    board_name = board

    # execute command
    result = subprocess.run(
        ["nebula", "update-config", "--section", section, "--field", field, "--yamlfilename", configfilename, "--board-name", board_name],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return JSONResponse(status_code=500, content={"message": result.stderr})
    return {"result": result.stdout}
        

@app.post("/api/{board}/power-cycle")
def power_cycle(board: str, config: dict):
    # get params
    configfilename = config.get("configfilename", "/etc/default/nebula")
    board_name = board

    # execute command
    result = subprocess.run(
        ["nebula", "pdu.power-cycle", "--yamlfilename", configfilename, "--board-name", board_name],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return JSONResponse(status_code=500, content={"message": result.stderr})
    return {"result": result.stdout}
