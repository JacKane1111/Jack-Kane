# -*- coding: utf-8 -*-
# ============================================================================
#  电机控制 Android 应用  (Motor Control App)
#  语言 / 框架: Python + Kivy   ->   使用 Buildozer 编译为 Android .apk 安装包
#  功能概述:
#     1. 主界面有 6 个 160x80 的按钮
#     2. 第 1 个按钮进入 "Auto" 界面
#     3. Auto 界面有 3 个输入栏(2 个长度栏[厘米] + 1 个数量栏)
#     4. 点击输入栏弹出数字键盘(最多 3 位数字)
#     5. 一个只读的"剩余数量"显示栏
#     6. 运行按钮: 未运行=绿色"运行"; 运行中=红色"停止"
#     7. 按下运行后, 通过蓝牙向控制板发送脉冲信号驱动电机
#        脉冲时间 = 长度(cm) * 0.001 * 60 / 24   例: 100cm -> 0.25 秒
#        每运行完 1 个脉冲, 间隔 1 秒, 剩余数量减 1, 循环直到数量为 0
#        运行中点击红色按钮可随时停止并复位为绿色状态
# ============================================================================

# ---------------------------------------------------------------------------
#  导入 Kivy 框架相关模块
# ---------------------------------------------------------------------------
from kivy.app import App                       # App 是所有 Kivy 应用的基类
from kivy.uix.screenmanager import ScreenManager, Screen  # 用于多窗口(界面)切换的管理器与界面基类
from kivy.uix.boxlayout import BoxLayout        # 盒式布局: 子控件按水平或垂直方向排列
from kivy.uix.gridlayout import GridLayout      # 网格布局: 子控件按行列排列(用于数字键盘)
from kivy.uix.button import Button              # 按钮控件
from kivy.uix.label import Label                # 文本标签控件
from kivy.uix.textinput import TextInput        # 文本输入框控件(此处用作只读的输入显示栏)
from kivy.uix.popup import Popup                # 弹出窗口控件(用于数字键盘)
from kivy.clock import Clock                    # 时钟: 用于在主线程中定时/延时执行 UI 更新
from kivy.core.window import Window             # 窗口对象: 用于设置背景颜色/窗口大小等

import threading                                # 线程模块: 让电机循环在后台线程运行, 避免界面卡死
import time                                     # 时间模块: 用于线程内的延时(脉冲时长、间隔 1 秒)

