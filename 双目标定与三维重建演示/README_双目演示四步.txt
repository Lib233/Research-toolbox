1. 右相机视频 + right_anchors.csv：保持三维不勾选；运行生成 frame_trajectory.csv。
2. 左相机视频 + left_anchors.csv：勾选启用三维，选择双目三角测量。
3. 输入 SYNTHETIC_stereo_calibration.json；另选上步右相机输出的 frame_trajectory.csv；偏移0。
4. 运行后查看 stereo_3d_points.csv 的 valid_3d 和 synthetic_true_3d.csv 真值；注意重投影误差不等于真实空间误差。
所有文件均为合成演示，并非用户昆虫实验。操作详见项目顶层《三维视频处理与二维.md》。
