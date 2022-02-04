from __future__ import annotations
from datetime import datetime
from sqlalchemy.sql.schema import UniqueConstraint

from sqlalchemy.sql.sqltypes import Boolean
from mltrace.db.base import Base
from sqlalchemy import (
    ARRAY,
    Column,
    JSON,
    Index,
    String,
    LargeBinary,
    Integer,
    DateTime,
    Table,
    ForeignKey,
    Enum,
    PickleType,
    UniqueConstraint,
    text,
    Numeric,
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.schema import ForeignKeyConstraint

import enum
import typing


class PointerTypeEnum(str, enum.Enum):
    DATA = "DATA"
    MODEL = "MODEL"
    ENDPOINT = "ENDPOINT"
    UNKNOWN = "UNKNOWN"


# Tables for monitoring extensions

output_table = Table(
    "outputs",
    Base.metadata,
    Column("timestamp", DateTime),
    Column("identifier", String),
    Column("task_name", String),
    Column("value", Numeric),
    Index("outputs_ts_name_asc", "timestamp", "task_name"),
    Index(
        "outputs_ts_name_desc",
        text("timestamp DESC"),
        "task_name",
    ),
)

feedback_table = Table(
    "feedback",
    Base.metadata,
    Column("timestamp", DateTime),
    Column("identifier", String),
    Column("task_name", String),
    Column("value", Numeric),
    Index("feedback_ts_name_asc", "timestamp", "task_name"),
    Index(
        "feedback_ts_name_desc",
        text("timestamp DESC"),
        "task_name",
    ),
)


component_tag_association = Table(
    "component_tags",
    Base.metadata,
    Column("component_name", String, ForeignKey("components.name")),
    Column("tag_name", String, ForeignKey("tags.name")),
)


# Functionality for label tracking.

label_io_pointer_association = Table(
    "labels_io_pointers",
    Base.metadata,
    Column("label", String, ForeignKey("labels.id"), index=True),
    Column("io_pointer_name", String),
    Column("io_pointer_value", LargeBinary),
    ForeignKeyConstraint(
        ["io_pointer_name", "io_pointer_value"],
        ["io_pointers.name", "io_pointers.value"],
    ),
)

deleted_labels = Table(
    "deleted_labels",
    Base.metadata,
    Column("label", String, ForeignKey("labels.id"), primary_key=True),
    Column("deletion_request_time", DateTime),
)


class Label(Base):
    __tablename__ = "labels"
    id = Column(String, primary_key=True)
    io_pointers = relationship(
        "IOPointer",
        secondary=label_io_pointer_association,
        cascade="all",
        backref="io_pointers",
    )

    def __init__(self, id: str):
        self.id = id
        self.io_pointers = []


class Component(Base):
    __tablename__ = "components"

    name = Column(String, primary_key=True)
    description = Column(String)
    owner = Column(String)
    component_runs = relationship("ComponentRun", cascade="all, delete-orphan")
    tags = relationship(
        "Tag", secondary=component_tag_association, cascade="all"
    )

    def __init__(
        self,
        name: str,
        description: str,
        owner: str,
        tags: typing.List[Tag] = [],
    ):
        self.name = name
        self.description = description
        self.owner = owner
        self.tags = tags

    def add_tags(self, tags: typing.List[Tag]):
        self.tags = list(set(self.tags + tags))


class Tag(Base):
    __tablename__ = "tags"

    name = Column(String, primary_key=True)

    def __init__(self, name: str):
        self.name = name


class IOPointer(Base):
    __tablename__ = "io_pointers"

    name = Column(String, primary_key=True, nullable=False)
    value = Column(LargeBinary, primary_key=True, nullable=False)
    pointer_type = Column(Enum(PointerTypeEnum))
    flag = Column(Boolean, default=False)

    labels = relationship(
        "Label",
        secondary=label_io_pointer_association,
        cascade="all",
        backref="labels",
    )

    __table_args__ = (UniqueConstraint("name", "value", name="_iop_uc"),)

    def __init__(
        self,
        name: str,
        value: bytes = b"",
        pointer_type: PointerTypeEnum = PointerTypeEnum.UNKNOWN,
        labels=[],
    ):
        self.name = name
        self.value = value
        self.pointer_type = pointer_type
        self.flag = False
        self.labels = labels

    def set_pointer_type(self, pointer_type: PointerTypeEnum):
        self.pointer_type = pointer_type

    def set_flag(self):
        self.flag = True

    def clear_flag(self):
        self.flag = False

    def add_label(self, label: Label):
        self.labels = self.labels + [label]

    def add_labels(self, labels: typing.list[Label]):
        self.labels = self.labels + labels

    def dedup_labels(self):
        self.labels = list(set(self.labels))


component_run_input_association = Table(
    "component_runs_inputs",
    Base.metadata,
    Column("input_path_name", String),
    Column("input_path_value", LargeBinary),
    Column("component_run_id", Integer, ForeignKey("component_runs.id")),
    # UniqueConstraint(
    #     "input_path_name", "input_path_value", name="inp_nameval"
    # ),
    ForeignKeyConstraint(
        ["input_path_name", "input_path_value"],
        ["io_pointers.name", "io_pointers.value"],
    ),
)

component_run_output_association = Table(
    "component_runs_outputs",
    Base.metadata,
    Column("output_path_name", String),
    Column("output_path_value", LargeBinary),
    Column("component_run_id", Integer, ForeignKey("component_runs.id")),
    # UniqueConstraint(
    #     "output_path_name", "output_path_value", name="out_nameval"
    # ),
    ForeignKeyConstraint(
        ["output_path_name", "output_path_value"],
        ["io_pointers.name", "io_pointers.value"],
    ),
)

component_run_dependencies = Table(
    "component_run_dependencies",
    Base.metadata,
    Column(
        "component_run_id",
        Integer,
        ForeignKey("component_runs.id"),
        primary_key=True,
    ),
    Column(
        "depends_on_component_run_id",
        Integer,
        ForeignKey("component_runs.id"),
        primary_key=True,
    ),
)


class ComponentRun(Base):
    __tablename__ = "component_runs"

    id = Column(Integer, primary_key=True)
    component_name = Column(String, ForeignKey("components.name"))
    notes = Column(String)
    git_hash = Column(String)
    git_tags = Column(PickleType)
    code_snapshot = Column(LargeBinary)
    start_timestamp = Column(DateTime)
    end_timestamp = Column(DateTime)
    mlflow_run_id = Column(String)
    mlflow_run_params = Column(PickleType)
    mlflow_run_metrics = Column(PickleType)
    inputs = relationship(
        "IOPointer",
        secondary=component_run_input_association,
        cascade="all",
        backref=backref("component_runs_inputs", lazy="joined"),
    )
    outputs = relationship(
        "IOPointer",
        secondary=component_run_output_association,
        cascade="all",
        backref=backref("component_runs_outputs", lazy="joined"),
    )
    dependencies = relationship(
        "ComponentRun",
        secondary=component_run_dependencies,
        primaryjoin=id == component_run_dependencies.c.component_run_id,
        secondaryjoin=id
        == component_run_dependencies.c.depends_on_component_run_id,
        backref="left_component_run_ids",
        cascade="all",
    )
    stale = Column(PickleType)
    test_results = Column(JSON)

    def __init__(self, component_name):
        """Initialize ComponentRun, or an instance of a Component's 'run.'"""
        self.component_name = component_name
        self.notes = ""
        self.inputs = []
        self.outputs = []
        self.dependencies = []
        self.stale = []
        self.test_results = JSON.NULL

    def set_mlflow_run_id(self, mlflow_run_id: str):
        """Call this function to set the mlflow component run id"""
        self.mlflow_run_id = mlflow_run_id

    def set_mlflow_run_metrics(self, mlflow_run_metrics: dict):
        """Call this function to set the mlflow component run id"""
        self.mlflow_run_metrics = mlflow_run_metrics

    def set_mlflow_run_params(self, mlflow_run_params: dict):
        """Call this function to set the mlflow component run id"""
        self.mlflow_run_params = mlflow_run_params

    def set_start_timestamp(self, ts: datetime = None):
        """Call this function to set the start timestamp
        to a specific timestamp or now."""
        if ts is None:
            ts = datetime.utcnow()

        if not isinstance(ts, datetime):
            raise TypeError("Timestamp must be of type datetime.")

        self.start_timestamp = ts

    def set_end_timestamp(self, ts: datetime = None):
        """Call this function to set the end timestamp
        to a specific timestamp or now."""
        if ts is None:
            ts = datetime.utcnow()

        if not isinstance(ts, datetime):
            raise TypeError("Timestamp must be of type datetime.")

        self.end_timestamp = ts

    def set_code_snapshot(self, code_snapshot: bytes):
        """Code snapshot setter."""
        self.code_snapshot = code_snapshot

    def add_notes(self, notes: str):
        """Add notes describing details of component run"""
        if not isinstance(notes, str):
            raise TypeError("notes field must be of type str")
        self.notes = notes

    def set_git_hash(self, git_hash: str):
        """Git hash setter."""
        self.git_hash = git_hash

    def set_git_tags(self, git_tags: typing.List[str]):
        """Git tag setter."""
        self.git_tags = git_tags

    def add_staleness_message(self, message: str):
        """Staleness indicator."""
        self.stale = self.stale + [message]

    def add_input(self, input: IOPointer):
        """Add a single input (instance of IOPointer)."""
        self._add_io(input, True)

    def add_inputs(self, inputs: typing.List[IOPointer]):
        """Add a list of inputs (each element should be
        an instance of IOPointer)."""
        self._add_io(inputs, True)

    def add_output(self, output: IOPointer):
        """ "Add a single output (instance of IOPointer)."""
        self._add_io(output, False)

    def add_outputs(self, outputs: typing.List[IOPointer]):
        """Add a list of outputs (each element should be an
        instance of IOPointer)."""
        self._add_io(outputs, False)

    def _add_io(
        self,
        elems: typing.Union[typing.List[IOPointer], IOPointer],
        input: bool,
    ):
        """Helper function to add inputs or outputs."""
        # Elems can be a list or a single IOPointer. Set to a list.
        elems = [elems] if not isinstance(elems, list) else elems
        if input:
            self.inputs = list(set(self.inputs + elems))
        else:
            self.outputs = list(set(self.outputs + elems))

    def set_upstream(
        self,
        dependencies: typing.Union[typing.List[ComponentRun], ComponentRun],
    ):
        """Set dependencies for this ComponentRun. API similar
        to Airflow set_upstream."""
        # Dependencies can be a list or a single ComponentRun. Set to a list.
        dependencies = (
            [dependencies]
            if not isinstance(dependencies, list)
            else dependencies
        )

        self.dependencies += dependencies
        # Drop duplicates
        self.dependencies = list(set(self.dependencies))

    def check_completeness(self) -> dict:
        """Returns a dictionary of success indicator and error messages."""
        status_dict = {"success": True, "msg": ""}
        if self.start_timestamp is None:
            status_dict["success"] = False
            status_dict[
                "msg"
            ] += f"{self.component_name} ComponentRun has no start timestamp. "
        if self.end_timestamp is None:
            status_dict["success"] = False
            status_dict[
                "msg"
            ] += f"{self.component_name} ComponentRun has no end timestamp. "

        # Show warnings if there are no dependencies or I/O.
        if len(self.inputs) == 0:
            status_dict[
                "msg"
            ] += f"{self.component_name} ComponentRun has no inputs. "
        if len(self.outputs) == 0:
            status_dict[
                "msg"
            ] += f"{self.component_name} ComponentRun has no outputs. "
        if len(self.dependencies) == 0:
            status_dict[
                "msg"
            ] += f"{self.component_name} ComponentRun has no dependencies. "

        # Make sure there are no circular dependencies.
        if self.id and self.id in [x.id for x in self.dependencies]:
            status_dict["success"] = False
            status_dict["msg"] += (
                f"{self.component_name} ComponentRun has a "
                + "circular dependency. "
            )

        return status_dict

    def set_test_result(self, test_results: JSON):
        self.test_results = test_results
