"""ToolDelta 启动器"""

import os
import time
import signal
import traceback
from .builtins import tmpjson_save_thread
from .urlmethod import check_update
from .frame import Frame, GameCtrl
from .color_print import Print
from .plugin_load.PluginGroup import plugin_group
from .plugin_load.injected_plugin import movent

frame = Frame()


def signal_handler(*_) -> None:
    """排除信号中断"""
    return Print.print_war("ToolDelta 已忽略信号中断")


signal.signal(signal.SIGINT, signal_handler)


def start_tool_delta() -> None:
    """启动ToolDelta"""
    plugin_group.set_frame(frame)
    try:
        frame.welcome()
        check_update()
        frame.basic_operation()
        frame.loadConfiguration()
        game_control = GameCtrl(frame)
        frame.set_game_control(game_control)
        frame.set_plugin_group(plugin_group)
        movent.set_frame(frame)
        plugin_group.read_all_plugins()
        frame.plugin_load_finished(plugin_group)
        tmpjson_save_thread()
        frame.launcher.listen_launched(game_control.Inject)
        game_control.set_listen_packets()
        raise frame.launcher.launch()
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception:
        Print.print_err("ToolDelta 运行过程中出现问题: " + traceback.format_exc())


def safe_jump(*, out_task: bool = True, exit_directly: bool = True) -> None:
    """安全退出

    Args:
        out_task (bool, optional): frame框架系统是否退出
        exit_directly (bool, optional): 是否三秒强制直接退出
    """
    if out_task:
        frame.system_exit()
    frame.safelyExit()
    if exit_directly:
        for _ in range(2, 0, -1):
            Print.print_war(f"{_}秒后强制退出...", end="\r")
            time.sleep(1)
        Print.print_war("0秒后强制退出...", end="\r")
        Print.print_suc("ToolDelta 已退出.")
        os._exit(0)
    Print.print_suc("ToolDelta 已退出.")
