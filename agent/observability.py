import json
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from functools import wraps
from pathlib import Path

# 全局 trace_id，用于串联整条链路的日志
_GLOBAL_TRACE_ID = "no-trace"
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def new_trace_id():
    return uuid.uuid4().hex


def set_trace_id(trace_id: str = None):
    global _GLOBAL_TRACE_ID
    _GLOBAL_TRACE_ID = trace_id or new_trace_id()
    return _GLOBAL_TRACE_ID


def get_trace_id():
    return _GLOBAL_TRACE_ID


class JsonFormatter(logging.Formatter):
    def format(self, record):
        # 【优化点】：统一使用北京时间 (UTC+8)，并精确到毫秒
        cst_timezone = timezone(timedelta(hours=8))
        now_cst = datetime.now(cst_timezone)

        payload = {
            "ts": now_cst.isoformat(timespec='milliseconds'),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": get_trace_id(),
            "message": record.getMessage(),
        }
        # 合并 extra_fields 中的业务字段
        if hasattr(record, "extra_fields"):
            payload.update(record.extra_fields)
        return json.dumps(payload, ensure_ascii=False)


# 【核心修复】：自定义 Handler，每次写入后强制刷新磁盘，解决 Docker 挂载不实时同步的问题
class FlushFileHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()


def _build_logger(name, filename):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        # 1. 写入文件（使用强制刷新的 Handler）
        fh = FlushFileHandler(LOG_DIR / filename, encoding="utf-8")
        fh.setFormatter(JsonFormatter())
        logger.addHandler(fh)

        # 2. 控制台输出（方便在 docker logs 里直接看到）
        sh = logging.StreamHandler()
        sh.setFormatter(JsonFormatter())
        logger.addHandler(sh)
    return logger


app_logger = _build_logger("agent.app", "agent.log")
audit_logger = _build_logger("agent.audit", "audit.log")
metric_logger = _build_logger("agent.metric", "metric.log")


def log_event(logger, event_type, message, **fields):
    """统一的日志触发入口"""
    logger.info(message, extra={"extra_fields": {"event_type": event_type, **fields}})


def _digest_state(state):
    """提取 State 中的关键字段，防止日志过大或泄露敏感信息"""
    if not isinstance(state, dict):
        return {}
    keys = ["next_agent", "task_completed", "audit_passed", "retry_count",
            "equipment_done", "sequence_done", "compliance_done", "error_msg"]
    return {k: state.get(k) for k in keys if k in state}


def node_logger(node_name):
    """AOP 装饰器：自动记录 LangGraph 节点的耗时、状态和异常"""

    def decorator(fn):
        @wraps(fn)
        def wrapper(state, *args, **kwargs):
            start = time.time()
            log_event(app_logger, "node_start", f"{node_name} start",
                      node=node_name, state_digest=_digest_state(state))
            try:
                result = fn(state, *args, **kwargs)
                latency = int((time.time() - start) * 1000)
                log_event(app_logger, "node_end", f"{node_name} end",
                          node=node_name, latency_ms=latency, status="success",
                          result_keys=list(result.keys()) if isinstance(result, dict) else None)
                return result
            except Exception as e:
                latency = int((time.time() - start) * 1000)
                log_event(app_logger, "node_error", f"{node_name} error",
                          node=node_name, latency_ms=latency, status="error",
                          error_type=type(e).__name__, error_msg=str(e)[:300])
                raise

        return wrapper

    return decorator


def audit(operator_id, role, action, target, decision, comment=""):
    """HITL 人工审批的专用审计日志"""
    log_event(audit_logger, "audit", f"audit {action}",
              operator_id=operator_id, role=role, action=action,
              target=target, decision=decision, comment=comment)