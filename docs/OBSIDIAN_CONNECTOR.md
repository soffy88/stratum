# Obsidian 双向连接器

Stratum 使用笔记 frontmatter 中的稳定 `id` 做 upsert 主键，不用文件名做身份。
因此用户可以在 Obsidian 中改标题、移动文件或编辑正文，再通过同步导回同一条笔记。

API：`POST /api/v1/sync/obsidian`

```json
{"path":"/allowed/vault","mode":"both"}
```

`export` 会生成 `notes/`、`concepts/`、`sources/`、`evidence/`、`learning/` 和
`manifest.json`，并写入最小 `.obsidian/` workspace 配置；`import` 只接收允许根目录
下的 Markdown 文件，路径检查拒绝目录穿越。
