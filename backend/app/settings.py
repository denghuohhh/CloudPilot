from sqlmodel import Session, select
from .models import Setting
def get_setting(session: Session, owner_id: int, key: str, default: str = '') -> str:
    row = session.exec(select(Setting).where(Setting.owner_id == owner_id, Setting.key == key)).first()
    return row.value if row else default
def set_setting(session: Session, owner_id: int, key: str, value: str):
    row = session.exec(select(Setting).where(Setting.owner_id == owner_id, Setting.key == key)).first()
    if row: row.value = value
    else: session.add(Setting(owner_id=owner_id, key=key, value=value))
    session.commit()
