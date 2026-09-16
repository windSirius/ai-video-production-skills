# 外部素材、来源与权限

## 顺序

1. 官方开发商、发行商、角色或活动页面；
2. 用户提供或用户自有来源；
3. 明确许可的档案或素材库；
4. 有明确评论用途、来源与使用范围的短引用。

## 记录

每个外部源至少写：

```text
source_id publisher title source_url retrieved_at rights_status
original_path original_sha intended_claim watermark treatment notes
```

`rights_status` 使用 `official | licensed | user_owned | permission_needed | unknown`。可访问不等于可发布；`permission_needed` 与 `unknown` 默认不能进入正式轨道。

下载后必须 probe、解码和实际查看。文件名、封面或搜索摘要不能证明内容。不得绕过 DRM、登录、付费墙或平台限制。水印处理必须保留来源记录，并符合用户对该素材的授权范围。

新素材按与本地录屏相同的规则进入镜头索引、人物库、P0覆盖和复用台账。
