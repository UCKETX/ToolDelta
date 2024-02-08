import platform, os, subprocess, time, json, requests, ujson
from typing import Callable
from .color_print import Print
from .urlmethod import download_file, get_free_port
from .builtins import Builtins
from .packets import Packet_CommandOutput, PacketIDS
from .urlmethod import get_free_port

class SysStatus:
    LAUNCHING = 0
    RUNNING = 1
    NORMAL_EXIT = 2
    FB_LAUNCH_EXC = 3
    FB_CRASHED = 4
    NEED_RESTART = 5
    launch_type = "None"

class StandardFrame:
    # 提供了标准的启动器框架, 作为 ToolDelta 和游戏交互的接口
    launch_type = "Original"

    def __init__(self, serverNumber, password, fbToken):
        self.serverNumber = serverNumber
        self.serverPassword = password
        self.fbToken = fbToken
        self.status = SysStatus.LAUNCHING
        self.system_type = platform.uname()[0]
        self.inject_events = []
        self.packet_handler = None
        self.need_listen_packets = {9, 63, 79}
        self._launcher_listener = None

    def add_listen_packets(self, *pcks: int):
        for i in pcks:
            self.need_listen_packets.add(i)

    def launch(self):
        raise Exception("Cannot launch this launcher")

    def listen_launched(self, cb):
        self._launcher_listener = cb

    def close_fb(self):
        ...

    def get_players_and_uuids(self):
        return None

    def get_bot_name(self):
        return None

    get_all_players = None
    sendcmd: Callable[[str, bool, int], bytes | Packet_CommandOutput] = None
    sendwscmd: Callable[[str, bool, int], bytes | Packet_CommandOutput] = None
    sendwocmd: Callable[[str], None] = None
    sendfbcmd = None
    sendPacket = None
    sendPacketJson = None