# ---------------------------------------------------------------------------
#  蓝牙通讯模块 (BluetoothHelper)
#  说明: 真机(Android)上使用 pyjnius 调用安卓原生蓝牙 API 与 HC-05/HC-06
#        蓝牙串口模块(SPP)通信; 在电脑上调试时自动进入"模拟模式", 只打印日志。
# ---------------------------------------------------------------------------
class BluetoothHelper(object):
    """封装安卓经典蓝牙(SPP 串口)的连接与数据发送。"""

    # 目标控制板蓝牙模块的名称(HC-05 出厂默认名, 可按实际修改)
    TARGET_NAME = "HC-05"
    # SPP(串口)服务的标准 UUID, 蓝牙串口通信固定使用此 UUID
    SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"

    def __init__(self):
        self.socket = None      # 蓝牙 Socket 连接对象(连接成功后保存在此)
        self.out_stream = None  # 输出流对象, 通过它把字节数据写给控制板
        self.connected = False  # 连接状态标志: True 表示已连接
        self.simulate = False   # 是否处于模拟模式(非安卓环境自动为 True)

        # 尝试导入 pyjnius, 若失败则说明不在安卓真机上 -> 进入模拟模式
        try:
            from jnius import autoclass  # pyjnius: 让 Python 直接调用 Java/安卓类
            self.autoclass = autoclass   # 保存 autoclass 供后续连接时使用
        except Exception:
            self.simulate = True         # 无 pyjnius(如 PC 调试)-> 打开模拟模式
            print("[蓝牙] 未检测到安卓环境, 进入模拟模式(仅打印日志)")

    def connect(self):
        """连接到目标蓝牙控制板; 返回 True 表示连接成功。"""
        # 模拟模式下直接返回成功, 便于在电脑上测试界面逻辑
        if self.simulate:
            self.connected = True
            print("[蓝牙-模拟] 已'连接'到控制板")
            return True

        try:
            # 获取安卓默认蓝牙适配器(相当于手机的蓝牙硬件)
            BluetoothAdapter = self.autoclass('android.bluetooth.BluetoothAdapter')
            UUID = self.autoclass('java.util.UUID')                 # Java 的 UUID 类
            adapter = BluetoothAdapter.getDefaultAdapter()          # 拿到默认蓝牙适配器实例

            if adapter is None:                                     # 设备没有蓝牙硬件
                print("[蓝牙] 本机没有蓝牙适配器")
                return False

            # 遍历"已配对设备"列表, 找到名字等于 TARGET_NAME 的那一个
            paired = adapter.getBondedDevices().toArray()           # 已配对设备数组
            target_device = None                                    # 用于保存找到的目标设备
            for device in paired:                                   # 逐个检查已配对设备
                if device.getName() == self.TARGET_NAME:            # 名称匹配
                    target_device = device                         # 记录该设备
                    break                                          # 找到即跳出循环

            if target_device is None:                              # 没有找到目标控制板
                print("[蓝牙] 未找到已配对的控制板: %s" % self.TARGET_NAME)
                return False

            # 用标准 SPP UUID 创建一个 RFCOMM 蓝牙 Socket
            uuid_obj = UUID.fromString(self.SPP_UUID)              # 把字符串 UUID 转为 Java UUID 对象
            self.socket = target_device.createRfcommSocketToServiceRecord(uuid_obj)
            self.socket.connect()                                  # 发起连接(阻塞直到连接成功或失败)
            self.out_stream = self.socket.getOutputStream()        # 获取输出流用于发送数据
            self.connected = True                                  # 标记已连接
            print("[蓝牙] 已连接到控制板")
            return True
        except Exception as e:                                     # 任何异常都视为连接失败
            print("[蓝牙] 连接失败: %s" % str(e))
            self.connected = False
            return False

    def send(self, data):
        """向控制板发送一段字符串命令(自动追加换行符作为分隔)。"""
        # 模拟模式只打印, 不真正发送
        if self.simulate:
            print("[蓝牙-模拟] 发送 -> %s" % data)
            return
        try:
            if self.out_stream is not None:                        # 确认输出流可用
                # 把字符串编码为字节并写入输出流(末尾加 \n 便于控制板按行解析)
                self.out_stream.write((data + "\n").encode('utf-8'))
                self.out_stream.flush()                            # 立即把缓冲区数据发出去
        except Exception as e:
            print("[蓝牙] 发送失败: %s" % str(e))

    def close(self):
        """关闭蓝牙连接, 释放资源。"""
        if self.simulate:                                          # 模拟模式无需真正关闭
            self.connected = False
            return
        try:
            if self.socket is not None:                            # 若已建立连接
                self.socket.close()                                # 关闭 Socket
        except Exception:
            pass                                                   # 关闭出错忽略即可
        self.connected = False                                     # 复位连接标志


