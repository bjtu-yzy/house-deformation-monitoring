# 第三方来源与许可边界

本文件记录整理时发现的来源，不替代原许可证或项目权利人的确认。公开候选仓库未附加统一的开源许可证；因此不能把候选目录中的代码自动解释为 MIT 或 Apache 授权作品。

## SuperPoint / SuperGlue

原模型目录和 `match_pairs.py` 包含 Magic Leap 版权头，原 `deep_learning/LICENSE` 对使用和再分发设有限制。[SuperGlue 官方 LICENSE](https://github.com/magicleap/SuperGluePretrainedNetwork/blob/master/LICENSE) 将其限定于学术或非营利机构的非商业研究用途，并对复制、修改版分发等另有约束。

据此，本次整理未将这些模型实现、工具源码、预训练权重或衍生研究权重捆绑进公开候选包；本地原文件不作更改。后续若需公开修改过的研究实现，应先确认相应权利与许可条件。适配器仅提供配置与调用边界，不意味着第三方研究代码可以重新授权。

参考：

- [SuperGluePretrainedNetwork](https://github.com/magicleap/SuperGluePretrainedNetwork)
- [SuperGlue 论文](https://arxiv.org/abs/1911.11763)
- [SuperPoint 论文](https://arxiv.org/abs/1712.07629)

## 原 README 标注的研究分支

原 `deep_learning/README.md` 提到 [Superglue-with-Physarum-Dynamics](https://github.com/yingxin-jia/Superglue-with-Physarum-Dynamics)。这解释了原模型中训练损失分支和特殊输入形式的来源线索，但不能据此认定所有本地修改的作者、许可或训练来源。

## LightGlue

[官方 LightGlue 仓库](https://github.com/cvg/LightGlue) 的 [LICENSE](https://github.com/cvg/LightGlue/blob/main/LICENSE) 为 Apache-2.0。原项目中的 `lightglue.py / lightglue1.py` 还需逐一核对其实际来源、保留的版权信息和本地改动，不能仅凭文件名套用许可。本次候选包不携带它们，也不声明在线支持 LightGlue。

## 其他依赖与数据

Python 第三方依赖由 `requirements.txt` 安装，适用各自项目许可。当前未捆绑第三方 JS 库。合成示例由仓库脚本生成，已明确标注用途；原 COCO 图像、自采数据、上游样例、论文 PDF、视频及报告插图均未打包。
