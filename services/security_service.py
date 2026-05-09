from datetime import datetime, timedelta
from flask import request as flask_request
from extensions import db
from models import ScanLog


def log_scan(user_id, token_used, result, location="External"):
    
    entry = ScanLog(
        user_id=user_id,
        token_used=token_used,
        timestamp=datetime.utcnow(),
        ip_address=flask_request.remote_addr,
        user_agent=flask_request.headers.get("User-Agent", "")[:512],
        result=result,
        location=location,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def detect_anomaly(token_value: str) -> dict:
    
    window = datetime.utcnow() - timedelta(minutes=5)
    recent_scans = ScanLog.query.filter(
        ScanLog.token_used == token_value,
        ScanLog.timestamp >= window,
    ).all()

    unique_ips = set(s.ip_address for s in recent_scans)
    flags = {
        "high_frequency": len(recent_scans) > 10,
        "multiple_ips": len(unique_ips) > 3,
        "scan_count_5min": len(recent_scans),
        "unique_ip_count": len(unique_ips),
    }
    flags["is_suspicious"] = flags["high_frequency"] or flags["multiple_ips"]
    return flags


def get_scan_stats():
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total = ScanLog.query.count()
    today = ScanLog.query.filter(ScanLog.timestamp >= today_start).count()
    invalid_today = ScanLog.query.filter(
        ScanLog.result != "success",
        ScanLog.timestamp >= today_start
    ).count()
    recent = ScanLog.query.order_by(ScanLog.timestamp.desc()).limit(20).all()

    return {
        "total": total,
        "today": today,
        "invalid_today": invalid_today,
        "recent": recent,
    }
