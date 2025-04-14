
from enum import Enum
from typing import Type

from aiida import orm


class DumpStoreKeys(str, Enum):
    CALCULATIONS = 'calculations'
    WORKFLOWS = 'workflows'
    GROUPS = 'groups'
    DATA = 'data'

    @classmethod
    def from_instance(cls, node_inst: orm.Node | orm.Group) -> str:
        if isinstance(node_inst, orm.CalculationNode):
            return cls.CALCULATIONS.value
        elif isinstance(node_inst, orm.WorkflowNode):
            return cls.WORKFLOWS.value
        elif isinstance(node_inst, orm.Data):
            return cls.DATA.value
        elif isinstance(node_inst, orm.Group):
            return cls.GROUPS.value
        else:
            msg = f'Dumping not implemented yet for node type: {type(node_inst)}'
            raise NotImplementedError(msg)

    @classmethod
    def from_class(cls, orm_class: Type) -> str:
        if issubclass(orm_class, orm.CalculationNode):
            return cls.CALCULATIONS.value
        elif issubclass(orm_class, orm.WorkflowNode):
            return cls.WORKFLOWS.value
        elif issubclass(orm_class, orm.Data):
            return cls.DATA.value
        elif issubclass(orm_class, orm.Group):
            return cls.GROUPS.value
        else:
            msg = f'Dumping not implemented yet for node type: {orm_class}'
            raise NotImplementedError(msg)

    @classmethod
    def to_class(cls, key: 'DumpStoreKeys') -> Type:
        mapping = {
            cls.CALCULATIONS: orm.CalculationNode,
            cls.WORKFLOWS: orm.WorkflowNode,
            cls.DATA: orm.Data,
            cls.GROUPS: orm.Group,
        }
        if key in mapping:
            return mapping[key]
        else:
            msg = f'No node type mapping exists for key: {key}'
            raise ValueError(msg)
