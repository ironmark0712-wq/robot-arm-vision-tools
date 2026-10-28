# Robot Arm Vision Tools

[English](README.en.md)

从SO101机械臂自主研究中整理的离线工程工具：管理视觉物品类别，将像素换算到给定高度平面上的机器人坐标，并复查执行反馈和数据质量。无需机械臂即可运行示例。

作者：刘冠成，陕西科技大学机械专业本科在读。该机械臂自主研究在西安交通大学机械工程学院李响老师指导、设备支持下开展；导师已同意公开当前实践内容及在介绍中署名。[导师官方主页](https://faculty.xjtu.edu.cn/lixiang/zh_CN/index.htm)

## 工具与工程问题

| 工具 | 解决的问题 | 输入与输出 |
|---|---|---|
| 物品库管理 `robot_tools/object_library.py` | 新增或重拍类别时保持旧类别编号，拒绝重名、非法标签和越界框 | 合成标签/框 → 更新方案及稳定ID |
| 平面几何 `robot_tools/pick_geometry.py` | 在给定相机参数、外参和物体平面高度时，把像素射线交点转到基座坐标 | 合成像素/相机参数/已知高度 → 三维点及输入拒绝检查 |
| 反馈分析 `robot_tools/feedback_inspector.py` | 区分目标、实测反馈、程序阶段和真实任务结果；复查数据质量摘要 | 精简真实日志 → JSON/HTML报告 |

它们属于同一项实践的部分工程交付。完整抓放、重新摆放底座后的实机验收和训练结果不在本仓库的已验证成果中。

## 快速运行

在仓库根目录使用Python 3.10或更新版本。物品库和反馈分析仅使用标准库：

```bash
python examples/object_library_demo.py
python -m robot_tools.feedback_inspector samples/empty_grasp_13.json --output-dir artifacts/empty
python -m robot_tools.feedback_inspector samples/static_conversion_summary.json --output-dir artifacts/static
```

用浏览器打开生成的`.report.html`。输出目录里的同名报告已存在时，程序拒绝覆盖；重跑可换一个目录。预先生成的报告在`examples/expected_feedback/`。

几何示例需要NumPy和OpenCV。本次锁定依赖中的NumPy要求Python 3.12或更新版本；建议使用Python 3.12为本仓库单独创建环境：

```bash
python -m venv .venv
# 激活新环境后：
python -m pip install -r requirements-geometry.txt
python examples/geometry_demo.py
```

依赖文件记录本次实际验证版本。OpenCV使用headless包，示例不打开摄像头或窗口。各操作系统对Python/二进制依赖版本的支持以软件包实际提供的wheel为准。

## 检查

```bash
python -m unittest discover -s tests -v
```

没有安装几何依赖时，对应测试明确标为`skipped`，不是通过；完整验证需安装上述依赖。本地验证详情见[VALIDATION.md](VALIDATION.md)。检查逻辑复用已有项目用例，并保留正常静止和人工结果标签等对照。

## 样例来源与结论

- `examples/object_library_demo.py`、`examples/geometry_demo.py`和几何测试使用**合成输入**，不是新实机实验。
- `samples/empty_grasp_13.json`从原548条记录中摘取零基索引19—31：12条闭合记录及随后一条抬升记录，保留原时间与夹爪数值。闭合目标2012降至2006，12条反馈均为2014；结论是记录中未显示位移，不能据此确定扭矩、电机或接触根因。
- `samples/static_conversion_summary.json`是既有静止录制和转换报告的摘要：24张原图、45条状态、0指令，转换27行/27帧，质量标记0但`training_ready=false`，任务结果未知。检查器不重做转换或视频解码。
- 原始来源SHA和字段选择规则在各样例中；SHA用于关联原文件，不是签名或独立真实性认证。当前仓库没有完整图像、视频、标定参数或训练集。

## 坐标、单位和结果边界

几何模块要求**已知平面高度**、相机内参和外参；它不从单张图片恢复未知深度。合成往返误差只能检查数学实现，不能作为实物定位精度。

反馈样例使用舵机原始位置计数，不是角度、毫米、扭矩或夹持力。时间是程序经过/电脑接收时间，不称硬件同步。`LIFT_50MM`是阶段名称，不证明实物移动距离。任务成功须有明确来源，数据能读取、程序走完或质量标记为0都不能替代现场结果。

## 贡献与来源

本人负责本地项目推进、设备与场景准备、实机操作、观察并反馈问题、提出检查需求及复测；工程代码、日志分析和公开版整理使用AI辅助。本人需要理解并解释接口、检查条件和结果。本仓库不宣称所有算法从零原创。

SO-ARM100/SO101、LeRobot和YOLOE用于原实践，未将其模型、权重、整套框架或硬件文件打包到本仓库。详见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本仓库代码及明确包含的示例按[MIT许可证](LICENSE)发布，第三方组件保留各自许可。

后续可整理基础MuJoCo演示及LeRobot采集/转换管线；当前版本只包含上表三个离线工具。
