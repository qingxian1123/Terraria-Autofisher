# Terraria 钓鱼助手

## 通过钓鱼音效和简单的内存补丁实现后台自动钓鱼

## 脚本思路

上钩时会有固定音效，脚本就拿这段声音当模板，监听系统正在播放的音频，和 `assets/splash_template.wav` 做匹配

默认冷却 2 秒，重新抛竿后会清掉旧音频，避免同一段声音反复触发。相似度阈值和冷却时间都能在界面里调：误触多就提高阈值，漏钩多就适当降低。

泰拉瑞亚原版不支持鼠标后台聚焦，所以引入了虚拟手柄来实现了后台的操作，通过 `vgamepad` 和 ViGEmBus 模拟 Xbox 360 手柄，按右扳机完成收竿和抛竿。当然游戏要开启多人模式，否则单人模式游戏后台会自动暂停

内存补丁主要用于输入控制，原版 Terraria 即使开启了后台手柄输入，失去焦点后仍会用 `delayUseItem` 挡住使用物品。所以脚本用 EasyHook 加载运行时补丁，再用 Harmony 补丁处理 `TriggersSet.CopyInto(Player)`。只有脚本发出的短时钓鱼指令有效、右扳机按下，而且目标是本地玩家时，才清除这个限制并恢复使用物品输入


## 开发与运行

环境：Windows、Python 3.12 或更新版本，以及用于构建后台输入组件的 .NET SDK。

```powershell
uv sync --locked
.venv\Scripts\python.exe main.py
```

主界面提供阈值、抛竿间隔和动作方式调整。「设置」中可启用后台输入或安装／修复
虚拟手柄驱动。后台模式需进入多人游戏，保持游戏音效开启。

## 测试与构建

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe tools/build.py
```

构建入口依次运行测试、编译 `injector` 的 Release 配置，再用 PyInstaller 打包。
任一步失败都会终止。首次构建需要联网还原 NuGet 依赖。

输出：

- `dist/TerrariaAutoFisher-v1.0.2.exe`：无控制台的单文件程序。
- `dist/TerrariaAutoFisher-v1.0.2.exe.sha256`：SHA-256 校验值。
- `injector/runtime-v2/`：后台输入组件，构建时自动打包。

程序内置声音模板、游戏图标和手柄驱动安装包，无需在 EXE 旁复制素材目录。
构建完成后可直接启动 EXE；真实钓鱼需要另行进入游戏验证。

## 项目结构

- `autofisher/app.py`：钓鱼任务、状态与设备生命周期。
- `autofisher/ui.py`：主窗口和设置窗口布局。
- `autofisher/widgets.py`、`theme.py`：像素控件、主题和素材加载。
- `autofisher/audio.py`、`actions.py`、`config.py`：音频识别、输入后端与游戏配置。
- `assets/`：音效与图标；游戏素材归属和来源见 `assets/ui/README.md`。
- `injector/`：后台输入的 .NET 组件源码。
- `tests/`：自动化验证；`tools/build.py`、`TerrariaAutoFisher.spec`：构建入口和打包配置。

