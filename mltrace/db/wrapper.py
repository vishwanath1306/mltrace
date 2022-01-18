from msilib.schema import Component
from mltrace.db import Component
from mltrace.db.store import Store


def log_component_run_wrapper(
    store: Store, 
    component_run: Component,
    staleness_treshold: int = (60 * 60 * 24 * 30)
    ):
    pass
