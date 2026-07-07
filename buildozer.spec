# ============================================================================
#  Buildozer 配置文件 (buildozer.spec)
#  作用: 告诉 Buildozer 如何把上面的 Python(Kivy)程序编译成 Android .apk 安装包。
#  使用方法(在 Linux 或 WSL 环境):
#      pip install buildozer cython        # 安装编译工具
#      buildozer android debug             # 编译生成可安装的 debug .apk
#  编译成功后, .apk 文件会出现在 ./bin/ 目录下, 传到手机即可直接安装。
# ============================================================================

[app]

# 应用显示名称(手机上显示的名字)
title = MotorControl

# 包名(纯小写, 用于内部标识)
package.name = motorcontrol

# 包域名(反向域名写法, 唯一标识应用)
package.domain = org.motor

# 源码所在目录(. 表示当前目录)
source.dir = .

# 需要打包进 APK 的源码文件后缀
source.include_exts = py,png,jpg,kv,atlas

# 应用版本号
version = 1.0

# 依赖库列表: python3 运行时, kivy 界面框架, pyjnius 用于调用安卓蓝牙 API
requirements = python3,kivy,pyjnius

# 屏幕方向: portrait(竖屏)
orientation = portrait

# 是否全屏(0 = 不全屏, 保留状态栏)
fullscreen = 0

# ---- Android 权限(关键: 蓝牙相关权限, 否则无法使用蓝牙) ----
# BLUETOOTH / BLUETOOTH_ADMIN: 经典蓝牙连接与管理(安卓11及以下)
# BLUETOOTH_CONNECT / BLUETOOTH_SCAN: 安卓12+(API 31+)的新蓝牙权限
# ACCESS_FINE_LOCATION: 部分安卓版本蓝牙扫描需要定位权限
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_CONNECT,BLUETOOTH_SCAN,ACCESS_FINE_LOCATION

# 目标安卓 API 级别(31 对应 Android 12; 应用商店要求较高的目标级别)
android.api = 31

# 最低支持的安卓 API 级别(21 对应 Android 5.0)
android.minapi = 21

# 编译使用的 NDK/构建工具版本(留空则用 buildozer 默认推荐版本)
# android.ndk = 25b

# 支持的 CPU 架构(arm64-v8a 覆盖绝大多数现代手机; 加 armeabi-v7a 兼容老设备)
android.archs = arm64-v8a, armeabi-v7a

# 是否接受 Android SDK 许可协议(1 = 自动接受, 避免编译中途卡住)
android.accept_sdk_license = True


[buildozer]

# 日志级别(2 = 显示详细日志, 便于排查编译问题)
log_level = 2

# 出现警告时是否以 root 运行(0 = 否)
warn_on_root = 1
