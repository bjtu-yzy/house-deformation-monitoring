# 原研究模型接入

## 原则

本仓库只提供调用适配器，不携带第三方模型实现、权重、训练图像或论文 PDF。其来源、许可与未来公开方式见 [第三方说明](../THIRD_PARTY_NOTICES.md)。已有本地研究目录继续保留，不移动、不覆盖。

## 配置

复制根目录 `.env.example` 为 `.env`：

```dotenv
HM_SUPERGLUE_DIR=./external/deep_learning
HM_SUPERGLUE_WEIGHTS=
HM_DATA_DIR=
```

将示例路径改为自己的 **deep_learning** 目录，不是 `models` 目录或项目父目录。该目录应包含：

```text
deep_learning/
├── models/
│   ├── superpoint.py
│   ├── superglue.py
│   └── weights/superpoint_v1.pth
└── model_best_superglue.pth
```

`HM_SUPERGLUE_WEIGHTS` 留空时使用上面的默认 checkpoint，填写后可指向另一个已经确认兼容的权重。SuperPoint 的外部构造器仍使用 `models/weights/superpoint_v1.pth`。

安装与 Python 及硬件匹配的 PyTorch（要求 ≥2.6）。当前本机通过的是 PyTorch **2.9.1+cpu**；需要复现该 CPU 组合时可参考 [PyTorch 官方版本安装页](https://pytorch.org/get-started/previous-versions/)，不要直接复用旧项目的 CUDA 11.3 依赖行。基础 Web 服务不需要 PyTorch。

启动 `python run.py`，选择研究引擎并提交图像。首次加载成功后状态变为“研究模型已加载”。模型失败会返回 503，不会降级成另一个引擎或生成随机结果。

## 接口兼容性

此适配器针对本地原项目中带训练损失分支的 SuperGlue：描述子输入形状为 `N×256`，分数形状为 `N×1`；SuperGlue 使用 double，SuperPoint 使用 float。它与官方标准批次接口不同。

目前只验证过上述源码组合与 `model_best_superglue.pth`。原目录中的 `model_best.pth`、`model_best1.pth` 未判定训练来源和适配模型，不作为可替代权重推荐；LightGlue 也不作为已集成引擎。

## 模型与数据管理

源码仓库不包含 checkpoint、原始监控图像、训练数据或实验输出。模型与数据均在本地单独管理；仅将确认允许使用的研究源码配置到上述外部目录。