class FrameFBConn(StandardFrame):
    # 使用原生 FastBuilder External 连接
    cmds_reqs = []
    cmds_resp = {}
    def __init__(self, serverNumber, password, fbToken):
        global fbconn
        from . import fbconn
        super().__init__(serverNumber, password, fbToken)
        self.injected = False
        self.init_all_functions()

    def launch(self):
        try:
            free_port = get_free_port(10000)
            self.runFB(port = free_port)
            self.run_conn(port = free_port)
            Builtins.createThread(self.output_fb_msgs_thread)
            self.process_game_packets()
        except Exception as err:
            return err

    def runFB(self, ip="0.0.0.0", port=8080):
        self.downloadMissingFiles()
        if self.system_type == "Linux":
            os.system("chmod +x phoenixbuilder")
            con_cmd = rf"./phoenixbuilder -t fbtoken --no-readline --no-update-check --listen-external {ip}:{port} -c {self.serverNumber} {f'-p {self.serverPassword}' if self.serverPassword else ''}"

        # windows updated "./PRGM" command.
        if self.system_type == "Windows":
            con_cmd = rf".\phoenixbuilder.exe -t fbtoken --no-readline --no-update-check --listen-external {ip}:{port} -c {self.serverNumber} {f'-p {self.serverPassword}' if self.serverPassword else ''}"
        self.fb_pipe = subprocess.Popen(
            con_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
        )

    def run_conn(self, ip="0.0.0.0", port=8080, timeout=None):
        connect_fb_start_time = time.time()
        max_con_time = timeout or 10
        while 1:
            try:
                self.con = fbconn.ConnectFB(f"{ip}:{port}")
                Print.print_suc("§a成功连接上FastBuilder.")
                return 1
            except:
                if time.time() - connect_fb_start_time > max_con_time:
                    Print.print_err(f"§4{max_con_time}秒内未连接上FB，已退出")
                    self.close_fb()
                    os._exit(0)
                elif self.status == SysStatus.FB_LAUNCH_EXC:
                    Print.print_err(f"§4连接FB时出现问题，已退出")
                    self.close_fb()
                    os._exit(0)

    def output_fb_msgs_thread(self):
        while 1:
            tmp: str = self.fb_pipe.stdout.readline().decode("utf-8").strip("\n")
            if not tmp:
                continue
            elif " 简体中文" in tmp:
                # seems will be unable forever because it's no longer supported.
                try:
                    self.fb_pipe.stdin.write(f"{tmp[1]}\n".encode("utf-8"))
                    self.fb_pipe.stdin.flush()
                    Print.print_inf(f"语言已自动选择为简体中文： [{tmp[1]}]")
                except IndexError:
                    Print.print_war(f"未能自动选择为简体中文")
            elif "ERROR" in tmp:
                if "Server not found" in tmp:
                    Print.print_err(
                        f"§c租赁服号: {self.serverNumber} 未找到, 有可能是租赁服关闭中, 或是设置了等级或密码"
                    )
                    self.status = SysStatus.NORMAL_EXIT
                elif "Unauthorized rental server number" in tmp:
                    Print.print_err(
                        f"§c租赁服号: {self.serverNumber} ，你还没有该服务器号的卡槽， 请前往用户中心购买"
                    )
                    self.status = SysStatus.NORMAL_EXIT
                elif "Failed to contact with API" in tmp:
                    Print.print_err("§c无法连接到验证服务器, 可能是FB服务器崩溃, 或者是你的IP处于黑名单中")
                    try:
                        Print.print_war("尝试连接到 FastBuilder 验证服务器")
                        requests.get("http://user.fastbuilder.pro", timeout=10)
                        Print.print_err("??? 未知情况， 有可能只是验证服务器崩溃， 用户中心并没有崩溃")
                    except:
                        Print.print_err(
                            "§cFastBuilder服务器无法访问， 请等待修复(加入FastBuilder频道查看详情)"
                        )
                    self.status = SysStatus.NORMAL_EXIT
                elif "Invalid token" in tmp:
                    Print.print_err("§cFastBuilder Token 无法使用， 请重新下载")
                    self.status = SysStatus.NORMAL_EXIT
                elif "netease.report.kick.hint" in tmp:
                    Print.print_err(
                        "§c无法连接到网易租赁服 -> 网易土豆的常见问题，检查你的租赁服状态（等级、是否开启、密码）并重试, 也可能是你的网络问题"
                    )
                    self.status = SysStatus.NORMAL_EXIT
                elif "Press ENTER to exit." in tmp:
                    Print.print_err("§c程序退出")
                    os._exit(0)
                else:
                    Print.print_with_info(tmp, "§b  FB  §r")

            elif "Transfer: accept new connection @ " in tmp:
                Print.print_with_info(
                    "FastBuilder 监听端口已开放: " + tmp.split()[-1], "§b  FB  "
                )
            elif "Successfully created minecraft dialer." in tmp:
                Print.print_with_info("§e成功创建于 Minecraft 的链接", "§b  FB  §r")
            elif tmp.startswith("panic"):
                Print.print_err(f"FastBuilder 出现问题: {tmp}")
            else:
                Print.print_with_info(tmp, "§b  FB  §r")

    def close_fb(self):
        try:
            self.fb_pipe.stdin.write("exit\n".encode("utf-8"))
            self.fb_pipe.stdin.flush()
        except:
            pass
        try:
            self.fb_pipe.kill()
        except:
            pass
        Print.print_suc("成功关闭FB进程")

    def process_game_packets(self):
        try:
            for packet_bytes in fbconn.RecvGamePacket(self.con):
                packet_type = packet_bytes[0]
                if packet_type not in self.need_listen_packets:
                    continue
                packet_mapping = ujson.loads(
                    fbconn.GamePacketBytesAsIsJsonStr(packet_bytes)
                )
                if packet_type == PacketIDS.CommandOutput:
                    cmd_uuid = packet_mapping["CommandOrigin"]["UUID"].encode()
                    if cmd_uuid in self.cmds_reqs:
                        self.cmds_resp[cmd_uuid] = [time.time(), packet_mapping]
                self.packet_handler(packet_type, packet_mapping)
                if not self.injected and packet_type == PacketIDS.PlayerList:
                    self.injected = True
                    Builtins.createThread(self._launcher_listener)
        except StopIteration:
            pass
        self.status = SysStatus.FB_CRASHED

    def downloadMissingFiles(self):
        "获取缺失文件"
        Print.print_with_info(f"§d将自动检测缺失文件并补全", "§d 加载 ")
        mirror_src = "https://mirror.ghproxy.com/"
        file_get_src = (
            mirror_src
            + "https://raw.githubusercontent.com/SuperScript-PRC/ToolDelta/main/require_files.json"
        )
        try:
            files_to_get = json.loads(requests.get(file_get_src, timeout=30).text)
        except json.JSONDecodeError:
            Print.print_err("自动下载缺失文件失败: 文件源 JSON 不合法")
            return False
        except requests.Timeout:
            Print.print_err(f"自动下载缺失文件失败: URL 请求出现问题: 请求超时")
            return False
        except Exception as err:
            Print.print_err(f"自动下载缺失文件失败: URL 请求出现问题: {err}")
            return False
        try:
            Print.print_with_info(f"§d正在检测需要补全的文件", "§d 加载 ")
            mirrs = files_to_get["Mirror"]
            files = files_to_get[self.system_type]
            for fdir, furl in files.items():
                if not os.path.isfile(fdir):
                    Print.print_inf(f"文件: <{fdir}> 缺失, 正在下载..")
                    succ = False
                    for mirr in mirrs:
                        try:
                            download_file(mirr + "/https://github.com/" + furl, fdir)
                            succ = True
                            break
                        except requests.exceptions.RequestException:
                            Print.print_war("镜像源故障, 正在切换")
                            pass
                    if not succ:
                        Print.print_err("镜像源全不可用..")
                        return False
                    Print.print_inf(f"文件: <{fdir}> 下载完成        ")
        except requests.Timeout:
            Print.print_err(f"自动检测文件并补全时出现错误: 超时, 自动跳过")
        except Exception as err:
            Print.print_err(f"自动检测文件并补全时出现错误: {err}")
            return False
        return True

    def init_all_functions(self):
        def sendcmd(cmd: str, waitForResp: bool = False, timeout: int = 30):
            uuid = fbconn.SendMCCommand(self.con, cmd)
            if waitForResp:
                self.cmds_reqs.append(uuid)
                waitStartTime = time.time()
                while 1:
                    res = self.cmds_resp.get(uuid)
                    if res is not None:
                        self.cmds_reqs.remove(uuid)
                        del self.cmds_resp[uuid]
                        return Packet_CommandOutput(res[1])
                    elif time.time() - waitStartTime > timeout:
                        self.cmds_reqs.remove(uuid)
                        try:
                            # 特殊情况下只有 sendwscmd 能接收到返回的命令
                            Print.print_war(f'sendcmd "{cmd}" 超时, 尝试 sendwscmd')
                            return self.sendwscmd(cmd, True, timeout)
                        except TimeoutError:
                            raise
            else:
                return uuid
        def sendwscmd(cmd: str, waitForResp: bool = False, timeout: int = 30):
            uuid = fbconn.SendWSCommand(self.con, cmd)
            if waitForResp:
                self.cmds_reqs.append(uuid)
                waitStartTime = time.time()
                while 1:
                    res = self.cmds_resp.get(uuid)
                    if res is not None:
                        self.cmds_reqs.remove(uuid)
                        del self.cmds_resp[uuid]
                        return Packet_CommandOutput(res[1])
                    elif time.time() - waitStartTime > timeout:
                        self.cmds_reqs.remove(uuid)
                        raise TimeoutError("指令超时")
            else:
                return uuid

        self.sendcmd = sendcmd
        self.sendwscmd = sendwscmd
        self.sendwocmd = staticmethod(
            lambda cmd: fbconn.SendNoResponseCommand(self.con, cmd)
        )
        self.sendPacket = self.sendPacketJson = staticmethod(
            lambda pckID, pck: fbconn.SendGamePacketBytes(
                self.con,
                fbconn.JsonStrAsIsGamePacketBytes(
                    pckID, ujson.dumps(pck, ensure_ascii=False)
                ),
            )
        )
        self.sendfbcmd = staticmethod(lambda cmd: fbconn.SendFBCommand(self.con, cmd))