# ---------------------------------------------------------------------------
#  数字键盘弹窗 (NumberPad)
#  说明: 点击长度栏/数量栏时弹出; 最多输入 3 位数字; 含"清除"和"确定"。
# ---------------------------------------------------------------------------
class NumberPad(Popup):
    """自定义数字键盘弹窗, 输入完成后通过回调把结果返回给调用者。"""

    def __init__(self, on_confirm, initial="", **kwargs):
        # on_confirm: 一个函数, 用户点击"确定"后把输入的数字字符串传给它
        # initial:    弹出时预填的初始文本(通常是输入栏当前的值)
        super(NumberPad, self).__init__(**kwargs)                  # 调用父类 Popup 的初始化

        self.on_confirm = on_confirm                               # 保存确认回调函数
        self.title = "请输入数字 (最多3位)"                          # 弹窗标题
        self.size_hint = (0.8, 0.8)                                # 弹窗占父窗口 80% 宽高
        self.current = initial                                     # 当前已输入的数字字符串
        self.max_digits = 3                                        # 最多允许输入的位数 = 3

        # 弹窗内部使用垂直盒式布局: 上面是显示框, 下面是数字网格
        root = BoxLayout(orientation='vertical', spacing=5, padding=5)

        # 顶部显示当前输入内容的标签
        self.display = Label(text=self.current, font_size='40sp', size_hint_y=0.25)
        root.add_widget(self.display)                              # 把显示标签加入布局

        # 数字按钮区: 4 行 3 列的网格 (1-9, 清除, 0, 确定)
        grid = GridLayout(cols=3, spacing=5, size_hint_y=0.75)     # 3 列网格

        # 依次创建 1~9 的数字按钮
        for n in range(1, 10):                                     # n 从 1 到 9
            btn = Button(text=str(n), font_size='30sp')            # 每个数字一个按钮
            # 绑定点击事件: 点击时把该数字追加到当前输入(用默认参数锁定 n 的当前值)
            btn.bind(on_release=lambda inst, digit=str(n): self.add_digit(digit))
            grid.add_widget(btn)                                   # 加入网格

        # 左下角"清除"按钮
        clear_btn = Button(text="清除", font_size='24sp', background_color=(0.9, 0.6, 0.2, 1))
        clear_btn.bind(on_release=self.clear)                      # 绑定清除功能
        grid.add_widget(clear_btn)

        # 中间下方"0"按钮
        zero_btn = Button(text="0", font_size='30sp')
        zero_btn.bind(on_release=lambda inst: self.add_digit("0"))  # 追加数字 0
        grid.add_widget(zero_btn)

        # 右下角"确定"按钮
        ok_btn = Button(text="确定", font_size='24sp', background_color=(0.2, 0.7, 0.3, 1))
        ok_btn.bind(on_release=self.confirm)                       # 绑定确认功能
        grid.add_widget(ok_btn)

        root.add_widget(grid)                                      # 把数字网格加入主布局
        self.content = root                                       # 设置弹窗内容为该布局

    def add_digit(self, digit):
        """向当前输入追加一位数字(超过 3 位则忽略)。"""
        if len(self.current) < self.max_digits:                   # 只有未满 3 位才允许追加
            self.current += digit                                  # 追加这一位数字
            self.display.text = self.current                       # 更新显示

    def clear(self, *args):
        """清空当前输入。"""
        self.current = ""                                          # 输入内容清空
        self.display.text = ""                                     # 显示同步清空

    def confirm(self, *args):
        """点击确定: 把输入结果通过回调返回, 并关闭弹窗。"""
        self.on_confirm(self.current)                              # 调用回调, 把数字字符串传出去
        self.dismiss()                                             # 关闭弹窗


# ---------------------------------------------------------------------------
#  主界面 (MainScreen): 6 个 160x80 的按钮
# ---------------------------------------------------------------------------
class MainScreen(Screen):
    """应用启动后看到的第一个界面, 含 6 个功能按钮。"""

    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)                # 调用父类 Screen 初始化

        # 用垂直盒式布局承载标题 + 一个居中的网格按钮区
        outer = BoxLayout(orientation='vertical', padding=20, spacing=20)

        # 顶部标题
        title = Label(text="电机控制主界面", font_size='28sp', size_hint_y=0.15)
        outer.add_widget(title)                                   # 标题加入布局

        # 用一个"锚定居中"的容器承载按钮网格, 使按钮居中显示
        from kivy.uix.anchorlayout import AnchorLayout           # 锚定布局: 让子控件对齐到中心
        anchor = AnchorLayout(anchor_x='center', anchor_y='center')

        # 6 个按钮排成 2 行 3 列的网格; size_hint=None 表示使用固定像素尺寸
        grid = GridLayout(cols=3, rows=2, spacing=20, size_hint=(None, None))
        grid.bind(minimum_size=grid.setter('size'))               # 让网格大小自动适配子控件总大小

        # 6 个按钮的名称文字
        button_names = ["Auto", "按钮2", "按钮3", "按钮4", "按钮5", "按钮6"]

        for i, name in enumerate(button_names):                   # i 为下标, name 为按钮文字
            # 创建按钮, 固定大小 160x80 像素(题目要求)
            btn = Button(text=name, size_hint=(None, None), size=(160, 80), font_size='20sp')
            if i == 0:                                             # 第 1 个按钮(下标 0)
                # 绑定点击: 切换到 Auto 界面
                btn.bind(on_release=self.go_auto)
            grid.add_widget(btn)                                   # 把按钮加入网格

        anchor.add_widget(grid)                                    # 网格放入居中容器
        outer.add_widget(anchor)                                   # 居中容器放入主布局
        self.add_widget(outer)                                     # 主布局加入界面

    def go_auto(self, *args):
        """切换到名为 'auto' 的界面。"""
        self.manager.current = 'auto'                              # ScreenManager 切换当前界面为 auto


