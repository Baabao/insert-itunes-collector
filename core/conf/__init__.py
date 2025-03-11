import os
from typing import Optional

from core.conf.execution import Execution, ExecutionInterface
from core.conf.setting import LazySetting
from core.utils.singleton import SingletonInstance

# static configuration
settings = LazySetting()


class ExecutionManager(metaclass=SingletonInstance):
    _execution: Optional[ExecutionInterface] = None

    @staticmethod
    def get_instance(dynamic: bool = True) -> ExecutionInterface:
        if ExecutionManager._execution is None:
            json_path = f"{os.getcwd()}/execution/{settings.PROD}.setting.json"
            ExecutionManager._execution = Execution(
                json_path=json_path, dynamic=dynamic
            )
        return ExecutionManager._execution
