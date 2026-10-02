# 神经研究所每日自动化 / EasonFans Daily Automation

使用 Python + Playwright 操作神经研究所论坛的个人自动化工具。支持每日签到、转盘、本地题库答题，以及可选的留言功能。项目非网站官方出品，页面改版可能需要调整程序。

**公开版默认关闭自动留言，不包含账号、登录状态或完整题库。** 请使用自己的账号，遵守网站规则和操作频率要求，不要批量骚扰其他用户。

## 安装与首次运行（Windows）

需要 Python 3.10 或更新版本，安装时启用 Add Python to PATH。

1. 下载本仓库 ZIP 并解压到固定目录，或用 Git 克隆。
2. 双击 `一键安装依赖.bat`，安装 Playwright、Chromium 并生成 `config.json`。
3. 参考 `题库.example.txt`，准备自己的 UTF-8 编码 `题库.txt`，放在程序目录内。示例题目仅说明格式，不是网站题库。
4. 双击 `首次登录.bat`，在打开的浏览器中登录自己的账号。识别登录成功后浏览器自动关闭，登录资料保存在本机。
5. 双击 `检查登录状态.bat` 验证，再双击 `立即运行.bat`。

手动安装命令（在项目目录运行）：

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item config.example.json config.json
```

已有配置时不要重复执行最后一条覆盖命令。Python 与 Playwright 应安装在同一个 Python 环境。

## 运行逻辑

依次执行：登录检查 → 签到 → 转盘 → 最多三道答题 → 可选留言。

- 无法唯一匹配题目或答案时，不猜答、不提交；保存日志和截图，结束本次答题，继续后续任务。
- 支持“第 2 个”和“第二个”等数字写法匹配；相似问题、相反问法或冲突答案不保证能自动处理。
- 网络故障、登录超时、浏览器错误等仍会报错退出，不会被当作“缺少答案”忽略。
- 转盘点击日志只说明已点击控件；真实结果需以网站为准。
- 运行日志和故障截图在 `logs/`，可能包含账号信息，请勿直接公开。

## 题库格式

```text
1.一天有多少小时？—24小时
2.一周有多少天？
答：7天
```

每次启动会读取 `题库.txt`，生成 `quiz_bank.json` 与 `题库导入报告.json`。报告列出未识别内容和同题不同答案，建议人工检查。题库文件及导入产物均已加入 Git 忽略规则。程序也支持仅提供配置指定的 JSON 题库，格式为 `[{"question": "问题", "answer": "答案"}]`。

本仓库仅附自编格式示例。完整题库请自行准备，并确认其使用和分享权限。

## 配置

编辑本机 `config.json`，不要修改示例文件存放个人信息。

| 配置 | 默认值 | 用途 |
| --- | --- | --- |
| `message_count` | `0` | 0 关闭留言；自行改为正整数开启 |
| `wall_url` | 含 `YOUR_UID` 的示例地址 | 开启留言前替换为自己的 UID |
| `message_delay_seconds` | `25` | 两次留言之间等待秒数 |
| `headless` | `false` | 显示浏览器，便于首次登录及处理登录失效 |
| `login_wait_minutes` | `10` | 等待人工登录的分钟数 |
| `navigation_timeout_ms` | `45000` | 浏览器默认超时 |

留言功能会从配置的留言墙页面收集用户并提交表情。`visited_ids.json` 保存历史，但当前实现不保证跨天跳过已经留言过的人。启用前请明确了解该行为；不要分享登录资料。

## 每天 20 点自动运行

先确认手动运行正常，再双击 `安装每天20点自动运行.bat`。它会创建或替换名为 `EasonFans Daily Automation` 的 Windows 计划任务，使用本机时区的 20:00。

电脑需要开机，浏览器自动化通常需要用户处于登录桌面状态。错过执行时间后可能补跑；不会自动唤醒关机电脑。移动项目目录后需要重新安装计划任务。可在 Windows 任务计划程序中禁用或删除该任务。

`创建桌面快捷方式.bat` 可创建启动快捷方式。启动脚本会切换到项目目录，不需要放进 Windows 系统目录。

## 命令行与测试

```powershell
python easonfans_daily.py --help
python easonfans_daily.py --import-bank
python easonfans_daily.py --login
python easonfans_daily.py --check-login
python easonfans_daily.py --inspect
python easonfans_daily.py --run
python -m unittest discover -v
```

`--check-login`、`--inspect` 不提交签到、答题或留言，但会读取网站并可能写本地诊断文件。测试使用本地模拟页面和替代对象，不使用个人登录资料，不向网站发送留言。

## 隐私与许可证

`.gitignore` 排除了个人配置、浏览器资料、日志、截图、题库、访问历史、缓存及压缩包。提交前仍应检查 `git status`，尤其是自定义路径产生的文件。

代码采用 [MIT License](LICENSE)。该许可证不授予网站内容、商标或第三方题库的权利。
