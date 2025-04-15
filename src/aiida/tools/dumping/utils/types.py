from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Set, Type

from aiida import orm
from aiida.tools.dumping.storage.store import DeletedEntityStore, DumpNodeStore

DumpEntityType = orm.CalculationNode | orm.WorkflowNode | orm.Data
QbDumpEntityType = Type[orm.CalculationNode] | Type[orm.WorkflowNode] | Type[orm.Data]
StoreNameType = Literal["calculations", "workflows", "groups", "data"]

