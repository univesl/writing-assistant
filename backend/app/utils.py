from datetime import datetime


def dt_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def ok(data, msg: str = "success"):
    return {"code": 200, "msg": msg, "data": data}


def err(code: int, msg: str):
    return {"code": code, "msg": msg, "data": None}
