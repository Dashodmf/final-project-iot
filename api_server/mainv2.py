from fastapi import FastAPI, HTTPException
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import os
from typing import Optional
from datetime import datetime, timezone

app = FastAPI(title="IoT InfluxDB API")

# InfluxDB Configuration
INFLUXDB_URL   = os.getenv("INFLUXDB_URL",   "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "my-super-secret-auth-token")
INFLUXDB_ORG   = os.getenv("INFLUXDB_ORG",   "ee-iot")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "sensor_data")

# ── Team info ── fill in your real names / IDs here ──────────────────────────
TEAM_NAMES  = ["Jompon Foowongsit", "Peeranut Tangtaweekul ", "Poomipat Yamploy", "Thanisorn Wiwatwarin"]
TEAM_STD_ID = ["6410550863", "6510552736", "6510552744", "6510552680"]
# ─────────────────────────────────────────────────────────────────────────────

def get_influx_client() -> InfluxDBClient:
    return InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)


# ─────────────────────────────────────────────────────────────────────────────
# Original endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"message": "IoT Data API is running", "status": "healthy"}


@app.get("/data/latest")
def get_latest_data(field: Optional[str] = None):
    """Returns the most recent reading for both temperature and humidity."""
    client = get_influx_client()
    query_api = client.query_api()

    field_filter = f'|> filter(fn: (r) => r["_field"] == "{field}")' if field else ""

    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -5m)
        |> filter(fn: (r) => r["_measurement"] == "environment")
        {field_filter}
        |> last()
    '''

    try:
        tables = query_api.query(query)
        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "time":     record.get_time(),
                    "field":    record.get_field(),
                    "value":    record.get_value(),
                    "location": record.values.get("location"),
                })
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        client.close()


@app.get("/data/history")
def get_history(field: Optional[str] = None, minutes: int = 1):
    """Returns historical data. Optionally filter by field (temperature/humidity)."""
    client = get_influx_client()
    query_api = client.query_api()

    field_filter = f'|> filter(fn: (r) => r["_field"] == "{field}")' if field else ""

    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -{minutes}m)
        |> filter(fn: (r) => r["_measurement"] == "environment")
        {field_filter}
        |> sort(columns: ["_time"], desc: true)
    '''

    try:
        tables = query_api.query(query)
        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "time":     record.get_time(),
                    "field":    record.get_field(),
                    "value":    record.get_value(),
                    "location": record.values.get("location"),
                })
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        client.close()


# ─────────────────────────────────────────────────────────────────────────────
# New endpoints (required by assignment)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/info")
def get_info():
    """Returns team member names and student IDs."""
    return {"name": TEAM_NAMES, "std_id": TEAM_STD_ID}


@app.get("/room_temp")
def get_room_temp():
    """Returns the current room temperature."""
    client = get_influx_client()
    query_api = client.query_api()

    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -5m)
        |> filter(fn: (r) => r["_measurement"] == "environment")
        |> filter(fn: (r) => r["_field"] == "temperature")
        |> last()
    '''

    try:
        tables = query_api.query(query)
        for table in tables:
            for record in table.records:
                return {"temp": round(float(record.get_value()), 2)}
        raise HTTPException(status_code=404, detail="No temperature data found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        client.close()


def _write_light_state(state: bool):
    """Helper: write a light control command to InfluxDB."""
    client = get_influx_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)
    try:
        point = (
            Point("light_control")
            .field("state", state)
            .time(datetime.now(timezone.utc), WritePrecision.NS)
        )
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        client.close()


@app.get("/light_on")
def light_on():
    """Turns the light on."""
    _write_light_state(True)
    return {}


@app.get("/light_off")
def light_off():
    """Turns the light off."""
    _write_light_state(False)
    return {}


@app.get("/light_status")
def get_light_status():
    """Returns the current light status (true = on, false = off)."""
    client = get_influx_client()
    query_api = client.query_api()

    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -1h)
        |> filter(fn: (r) => r["_measurement"] == "light_control")
        |> filter(fn: (r) => r["_field"] == "state")
        |> last()
    '''

    try:
        tables = query_api.query(query)
        for table in tables:
            for record in table.records:
                return {"light": bool(record.get_value())}
        # Default to off if no record found
        return {"light": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        client.close()


@app.get("/status")
def get_board_status():
    """Returns board online status and last heartbeat timestamp."""
    client = get_influx_client()
    query_api = client.query_api()

    # Boards are considered online if a heartbeat was received within the last 30 s
    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -1m)
        |> filter(fn: (r) => r["_measurement"] == "heartbeat")
        |> last()
    '''

    try:
        tables = query_api.query(query)
        result: dict = {}
        last_time: Optional[datetime] = None

        for table in tables:
            for record in table.records:
                board_name = record.values.get("board", "unknown")
                record_time = record.get_time()

                # Mark board online if heartbeat is within the last 30 seconds
                age_seconds = (datetime.now(timezone.utc) - record_time).total_seconds()
                result[board_name] = age_seconds <= 30

                if last_time is None or record_time > last_time:
                    last_time = record_time

        result["last_time_heartbeat"] = last_time.isoformat() if last_time else None
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        client.close()


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)