# ---------------------------------------------------------------------------
#  Auto 界面 (AutoScreen): 长度/数量输入 + 剩余显示 + 运行/停止按钮
# ---------------------------------------------------------------------------
class AutoScreen(Screen):
    """自动运行界面: 设置长度与数量, 通过蓝牙驱动电机按脉冲循环运行。"""

    def __init__(self, bt_helper, **kwargs):
        super(AutoScreen, self).__init__(**kwargs)                # 父类初始化
        self.bt = bt_helper                                       # 保存蓝牙助手实例(全局共享一个)

        self.running = False                                      # 运行状态标志: 是否正在循环
        self.remaining = 0                                        # 剩余数量(运行时递减)
        self.worker = None                                        # 后台工作线程对象

        # 整个界面使用垂直盒式布局
        root = BoxLayout(orientation='vertical', padding=20, spacing=12)

        # 顶部标题
        root.add_widget(Label(text="Auto 自动运行", font_size='26sp', size_hint_y=0.12))

        # ---- 第 1 个输入栏: 长度1 (厘米) ----
        root.add_widget(self._make_row("长度1 (厘米):", self._open_len1))
        # ---- 第 2 个输入栏: 长度2 (厘米) ----
        root.add_widget(self._make_row("长度2 (厘米):", self._open_len2))
        # ---- 第 3 个输入栏: 数量 ----
        root.add_widget(self._make_row("数量:", self._open_qty))

        # ---- 只读显示栏: 剩余数量(不可输入, 仅显示) ----
        rem_row = BoxLayout(orientation='horizontal', size_hint_y=0.14, spacing=10)
        rem_row.add_widget(Label(text="剩余数量:", font_size='20sp', size_hint_x=0.5))
        # readonly=True 使该框只读; disabled 也可, 这里用 readonly 保持外观
        self.remain_input = TextInput(text="0", font_size='24sp', multiline=False,
                                      readonly=True, halign='center', size_hint_x=0.5)
        rem_row.add_widget(self.remain_input)                     # 剩余数量显示框加入行
        root.add_widget(rem_row)                                  # 该行加入主布局

        # ---- 运行 / 停止 按钮 ----
        # 初始: 绿色 + "运行"文字
        self.run_btn = Button(text="运行", font_size='26sp', size_hint_y=0.2,
                              background_normal='',                # 清空默认背景图, 让背景色生效
                              background_color=(0.2, 0.75, 0.3, 1))  # 绿色 (R,G,B,A)
        self.run_btn.bind(on_release=self.on_run_pressed)         # 绑定点击事件
        root.add_widget(self.run_btn)

        # ---- 返回主界面按钮 ----
        back_btn = Button(text="返回主界面", font_size='18sp', size_hint_y=0.12)
        back_btn.bind(on_release=self.go_back)                    # 绑定返回功能
        root.add_widget(back_btn)

        self.add_widget(root)                                     # 主布局加入界面

        # 保存三个输入框的引用, 供数字键盘写入结果
        # (在 _make_row 中创建并分别赋值给下面这些属性)

    def _make_row(self, label_text, open_pad_callback):
        """
        创建一行"标签 + 只读输入框"; 点击输入框会调用 open_pad_callback 弹出数字键盘。
        返回值: 这一行的布局控件。
        """
        row = BoxLayout(orientation='horizontal', size_hint_y=0.14, spacing=10)  # 水平行布局
        row.add_widget(Label(text=label_text, font_size='20sp', size_hint_x=0.5))  # 左侧说明标签

        # 输入框设为只读(readonly=True): 用户不能用系统键盘直接改, 只能通过我们的数字键盘
        ti = TextInput(text="", font_size='24sp', multiline=False,
                       readonly=True, halign='center', size_hint_x=0.5)
        # 绑定触摸事件: 当手指点击(落在)输入框范围内时弹出数字键盘
        ti.bind(on_touch_down=lambda inst, touch: self._on_input_touch(inst, touch, open_pad_callback))
        row.add_widget(ti)                                        # 输入框加入行

        # 按标签内容把输入框引用存到对应属性, 方便后续读取/写入
        if "长度1" in label_text:
            self.len1_input = ti                                  # 长度1 输入框
        elif "长度2" in label_text:
            self.len2_input = ti                                  # 长度2 输入框
        elif "数量" in label_text:
            self.qty_input = ti                                   # 数量 输入框

        return row                                                # 返回这一行

    def _on_input_touch(self, instance, touch, callback):
        """判断触摸点是否落在输入框上; 是则触发对应的数字键盘回调。"""
        if instance.collide_point(*touch.pos):                    # collide_point: 判断坐标是否在控件内
            callback()                                            # 在框内点击 -> 弹出数字键盘
            return True                                           # 返回 True 表示事件已处理
        return False                                              # 否则不处理

    # --- 下面三个方法分别为三个输入框弹出数字键盘 ---
    def _open_len1(self):
        """弹出数字键盘并把结果写入 长度1 输入框。"""
        NumberPad(on_confirm=lambda val: self._set_input(self.len1_input, val),
                  initial=self.len1_input.text).open()

    def _open_len2(self):
        """弹出数字键盘并把结果写入 长度2 输入框。"""
        NumberPad(on_confirm=lambda val: self._set_input(self.len2_input, val),
                  initial=self.len2_input.text).open()

    def _open_qty(self):
        """弹出数字键盘并把结果写入 数量 输入框。"""
        NumberPad(on_confirm=lambda val: self._set_input(self.qty_input, val),
                  initial=self.qty_input.text).open()

    def _set_input(self, target_input, value):
        """把数字键盘返回的值写入指定输入框。"""
        target_input.text = value                                 # 直接设置输入框文本

    # -----------------------------------------------------------------------
    #  运行 / 停止 按钮的点击处理
    # -----------------------------------------------------------------------
    def on_run_pressed(self, *args):
        """点击运行/停止按钮: 未运行则启动循环; 运行中则停止。"""
        if not self.running:                                      # 当前未运行 -> 启动
            self.start_run()
        else:                                                     # 当前运行中 -> 停止
            self.stop_run()

    def start_run(self):
        """开始电机脉冲循环。"""
        # 读取数量输入(为空则按 0 处理)
        try:
            qty = int(self.qty_input.text) if self.qty_input.text else 0
        except ValueError:
            qty = 0                                               # 非法输入按 0
        # 读取长度1(决定脉冲时长); 为空则按 0
        try:
            length = int(self.len1_input.text) if self.len1_input.text else 0
        except ValueError:
            length = 0

        # 数量或长度为 0 则不启动(没有可运行的内容)
        if qty <= 0 or length <= 0:
            self.remain_input.text = "请输入长度和数量"           # 提示用户
            return

        # 计算单个脉冲时长(秒): 长度 * 0.001 * 60 / 24
        # 例: 100 * 0.001 * 60 / 24 = 0.25 秒
        self.pulse_seconds = length * 0.001 * 60.0 / 24.0

        self.remaining = qty                                      # 剩余数量 = 输入的数量
        self.remain_input.text = str(self.remaining)              # 显示剩余数量
        self.running = True                                       # 置为运行状态

        # 按钮变红并显示"停止"
        self.run_btn.text = "停止"
        self.run_btn.background_color = (0.85, 0.2, 0.2, 1)       # 红色

        # 先确保蓝牙已连接(未连接则尝试连接一次)
        if not self.bt.connected:
            self.bt.connect()

        # 启动后台线程执行循环, 避免阻塞 UI 主线程
        self.worker = threading.Thread(target=self._run_loop, daemon=True)
        self.worker.start()

    def _run_loop(self):
        """后台线程: 按脉冲循环驱动电机, 每完成 1 个剩余数量减 1。"""
        # 只要仍在运行且还有剩余数量, 就继续循环
        while self.running and self.remaining > 0:
            # 1) 发送"电机开"命令, 让控制板开始输出脉冲
            self.bt.send("MOTOR_ON")
            # 2) 保持脉冲 pulse_seconds 秒(例如 0.25 秒)
            time.sleep(self.pulse_seconds)
            # 3) 发送"电机关"命令, 停止脉冲
            self.bt.send("MOTOR_OFF")

            # 若在脉冲期间用户点了停止, 立即退出循环
            if not self.running:
                break

            # 4) 本次脉冲完成, 剩余数量减 1
            self.remaining -= 1
            # 在主线程中更新剩余数量显示(UI 只能在主线程更新)
            Clock.schedule_once(lambda dt: self._update_remaining())

            # 5) 若已全部完成, 退出循环
            if self.remaining <= 0:
                break

            # 6) 两次脉冲之间间隔 1 秒(题目要求)
            #    这里分成 10 段小睡, 以便停止时能更快响应
            for _ in range(10):
                if not self.running:                              # 每 0.1 秒检查一次是否被停止
                    break
                time.sleep(0.1)

        # 循环结束(完成或被停止): 回到主线程复位按钮状态
        Clock.schedule_once(lambda dt: self._finish_run())

    def _update_remaining(self):
        """在主线程更新剩余数量显示框。"""
        self.remain_input.text = str(self.remaining)              # 刷新剩余数量文本

    def stop_run(self):
        """用户点击红色停止按钮时调用: 终止循环。"""
        self.running = False                                      # 置为停止, 后台线程会检测到并退出
        # 立即发一次电机关命令, 确保电机不再转动
        self.bt.send("MOTOR_OFF")

    def _finish_run(self):
        """循环结束后复位界面(无论是正常完成还是被停止)。"""
        self.running = False                                      # 复位运行标志
        self.run_btn.text = "运行"                                # 按钮文字改回"运行"
        self.run_btn.background_color = (0.2, 0.75, 0.3, 1)       # 按钮变回绿色

    def go_back(self, *args):
        """返回主界面(若正在运行则先停止)。"""
        if self.running:                                          # 若还在运行
            self.stop_run()                                       # 先停止电机循环
        self.manager.current = 'main'                             # 切换回主界面


# ---------------------------------------------------------------------------
#  应用主类 (MotorApp)
# ---------------------------------------------------------------------------
class MotorApp(App):
    """整个应用的入口类, 负责创建界面管理器并组织各个界面。"""

    def build(self):
        """构建并返回应用的根控件(界面管理器)。"""
        Window.clearcolor = (0.12, 0.12, 0.15, 1)                 # 设置窗口背景为深灰色

        # 创建一个全局共享的蓝牙助手(主界面与 Auto 界面共用同一个连接)
        self.bt = BluetoothHelper()

        # 创建界面管理器, 负责在多个 Screen 之间切换
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))                    # 添加主界面, 命名为 main
        sm.add_widget(AutoScreen(self.bt, name='auto'))           # 添加 Auto 界面, 命名为 auto
        return sm                                                 # 返回管理器作为根控件

    def on_stop(self):
        """应用退出时关闭蓝牙连接, 释放资源。"""
        try:
            self.bt.close()                                       # 关闭蓝牙
        except Exception:
            pass


# ---------------------------------------------------------------------------
#  程序入口: 直接运行本文件时启动应用
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    MotorApp().run()                                             # 创建应用实例并运行
