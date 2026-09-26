"""恋爱大师 - 对话历史数据库连接层（MySQL）

设计要点：
1. **优雅降级**：未启用 MySQL（或连不上）时 `db_ready()` 返回 False，
   历史接口返回 `available=false`，前端自动回退本地存储 —— 不影响对话等主功能。
2. **连接池**：MySQL 侧开启 pool_pre_ping（云托管/云数据库会主动断开空闲连接），
   pool_recycle 小于 MySQL 的 wait_timeout，避免拿到已失效连接。
3. **自动建表**：启动时 `create_all`，无需手工执行 DDL。
   另附一个**幂等的「补列」逻辑**（见 `_sync_missing_columns`）：
   `create_all` 只会建新表、不会给已有表加字段，模型新增列后线上库会直接
   报 `Unknown column`，所以启动时按 inspector 比对并 ALTER 补齐。
   只做加列（不改类型、不删列），可重复执行。
   生产环境量大时可改为 Alembic 迁移，当前规模（演示项目）够用。
"""
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """ORM 基类"""


_engine = None
_SessionFactory = None
_ready = False


def _column_default_literal(col, dialect):
    """把模型上的 Python 默认值转成 DDL 里能用的字面量。

    给已有表加 NOT NULL 列时，MySQL 要求必须带默认值（否则已有行无法填充）。
    模型里写的是 `default=""` 这种 Python 侧默认，不会自动出现在 DDL 里，
    所以这里手动取出来。
    """
    if col.server_default is not None:
        return col.server_default.arg.text if hasattr(col.server_default.arg, "text") else None
    if col.default is None:
        return None
    arg = col.default.arg
    # 可调用默认值（如 datetime.now）没法写进 DDL，交给应用层或允许 NULL
    if col.default.is_callable or not isinstance(arg, (str, int, float, bool)):
        return None
    if isinstance(arg, bool):
        return "1" if arg else "0"
    if isinstance(arg, (int, float)):
        return str(arg)
    escaped = arg.replace("'", "''")
    return f"'{escaped}'"


def _sync_missing_columns(engine) -> None:
    """给已存在的表补上模型里新增的列（幂等；只加列，不改类型、不删列）。

    背景：项目用 `create_all` 建表，它只建**新表**。模型加字段后，
    线上已有的表不会自动多出这一列 → 查询直接 `Unknown column` 报错。
    没有引入 Alembic，用一个 20 行的 inspector 比对把这步自动化，
    代价是只支持「加列」这类向后兼容的变更（对本项目完全够用）。
    """
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    preparer = engine.dialect.identifier_preparer

    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            continue  # 新表交给 create_all
        have = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in have:
                continue

            ddl = (
                f"ALTER TABLE {preparer.format_table(table)} "
                f"ADD COLUMN {preparer.quote(col.name)} "
                f"{col.type.compile(dialect=engine.dialect)}"
            )
            literal = _column_default_literal(col, engine.dialect)
            if literal is not None:
                ddl += f" DEFAULT {literal}"
            if not col.nullable:
                if literal is None:
                    # 没默认值又要 NOT NULL：强行加列会让已有行违规，
                    # 退化为可空列并告警，避免启动直接失败
                    logger.warning(
                        "列 %s.%s 声明为 NOT NULL 但无可用默认值，暂以可空方式添加，请手工确认",
                        table.name,
                        col.name,
                    )
                else:
                    ddl += " NOT NULL"

            try:
                with engine.begin() as conn:
                    conn.execute(text(ddl))
                logger.info("数据库补列完成：%s.%s", table.name, col.name)
            except Exception as exc:  # noqa: BLE001
                # 补列失败不应让服务起不来（可能表被别的实例同时补过）
                logger.warning("补列失败（可忽略，可能已存在）：%s.%s -> %s", table.name, col.name, exc)


def init_db() -> bool:
    """初始化数据库（建表 + 补列 + 建立连接池），返回是否可用。

    失败只记录日志不抛异常：数据库不可用时服务仍要能提供对话能力。
    """
    global _engine, _SessionFactory, _ready

    url = settings.db_url
    if not url:
        logger.info("MySQL 未启用（MYSQL_ENABLED=false）：对话历史由前端本地存储承担")
        _ready = False
        return False

    try:
        kwargs = {}
        if url.startswith("mysql"):
            kwargs = {
                "pool_size": settings.mysql_pool_size,
                "max_overflow": 10,
                "pool_recycle": settings.mysql_pool_recycle,
                "pool_pre_ping": True,
            }
        else:
            # sqlite（本地自测）：不支持 pool 参数
            kwargs = {"pool_pre_ping": True}

        _engine = create_engine(url, future=True, **kwargs)

        # 建表（表已存在时幂等）
        # 注意：模型必须已导入，否则 metadata 为空
        from app.db import models  # noqa: F401

        Base.metadata.create_all(_engine)
        # create_all 不会给已有表加字段，这里补齐模型新增的列
        _sync_missing_columns(_engine)
        _SessionFactory = sessionmaker(
            bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False
        )
        _ready = True
        logger.info("对话历史数据库已就绪：%s", _engine.url.render_as_string(hide_password=True))
    except Exception as exc:  # noqa: BLE001
        # 数据库连接失败不应导致整个服务起不来
        logger.exception("对话历史数据库初始化失败，相关接口将降级：%s", exc)
        _ready = False
    return _ready


def db_ready() -> bool:
    """数据库当前是否可用"""
    return _ready


@contextmanager
def session_scope() -> Iterator[Session]:
    """事务作用域：正常提交、异常回滚、结束关闭。

    调用前请先用 db_ready() 判断，不可用时会抛 RuntimeError。
    """
    if not _ready or _SessionFactory is None:
        raise RuntimeError("数据库不可用")
    session: Session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
