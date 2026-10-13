# 统一多源实验演示数据

先打开 `project_manifest.csv`。每一行对应一项**合成实验** E01–E06，包括条件 Group_A/Group_B 和独立试样 A01/A02/A03/B01/B02/B03。

- `record_1/video.avi` 与 `record_1/anchors.csv`：合成的两个小目标，软件将真正调用 LK 光流得到轨迹；其它五条实验直接使用配套 `trajectory.csv` 演示外部轨迹导入。
- 六个 `force.csv`：含明确空载阶段的模拟力—位移曲线；演示配置用 0–0.15 秒归零，0.2–2 秒作为拉离过程。
- 六个 `image.png`：人工绘制的简单亮区域；演示标定为 2 微米/像素，仅用于核对面积公式。
- 六个 `signal.csv`：合成的时间序列，演示未开启自动物理同步。
- 六个 `measurement.csv`：每次实验额外的一行测量指标。
- `param_frequency_hz`：人为设置的演示自变量。

所有数据都是虚构合成数据，不得写入真实科研论文。处理后看 `project_metrics_by_experiment.csv`、`project_stage_audit.csv` 和 `项目结果导航.html`。

真实使用时，请把这份 CSV **复制一份并替换原始路径和真实实验身份**；不能沿用合成演示的参数确认。
