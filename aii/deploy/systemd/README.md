# AII systemd user units (真源在 ~/.config/systemd/user/)

这些是 AII 各常驻服务的 systemd user unit 快照, 纳入版本管理防丢/可复现.
部署: `cp *.service ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now <unit>`

- aii-embed.service      共享嵌入微服务(BGE-M3, 按需加载/空闲卸载, GPU-或-CPU), 端口 8102
- aii-backend.service    AII 后端 API(:8101); 设 AII_EMBED_URL 走共享嵌入服务, 自身不载模型
- aii-flywheel-*.service 三业务飞轮(econ-zh/math-prog/misc); 嵌入均走共享服务
- aii-feeder.service     上游喂书守护(PDF→MD 分拣)
