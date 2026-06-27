# TreeChat · 树状 AI 对话

**本项目大量使用 AI 辅助完成。**

把 AI 对话从「线性」变成「树状」：
- **根节点**为空（或一段系统提示）；
- **边** = 你发送的消息；**节点** = AI 的回复；
- 可从**任意节点**拉出一条新边继续提问（即开分支）；
- 可**删除任意子树**；
- 每次请求只把「根 → 当前叶子」路径上的消息喂给模型——天然裁剪上下文，省 token 也更聚焦。

后端用 DeepSeek API（OpenAI 兼容），通过一个零依赖的本地 Python 代理转发，避免浏览器 CORS、也不把 key 写进前端。

## 运行

需要 Python 3.7+，**无需 pip 安装任何包**。

```bash
# 1. （可选）用环境变量提供 key，否则可在网页里填
#    PowerShell:
$env:DEEPSEEK_API_KEY="sk-你的key"
#    bash:
export DEEPSEEK_API_KEY=sk-你的key

# 2. 启动
python app.py
```

浏览器会自动打开 `http://127.0.0.1:8000`。首次若未设置 key，会弹窗让你填（key 只存在服务端内存，不写盘）。

获取 key：<https://platform.deepseek.com/api_keys>

## 操作

| 操作 | 方式 |
|------|------|
| 选中节点 | 单击树中的节点卡片 |
| 平移画布 | 拖拽空白处 |
| 缩放 | 滚轮，或右上角 ＋ / － / 适配 |
| 拉新分支 | 选中某节点 → 右侧输入框输入 → Enter 发送 |
| 换行 | Shift + Enter |
| 删除子树 | 选中节点 → 「删除此子树」 |
| 切模型 | 顶栏下拉（deepseek-chat / deepseek-reasoner） |
| 系统提示 | 顶栏「系统提示」 |
| 导出 / 导入 | 顶栏按钮，JSON 文件，含整棵树 |

对话树自动保存在浏览器 `localStorage`，刷新不丢。

## 文件

- `app.py` —— 本地服务器 + DeepSeek 流式代理（仅标准库）
- `index.html` —— 全部前端（树可视化 + 流式对话）

## 设计要点

- 数据模型：`node = {id, parent, user, reply, children[]}`，把「边的内容（user 消息）」和「它指向的节点（AI 回复）」存在同一对象里。
- 请求上下文：`pathTo(leaf)` 取根到叶路径，拼成 `system? + (user, assistant)* + user` 发给 API。
- `deepseek-reasoner` 的 `reasoning_content` 会单独以「💭 思考」块展示。
