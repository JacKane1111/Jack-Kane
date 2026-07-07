// ============================================================================
//  控制板固件 (Arduino)  —— 配合手机 App 使用
//  作用: 通过蓝牙串口(HC-05/HC-06)接收手机 App 发来的命令,
//        收到 "MOTOR_ON" 就让步进电机开始转动(输出脉冲),
//        收到 "MOTOR_OFF" 就停止转动。
//  接线(以常见 A4988/DRV8825 步进电机驱动板为例):
//        Arduino D2  -> 驱动板 STEP(脉冲)
//        Arduino D3  -> 驱动板 DIR (方向)
//        Arduino D4  -> 驱动板 EN  (使能, 低电平有效)
//        HC-05 TXD   -> Arduino D10 (软串口 RX)
//        HC-05 RXD   -> Arduino D11 (软串口 TX, 需分压到 3.3V)
// ============================================================================

#include <SoftwareSerial.h>          // 软件串口库: 用普通引脚模拟串口与蓝牙模块通信

SoftwareSerial BT(10, 11);           // 创建软串口对象: RX=10, TX=11, 连接 HC-05

const int STEP_PIN = 2;              // 步进脉冲引脚
const int DIR_PIN  = 3;              // 方向引脚
const int EN_PIN   = 4;              // 使能引脚(低电平使能驱动板)

bool motorRunning = false;           // 电机是否正在转动的标志

void setup() {
  pinMode(STEP_PIN, OUTPUT);         // 脉冲引脚设为输出
  pinMode(DIR_PIN, OUTPUT);          // 方向引脚设为输出
  pinMode(EN_PIN, OUTPUT);           // 使能引脚设为输出

  digitalWrite(DIR_PIN, HIGH);       // 设定一个转动方向(HIGH/LOW 对应正/反转)
  digitalWrite(EN_PIN, HIGH);        // 初始禁用驱动板(HIGH = 关闭输出)

  Serial.begin(9600);                // 打开硬件串口(用于电脑调试观察)
  BT.begin(9600);                    // 打开蓝牙串口, 波特率 9600(HC-05 默认)
}

void loop() {
  // 若蓝牙有数据到达, 读取一行命令并处理
  if (BT.available()) {                       // 蓝牙缓冲区里有数据
    String cmd = BT.readStringUntil('\n');    // 读取一行命令(App 每条命令末尾带 \n)
    cmd.trim();                               // 去掉首尾空白字符

    if (cmd == "MOTOR_ON") {                  // 收到"电机开"命令
      motorRunning = true;                    // 置为运行
      digitalWrite(EN_PIN, LOW);              // 使能驱动板(LOW = 允许输出)
      Serial.println("电机启动");
    } else if (cmd == "MOTOR_OFF") {          // 收到"电机关"命令
      motorRunning = false;                   // 置为停止
      digitalWrite(EN_PIN, HIGH);             // 禁用驱动板(停止输出)
      Serial.println("电机停止");
    }
  }

  // 当处于运行状态时, 持续输出步进脉冲让电机转动
  if (motorRunning) {
    digitalWrite(STEP_PIN, HIGH);             // 脉冲拉高
    delayMicroseconds(500);                   // 高电平保持 500 微秒(决定转速)
    digitalWrite(STEP_PIN, LOW);              // 脉冲拉低
    delayMicroseconds(500);                   // 低电平保持 500 微秒
    // 上面一高一低 = 1 个完整脉冲(周期 1 毫秒, 即约 1000 步/秒)
  }
}
