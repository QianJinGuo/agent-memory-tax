# 我们把自己的 Agent 账单算错了 3 倍

> **Agent 不为思考付钱，为记忆付钱。**

![成本透视](docs/img/agent-bill-hero.png)

一次真实 Claude Code session（7 分钟、一次代码 review、257 行本地日志）的成本透视：**按日志条数记账，输入量被多算 3.3 倍、决策次数被多算 3 倍，而占输入流量 89% 的缓存流量完全隐形。**

先说清楚：**官方账单没有错。** 供应商按真实计费语义收钱——全价输入、约 1/10 的缓存读、输出。我们用 [ccusage](https://github.com/ryoppippi/ccusage) 对同一 session 对账，它的计量**逐 token 正确**。算错的是我们从日志重算成本的那本私账——而这恰恰引出真正的问题：

> **计量已解决，诊断仍空白。** 缓存占比 89.3%、冷启动占 30%、一条命令吃掉 16%——这些结构性事实，没有任何工具会主动算给你看。

## 同一份日志，两种记账

| 记账方式 | API 调用 | 输入 tokens | 输出 tokens |
|---|---|---|---|
| 按日志条数（naive） | 33 | 339,088 | 16,245 |
| 按 `message.id` 去重（真实） | **11** | **103,616** | **6,734** |

| 账单结构（典型比价估算） | 占比 |
|---|---|
| fresh input（其中冷启动一次 ≈ 30%） | ≈ 46% |
| cache 重读（上下文税的真实形态） | ≈ 39% |
| output（最后一次长回复占全部输出的 31%） | ≈ 15% |

一句话：**账单的 85% 是记忆操作**——把上下文装进脑子、把历史反复读回去；思考的产物只占 15%。典型比价下，记忆比思考贵 5.7 倍。

## 30 秒自测

跑在你自己的 `~/.claude/projects` 上，然后去质问你现有的成本工具：

```python
import json, glob
calls = {}
for fp in glob.glob('~/.claude/projects/*/*.jsonl'):
    for line in open(fp):
        r = json.loads(line)
        if r.get('type') != 'assistant': continue
        calls[r['message']['id']] = r['message']['usage']  # message.id 去重
fresh = sum(u['input_tokens'] for u in calls.values())
cache = sum(u['cache_read_input_tokens'] for u in calls.values())
out   = sum(u['output_tokens'] for u in calls.values())
print(f"API 调用: {len(calls)} | fresh: {fresh:,} | cache: {cache:,} ({cache/(fresh+cache):.0%}) | out: {out:,}")
```

## 交互版

**[在线交互页](https://qianjinguo.github.io/agent-bill-3x/)** —— naive/honest 口径一键切换、敢说/不说清单、三步法与三层校验、多工具适用边界。`?mode=honest` 可直达诚实口径。

| 两种记账 | |
|---|---|
| ![naive 口径](docs/img/agent-bill-naive.png) | ![honest 口径](docs/img/agent-bill-honest.png) |

## 完整文章

[article.zh.md](article.zh.md) —— 含统计口径与误差边界、多工具三档表（Claude Code / ZCode / Codex CLI 已验证；OpenCode / Hermes 需导出或体积估算；纯云工具为物理边界）、对账实验与局限声明。

## 局限（诚实版）

n=1；比价是假设（日志里没有钱，只有 token）；GLM 经代理转发，`cache_creation` 恒 0 疑似代理丢失字段；口径锚定 Claude Code v2.1.153，runtime 升级即需重验。

## License

MIT