class FrameNeOmg(StandardFrame):
    # 使用 NeOmega 框架连接到游戏
    launch_type = "NeOmega"

    def __init__(self, serverNumber, password, fbToken):
        super().__init__(serverNumber, password, fbToken)
        self.injected = False
        self.omega = None
        self.download_libs()
        self.set_neomg_lib()
        self.init_all_functions()

    def set_neomg_lib(self):
        global neo_conn
        from .neo_libs import neo_conn

    def set_omega(self, openat_port):
        retries = 0
        while retries <= 10:
            try:
                self.omega = neo_conn.ThreadOmega(
                    connect_type=neo_conn.ConnectType.Remote,
                    address=f"tcp://127.0.0.1:{openat_port}",
                    accountOption=neo_conn.AccountOptions(
                        UserToken=self.fbToken,
                        ServerCode=self.serverNumber,
                        ServerPassword=str(self.serverPassword),
                    ),
                )
                retries = 0
                break
            except Exception as err:
                time.sleep(5)
                retries += 1
                Print.print_war(f"OMEGA 连接失败, 重连: 第 {retries} 次: {err}")
                if retries > 5:
                    Print.print_err("最大重试次数已达到")
                    raise SystemExit

    def start_neomega_proc(self):
        free_port = get_free_port(24016)
        py_file_path = os.path.join(os.getcwd(), "tooldelta", "neo_libs", "access.py")
        Print.print_inf(f"DEBUG: PythonLIB Omega 启动路径: {py_file_path}")
        self.neomg_proc = subprocess.Popen(
            [
                f"python3", py_file_path,
                "--server_code", self.serverNumber,
                "--token", self.fbToken,
                "--openat", f"tcp://127.0.0.1:{free_port}",
                "--server_pwd", str(self.serverPassword)
            ],
            stdin = subprocess.PIPE,
            stdout = subprocess.PIPE,
            stderr = subprocess.STDOUT
        )
        return free_port

    def msg_show(self):
        def _msg_show_thread():
            str_max_len = 50
            while 1:
                msg_orig = self.neomg_proc.stdout.readline().decode("utf-8").strip("\n")
                if msg_orig == "" or msg_orig == "SIGNAL: exit":
                    Print.print_with_info(f"ToolDelta: NEOMG 进程已结束", "§b NEOMG")
                    return
                while msg_orig:
                    msg = msg_orig[:str_max_len]
                    msg_orig = msg_orig[str_max_len:]
                    Print.print_with_info(msg, "§b NOMG ")
        Builtins.createThread(_msg_show_thread)

    def launch(self):
        openat_port = self.start_neomega_proc()
        # openat_port = 24016
        self.msg_show()
        self.set_omega(openat_port)
        Print.print_suc("已开启 NEOMG 进程")
        pcks = [
            self.omega.get_packet_id_to_name_mapping(i)
            for i in self.need_listen_packets
        ]
        self.omega.listen_packets(pcks, self.packet_handler_parent)
        self._launcher_listener()
        # bug expired
        self.omega.listen_player_chat(lambda _, _2: None)
        Print.print_suc("NEOMEGA 接入已就绪")
        r = self.omega.wait_disconnect()
        return Exception(r)

    def download_libs(self):
        try:
            res = json.loads(requests.get("https://mirror.ghproxy.com/https://raw.githubusercontent.com/SuperScript-PRC/ToolDelta/main/require_files.json").text)
            use_mirror = res["Mirror"][0]
        except Exception as err:
            Print.print_err(f"获取依赖库表出现问题: {err}")
            raise SystemExit
        sys_machine = platform.uname().machine.lower()
        if sys_machine == "x86_64":
            sys_machine = "amd64"
        elif sys_machine == "aarch64":
            sys_machine = "arm64"
        sys_info_fmt = f"{platform.uname().system}:{sys_machine.lower()}"
        source_dict = res[sys_info_fmt]
        for k, v in source_dict.items():
            pathdir = os.path.join(os.getcwd(), k)
            url = use_mirror + "/https://raw.githubusercontent.com/" + v
            if not os.path.isfile(pathdir):
                Print.print_inf(f"正在下载依赖库 {pathdir} ...")
                try:
                    download_file(url, pathdir)
                except Exception as err:
                    Print.print_err(f"下载依赖库出现问题: {err}")
                    raise SystemExit

    def get_players_and_uuids(self):
        players_uuid = {}
        for i in self.omega.get_all_online_players():
            players_uuid[i.name] = i.uuid
        return players_uuid

    def get_bot_name(self):
        return self.omega.get_bot_name()

    def packet_handler_parent(self, pkt_type, pkt):
        pkt_type = self.omega.get_packet_name_to_id_mapping(pkt_type)
        self.packet_handler(pkt_type, pkt)

    def init_all_functions(self):
        def sendcmd(cmd, waitForResp = False, timeout = 30):
            if waitForResp:
                res = self.omega.send_player_command_need_response(cmd, timeout)
                if res is None:
                    raise TimeoutError("指令超时")
                return res
            else:
                self.omega.send_player_command_omit_response(cmd)
                return b""
        def sendwscmd(cmd, waitForResp = False, timeout = 30):
            if waitForResp:
                res = self.omega.send_websocket_command_need_response(cmd, timeout)
                if res is None:
                    raise TimeoutError("指令超时")
                return res
            else:
                self.omega.send_websocket_command_omit_response(cmd)
                return b""
        def sendwocmd(cmd: str):
            self.omega.send_settings_command(cmd)
        def sendPacket(pktID: int, pkt: str):
            self.omega.send_game_packet_in_json_as_is(pktID, pkt)
        def sendfbcmd(_):
            raise AttributeError("NeOmg模式无法发送FBCommand")

        self.sendcmd = sendcmd
        self.sendwscmd = sendwscmd
        self.sendwocmd = sendwocmd
        self.sendPacket = self.sendPacketJson = sendPacket
        self.sendfbcmd = sendfbcmd