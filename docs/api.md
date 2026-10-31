# API

默认根地址 `http://127.0.0.1:8000`。交互式文档位于 `/docs`，机器可读模式位于 `/openapi.json`。

## 健康与引擎

`GET /api/health` 返回版本、忙碌状态和两种引擎的配置情况。`superglue.available` 表示配置检查通过；`loaded` 为 true 才表示权重成功加载，首次推理仍可能因兼容问题失败。

## 单次分析

`POST /api/analyze/upload`，`multipart/form-data`：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| image1 | 文件，必填 | 参考图像 |
| image2 | 文件，必填 | 目标图像，必须同尺寸 |
| engine | superglue / sift | 默认 superglue |

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/analyze/upload `
  -F "engine=sift" `
  -F "image1=@examples/reference.png" `
  -F "image2=@examples/target-1.png"
```

结果包含 `task_id`、`engine`、`unit`、`status`、`valid_regions`、实际关键点数、匹配点数、位移统计和 `region_results`。区域值包含 `raw_matches_count`、过滤后点数、状态及统计量。

`status` 为 `completed`（四区有效）、`partial`（部分有效）或 `unmeasurable`（均无法测量）。统计量 `null` 表示缺失，不能转成 0。`matches_count` 是参与全图统计的有效点对数；区域中少于六个点时仍报告实际过滤后数量，但该区域不参与位移统计。

## 时序分析

`POST /api/analyze/multi-region`，`multipart/form-data`：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| base_image | 文件，必填 | 基础参考图像 |
| base_date | YYYY-MM-DD，必填 | 基础图像拍摄日期 |
| comparison_images | 重复文件字段 | 1–20 张对比图像 |
| dates | JSON 字符串数组 | 与上传文件顺序一一对应的日期 |
| engine | superglue / sift | 默认 superglue |
| slope_threshold | 正数 | 默认 0.5 px/天，最大 1000 |

日期必须有效、互不重复且晚于基础日期。服务将 `(日期, 图像)` 一起排序，返回 `comparison_results` 和 `trend_analysis`。每个区域返回等长 `series`（允许 null）、有效与缺失样本数、斜率和趋势枚举。趋势为 `increasing`、`decreasing`、`no_clear_trend` 或 `insufficient_data`。

## 报告和实际历史

| 路径 | 行为 |
| --- | --- |
| GET /api/tasks/{task_id}/report.json | 下载完整 JSON |
| GET /api/tasks/{task_id}/report.csv | 下载 UTF-8 BOM CSV |
| GET /api/tasks/{task_id}/matches.png | 查看单次分析实际匹配图；无测量时不存在 |
| GET /api/history | 返回最近 20 个真实报告的索引，不生成示例历史 |

错误状态：400 输入无效，413 单图过大，422 参数格式错误，429 服务忙碌，503 研究模型不可用，404 任务或图像不存在。内部未知错误使用 500，不伪装成已完成的测量。

上传文件名不用于磁盘路径；没有任意文件访问或缓存清空接口。旧版 `/api/image/{filename}` 已由任务文件路由替代；旧客户端需与新版前端一起更新。
