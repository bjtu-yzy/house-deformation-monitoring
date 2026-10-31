# 研究代码与实验索引

本项目的核心研究路线为 **SuperPoint 特征提取 → SuperGlue 匹配 → 分区位移统计 → 多日期趋势**。整理后的 Web 服务没有声称实现所有文档中提出的研究目标。

以下文件继续保存在原研究目录，未捆绑进当前 GitHub 候选源码包。这样可以先核对原作者、第三方许可、训练集和参数，再决定公开哪些研究材料。

| 原 deep_learning 文件 | 作用或版本线索 | 需要处理 |
| --- | --- | --- |
| load_data_superpoint.py | SuperPoint 数据加载与训练样本构造 | 数据路径、图像配对与监督构造核对 |
| load_data_sift.py | SIFT 特征训练数据路线 | 与模型输入维度、训练权重对应 |
| load_data_lightglue.py / load_data_lightglue_sfit.py | LightGlue 试验数据加载 | 含注释旧代码和不同特征接口，不能混为当前 Web 流程 |
| train.py | SuperGlue 训练入口 | 个人绝对路径、数据来源、参数、随机种子、训练环境待整理 |
| train_lightglue1.py | LightGlue 训练入口 | 与 lightglue1.py / checkpoint 的对应待核实 |
| test_superglue.py | 大型测试 / 对比脚本 | 含多版代码、路径和参数，需要先确定有效实验段 |
| test_lightglue.py | LightGlue 实验 | 未接入 Web 服务，指标需独立复现 |
| test_displacement.py | 位移计算与匹配展示 | 原路径不可移植；当前有效流程已迁入 backend |
| test_ROI.py / test_ROI_final.py | 交互式 ROI 实验 | 两个文件 SHA-256 相同，可在确认后保留一份 |
| test_ROI_no_interact.py | 非交互式 ROI 实验 | 需要样例图和实际参数说明 |
| match_pairs.py | 带上游版权头的匹配 / 评测入口 | 核对第三方许可，不作为项目原创实现公开 |
| models/*.py | 模型及匹配实现 | 包含第三方版权头；由外部适配器使用 |
| my_utils/losses.py / metrics.py | 训练损失、实验指标 | 需与对应训练流水线共同确认 |

## 后续复现应补齐的内容

- 自采建筑场景与 COCO 数据的来源、使用范围和 train / val / test 去重规则。
- 每次训练的配置、软件环境、随机种子、日志、最优权重选择规则及权重校验值。
- 标注位移或标定方法、误差定义、对照方法和可重复的评测入口。
- 原报告指标与可复现输出的对应关系，明确区分论文结果和本项目结果。

根目录 `examples/` 的图片由脚本生成，只验证已知图像平移时端到端流程正常。它们没有建筑安全标签，也不能代替真实数据集评测。
