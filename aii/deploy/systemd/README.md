# AII systemd user units (真源在 ~/.config/systemd/user/)

这些是 AII 各常驻服务的 systemd user unit 快照, 纳入版本管理防丢/可复现.
部署: `cp *.service ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now <unit>`

- aii-embed.service      共享嵌入微服务(BGE-M3, 按需加载/空闲卸载, GPU-或-CPU), 端口 8102。
  ★2026-07-07起禁止用本机GPU, 已迁到笔记本(GTX1050Ti, Windows原生跑, 不经WSL——WSL的
  GPU直通层dxgk会崩溃重启, tailscale 100.68.226.13), 本机这份unit已停用(仅留作历史
  快照/如需改回本机时的底子)。笔记本那边是Windows任务计划(aii-embed-native), 不在此目录。
- aii-backend.service    AII 后端 API(:8101); 设 AII_EMBED_URL 走共享嵌入服务(现指向笔记本), 自身不载模型
- aii-flywheel-*.service 四业务飞轮(econ-zh/math-prog/misc/advmath); 嵌入均走共享服务
- aii-feeder.service     上游喂书守护(PDF→MD 分拣)
