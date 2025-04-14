from typing import Literal, Type

from aiida import orm

DumpEntityType = orm.CalculationNode | orm.WorkflowNode| orm.Data
QbDumpEntityType = Type[orm.CalculationNode] | Type[orm.WorkflowNode] | Type[orm.Data]
StoreNameType = Literal['calculations', 'workflows', 'groups', 'data']
