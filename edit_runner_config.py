import argparse
import os
from distutils.util import strtobool
from typing import Optional, Dict

from core.common.fs_utils import read_json, write_json


def get_env() -> Optional[str]:
    return os.getenv("PROD")


def get_execution(fp: str) -> Dict:
    return read_json(fp)


def str2bool(value) -> bool:
    if isinstance(value, bool):
        return value
    try:
        return bool(strtobool(value))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Boolean value expected (true/false)."
        ) from exc


def modify(**kwargs) -> None:
    file_path = os.path.join(os.getcwd(), "execution", f"{get_env()}.setting.json")
    execution = read_json(file_path)
    execution["runner_config"] = {**execution.get("runner_config"), **kwargs}
    write_json(file_path, execution, indent=2)


def init_arg() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="quickly modify runner config")
    parser.add_argument(
        "--continue_execute",
        type=str2bool,
        required=False,
        help="soft interrupt runner or not",
    )
    parser.add_argument(
        "--prepare_interval",
        type=int,
        required=False,
        help="modify sleep time before execute entry_point()",
    )
    parser.add_argument(
        "--post_interval",
        type=int,
        required=False,
        help="modify sleep time before execute entry_point()",
    )
    parser.add_argument(
        "--process_num",
        type=int,
        required=False,
        help="modify multiple process using process number",
    )
    return parser.parse_args()


if __name__ == "__main__":
    parse_args = init_arg()
    parse_kwargs = {k: v for k, v in vars(parse_args).items() if v is not None}
    if parse_kwargs:
        modify(**parse_kwargs)
        print(f"Successful change {parse_kwargs}")
    else:
        print("Nothing change")
