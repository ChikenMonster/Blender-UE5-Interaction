# Blender UE5 Interaction

[简体中文](#简体中文) | [English](#english)

---

## 简体中文

**面向 Blender 5.2 的 Unreal Engine 5.8 风格视口交互扩展。**

**开发者 / 版权所有者：** Chiken_Monster  
**维护联系邮箱：** 1130319586@qq.com

Blender UE5 Interaction 为 Blender 的三维视口提供可选的 UE 风格工具快捷键、鼠标导航，以及按住鼠标右键（RMB）进行环顾和飞行的操作方式。插件同时支持 **Object Mode（物体模式）**，以及独立启用的 **Mesh Edit Mode（网格编辑模式）** 功能。

插件尽可能调用 Blender 原生工具和操作器，通过自身的 Add-on Keymap 管理快捷键，不直接改写用户的 Blender 键位配置。

> **版本：** 0.2.6  
> **最低 Blender 版本：** 5.2.0  
> **Blender 5.3：** 尚未验证

### 功能概览

- **物体模式工具快捷键：** `Q` 选择、`W` 移动、`E` 旋转、`R` 缩放。
- **视口辅助操作：** `F` 聚焦选中对象；`G` 切换视口 Overlay（仅近似 UE 的 Game View，并非完全替代）。
- **Alt + 鼠标导航：** 在物体模式下环绕、平移与推拉视图。
- **右键环顾／飞行：** 按住右键移动鼠标环顾，通过键盘飞行，并使用滚轮调节速度。
- **网格编辑模式支持：** 独立的右键飞行模式，以及可选的部分 Industry Compatible 风格工具键位。
- **Extrude Region 工具：** `Ctrl+E` 激活 Blender 原生的 **Extrude Region 工具**；每次激活时方向模式默认为 `XYZ`，工具栏中仍可手动切换为 `Normal`。
- **原生 Edge Menu：** 启用网格编辑模式的 Industry 键位后，`Ctrl+Shift+E` 打开 Blender 原生边操作菜单。
- **诊断工具：** 只读键位冲突审计，以及内置的生命周期和数学自检。

### 安装

#### 安装扩展 ZIP

1. 使用为本插件构建的 ZIP，压缩包根目录应包含 `blender_manifest.toml` 及 Python 模块。
2. 打开 Blender 的 **Edit → Preferences → Get Extensions**。
3. 选择 **Install from Disk...**，选中 ZIP，必要时启用扩展。
4. 打开 **3D Viewport → Sidebar（`N`）→ UE Interaction**，配置各项功能。

#### 从源码构建

源码目录根层级必须包含 `blender_manifest.toml` 和 `__init__.py`。在该目录执行：

```bash
blender --command extension build --source-dir . --output-dir ./dist
blender --command extension validate ./dist/blender_ue5_interaction-0.2.6.zip
```

如果系统环境变量 `PATH` 中找不到 `blender`，请改用 Blender 可执行文件的完整路径。生成的 ZIP 文件名由 `blender_manifest.toml` 中的扩展 ID 和版本决定。

### 默认行为

首次安装后，**默认仅开启 `F`（聚焦选中对象）和 `G`（切换 Overlay）**；其他 UE 风格快捷键及导航模式均需在扩展偏好设置或 **UE Interaction** 侧边栏中手动启用。

| 设置 | 默认状态 |
| --- | --- |
| 物体模式 `Q/W/E/R` 工具快捷键 | 关闭 |
| 物体模式 `F` 聚焦选中对象 | **开启** |
| 物体模式 `G` 切换 Overlay | **开启** |
| 物体模式 Alt + 鼠标导航 | 关闭 |
| 物体模式右键环顾／飞行 | 关闭 |
| 网格编辑模式右键飞行 | 关闭 |
| 网格编辑模式 Industry 工具键位 | 关闭 |

**当前界面细节：** 当物体模式 `Q/W/E/R` 工具快捷键总开关关闭时，偏好设置和侧边栏中的 `F`、`G` 选项会显示为不可编辑，但已启用的 `F`、`G` 快捷键仍然有效。如需修改这两项，先临时开启物体模式工具快捷键总开关，调整 `F`／`G` 后可再次关闭总开关。

### 操作说明

#### Object Mode（物体模式）

开启 **Q/W/E/R tool keys (Object Mode)** 后，启用四个工具快捷键。`F` 与 `G` 有独立的启用状态，默认开启。

| 输入 | 功能 | 对应开关 |
| --- | --- | --- |
| `Q` | 框选工具（Select Box） | 物体模式工具快捷键 |
| `W` | 移动工具（Move） | 物体模式工具快捷键 |
| `E` | 旋转工具（Rotate） | 物体模式工具快捷键 |
| `R` | 缩放工具（Scale） | 物体模式工具快捷键 |
| `F` | 聚焦选中对象 | Focus selected |
| `G` | 切换视口 Overlay | Overlay toggle |
| `Alt + LMB` 拖动 | 环绕视图（Orbit） | Alt + 鼠标导航 |
| `Alt + MMB` 拖动 | 平移视图（Pan） | Alt + 鼠标导航 |
| `Alt + RMB` 拖动 | 推拉视图（Dolly） | Alt + 鼠标导航 |

Alt + 鼠标导航支持透视与正交视图，但不在相机视图内生效；右键环顾／飞行仅适用于**透视视图**。

启用 **RMB look + WASD fly** 后，按住鼠标右键进行导航：

| 按住 RMB 期间的输入 | 功能 |
| --- | --- |
| 鼠标移动 | 环顾视角 |
| `W` / `S` | 前进／后退 |
| `A` / `D` | 向左／向右 |
| `Q` / `E` | 沿世界 Z 轴下降／上升 |
| `R` / `F` | 沿视角局部上方向上升／下降 |
| 鼠标滚轮 | 减小／增大飞行速度倍率 |
| 松开 RMB | 结束飞行 |
| `Esc` | 取消飞行 |

短促点击 RMB 时，插件会尝试打开 Blender 原生右键上下文菜单，而非进入持续飞行。具体限制见[已知限制](#已知限制)。

#### Mesh Edit Mode（网格编辑模式）

编辑模式的两项功能**相互独立，均需手动开启**。其作用范围仅限三维视口中的网格编辑，不向 Curve、Armature、Sculpt、UV、Node 或 Text 等上下文新增工具快捷键。

启用 **Edit Mesh industry keys (Q/W/E/R + Ctrl+E)** 后，使用以下部分 Industry Compatible 风格映射：

| 输入 | 功能 |
| --- | --- |
| `Q` | 框选工具（Select Box） |
| `W` | 移动工具（Move） |
| `E` | 旋转工具（Rotate） |
| `R` | 缩放工具（Scale） |
| `Ctrl+E` | 激活上下文相关的 **Extrude Region 工具**，方向模式默认 `XYZ` |
| `Ctrl+Shift+E` | 打开 Blender 原生 Edge Menu |

`Ctrl+E` 执行的是**激活工具**，而非立即完成一次挤出。激活后仍可在工具栏的 `XYZ` 与 `Normal` 之间手动切换。插件在网格编辑模式中**不会**重新映射 `Ctrl+B`、`1/2/3`（顶点／边／面选择）、`F`、`G` 或 `S`。

**原生快捷键变化：** 开启 Industry 键位后，`E` 不再直接执行 Blender 默认挤出操作，`Ctrl+E` 也不再打开 Edge Menu；Edge Menu 移至 `Ctrl+Shift+E`。在受影响的三维视口上下文中，`Q` 还会取代 Quick Favorites。关闭该功能即可恢复原有 Blender 键位。

启用 **Edit Mesh RMB + WASD/QE fly** 后，可在网格编辑的透视视图中按住 RMB 飞行：

| 按住 RMB 期间的输入 | 功能 |
| --- | --- |
| 鼠标移动 | 环顾视角 |
| `W` / `S` | 前进／后退 |
| `A` / `D` | 向左／向右 |
| `Q` / `E` | 沿世界 Z 轴下降／上升 |
| 鼠标滚轮 | 调节与物体模式共享的飞行速度倍率 |
| 松开 RMB / `Esc` | 结束／取消飞行 |

**网格编辑模式**下，多方向组合输入会进行速度归一化，避免斜向飞行更快。该模式不使用 `R`／`F` 控制飞行，也不支持独立的 Alt + 鼠标导航。右键飞行过程中，移动按键由导航操作器接管，不会用于编辑网格几何；退出飞行后恢复当前 Blender／插件键位行为。

### 配置

通过 **3D Viewport → `N` → UE Interaction** 或扩展偏好设置调整。

| 设置 | 默认值 | 范围 |
| --- | --- | --- |
| 飞行基础速度 | `5.0` 世界单位／秒 | `0.05–100.0` |
| 飞行速度倍率 | `1.0×` | `1.0×–20.0×` |
| 鼠标环顾灵敏度 | `0.25` 度／像素 | `0.01–3.0` |
| 反转垂直环顾方向 | 关闭 | 开／关 |
| RMB 拖动阈值 | `5` 像素 | `0–50` |
| RMB 单击时间阈值 | `250` 毫秒 | `50–1000` |

物体模式与网格编辑模式共享飞行速度倍率；在任一模式飞行期间使用滚轮，都会更新同一个倍率值。

### 安全性与诊断

- **作用域限定的键位映射：** 插件在 Blender 的 Add-on Keyconfig 内创建映射，不直接修改 User／Default Keyconfig，也不调用 `save_userpref`。
- **资源清理：** 禁用或卸载扩展时，会移除其创建的 KeyMapItem，并请求取消正在运行的导航操作器。
- **仅修改视口状态：** RMB 飞行更新的是 `RegionView3D` 视图状态，不会主动变换对象、编辑网格几何或移动场景相机。
- **Self Test：** 运行内置的数学与键位生命周期检查，结果显示在 Blender 中并输出至控制台。
- **Audit Keymaps：** 只读检查已注册键位与潜在原生快捷键冲突，不会修改键位设置。

这些诊断功能不能替代不同 Blender 版本及键位配置下的实际回归测试。

### 已知限制

1. **RMB 上下文菜单：** 在配置的时间阈值内（默认 250 毫秒）、且移动距离不超过拖动阈值（默认 5 像素）时松开右键，才能转发 Blender 原生上下文菜单。按住不移动但超过时间阈值，可能无法打开菜单。
2. **启用后有意替换部分原生快捷键：** 物体模式的 `R` 会替换默认旋转操作，`G` 会将 Grab 替换为 Overlay 切换；网格编辑模式 Industry 键位会替换原生 `E`、`Ctrl+E`，并在对应视口中使 `Q` 优先于 Quick Favorites。
3. **Game View 近似：** `G` 仅切换 Blender 视口 Overlay，不等同于 Unreal Engine 的 Game View，也不影响最终渲染输出。
4. **模式与视图限制：** RMB 飞行只在透视视图生效；编辑模式飞行只支持网格编辑。Alt + 鼠标导航只适用于物体模式，且不支持相机视图。
5. **编辑模式导航：** `R/F` 不用于垂直飞行；Alt + 鼠标导航尚未适配编辑模式。
6. **多视口：** 分屏／多个三维视口的交互尚未完成全面验证。
7. **版本覆盖：** 目标版本为 Blender 5.2；Blender 5.3 尚未验证。清单中的最低版本 `5.2.0` 不代表保证兼容所有后续版本。
8. **键盘自动化：** Blender 的 GHOST／Raw Input 输入路径可能无法将合成键盘事件视为真实按键，因此需要使用物理键盘进行交互测试。

### 项目结构

用于构建扩展的源码结构如下：

```text
blender_manifest.toml
__init__.py
preferences.py
keymaps.py
operators.py
navigation.py
diagnostics.py
ui.py
README.md
LICENSE
```


### 许可证

**GNU General Public License v3.0 or later（`GPL-3.0-or-later`）** — 参见 [LICENSE](LICENSE)。

Copyright © 2026 Chiken_Monster。

---

## English

**Unreal Engine 5.8–style viewport controls for Blender 5.2.**

**Developer / Copyright holder:** Chiken_Monster  
**Maintainer contact:** 1130319586@qq.com

Blender UE5 Interaction is a Blender extension that adds optional UE-style tool shortcuts, mouse navigation, and right-mouse-button (RMB) look/fly controls to the 3D Viewport. It supports both **Object Mode** and a separate, opt-in set of controls for **Mesh Edit Mode**.

The extension uses Blender's native tools and operators where possible. It manages its own add-on keymap entries rather than rewriting the user's Blender key configuration.

> **Version:** 0.2.6  
> **Minimum Blender version:** 5.2.0  
> **Blender 5.3:** not verified

### Features

- **Object Mode tools:** `Q` Select, `W` Move, `E` Rotate, `R` Scale.
- **Viewport helpers:** `F` frame the selection; `G` toggle viewport overlays (an approximation of UE's Game View, not an exact replacement).
- **Alt + mouse navigation:** orbit, pan, and dolly in Object Mode.
- **RMB look/fly:** look around with the mouse and fly with keyboard movement keys; adjust speed with the mouse wheel.
- **Mesh Edit Mode support:** a separate RMB flight mode and an optional, partial Industry Compatible tool-key layout.
- **Extrude Region tool:** `Ctrl+E` activates Blender's Extrude Region **tool**, defaulting its direction mode to `XYZ` on each activation. `Normal` remains selectable in the tool header.
- **Native Edge Menu:** `Ctrl+Shift+E` opens Blender's original Edge Menu when the Mesh Edit Mode industry keys are enabled.
- **Diagnostics:** a read-only keymap audit and a built-in lifecycle/math self-test.

### Installation

#### Install an extension ZIP

1. Use a ZIP built for this extension, with `blender_manifest.toml` and the Python modules at the archive root.
2. In Blender, open **Edit → Preferences → Get Extensions**.
3. Use **Install from Disk...**, select the extension ZIP, and enable the extension if necessary.
4. Open **3D Viewport → Sidebar (`N`) → UE Interaction** to configure its features.

#### Build from source

The extension source directory must contain `blender_manifest.toml` and `__init__.py` at its root. From that directory, run:

```bash
blender --command extension build --source-dir . --output-dir ./dist
blender --command extension validate ./dist/blender_ue5_interaction-0.2.6.zip
```

Replace `blender` with the executable path if it is not available on your `PATH`. The output ZIP name follows the extension ID and version in `blender_manifest.toml`.

### Default behavior

On initial installation, **only `F` (focus selected) and `G` (toggle overlays) are enabled**. All other UE-style shortcuts and navigation modes are off until you enable them in the extension preferences or the **UE Interaction** sidebar.

| Setting | Default |
| --- | --- |
| Object Mode `Q/W/E/R` tool keys | Off |
| Object Mode `F` focus selected | **On** |
| Object Mode `G` overlay toggle | **On** |
| Object Mode Alt + mouse navigation | Off |
| Object Mode RMB look/fly | Off |
| Mesh Edit Mode RMB flight | Off |
| Mesh Edit Mode industry tool keys | Off |

**Current UI detail:** the `F` and `G` setting controls are disabled in the preferences/sidebar when Object Mode `Q/W/E/R` tool keys are off, even though the enabled `F`/`G` shortcuts still work. To change either setting, temporarily enable Object Mode tool keys, adjust `F`/`G`, then turn Object Mode tool keys off again if desired.

### Controls

#### Object Mode

Enable **Q/W/E/R tool keys (Object Mode)** for the four tool shortcuts. `F` and `G` have their own settings and are enabled by default.

| Input | Action | Feature toggle |
| --- | --- | --- |
| `Q` | Select Box tool | Object Mode tool keys |
| `W` | Move tool | Object Mode tool keys |
| `E` | Rotate tool | Object Mode tool keys |
| `R` | Scale tool | Object Mode tool keys |
| `F` | Frame selected objects | Focus selected |
| `G` | Toggle viewport overlays | Overlay toggle |
| `Alt + LMB` drag | Orbit | Alt + mouse navigation |
| `Alt + MMB` drag | Pan | Alt + mouse navigation |
| `Alt + RMB` drag | Dolly | Alt + mouse navigation |

Alt + mouse navigation is available in perspective and orthographic views, but not in camera view. RMB look/fly is limited to **perspective view**.

When **RMB look + WASD fly** is enabled, hold the right mouse button to navigate:

| Input while RMB is held | Action |
| --- | --- |
| Mouse movement | Look around |
| `W` / `S` | Forward / backward |
| `A` / `D` | Left / right |
| `Q` / `E` | Descend / ascend along world Z |
| `R` / `F` | Ascend / descend along view-local up |
| Mouse wheel | Decrease / increase flight-speed multiplier |
| Release RMB | End flight |
| `Esc` | Cancel flight |

A short RMB click attempts to open Blender's native context menu instead of starting a flight session. See [Known limitations](#known-limitations).

#### Mesh Edit Mode

Both Edit Mode options are **independent, opt-in settings**. They affect mesh editing in the 3D Viewport only; they do not add tool shortcuts to Curve, Armature, Sculpt, UV, Node, or Text editors.

Enable **Edit Mesh industry keys (Q/W/E/R + Ctrl+E)** for this partial Industry Compatible layout:

| Input | Action |
| --- | --- |
| `Q` | Select Box tool |
| `W` | Move tool |
| `E` | Rotate tool |
| `R` | Scale tool |
| `Ctrl+E` | Activate the context-sensitive Extrude Region **tool**, default direction `XYZ` |
| `Ctrl+Shift+E` | Open Blender's native Edge Menu |

`Ctrl+E` **selects a tool**; it is not a one-shot extrude command. The tool header can still switch between `XYZ` and `Normal`. The extension deliberately does **not** remap `Ctrl+B`, `1/2/3` (vertex/edge/face selection), `F`, `G`, or `S` in Mesh Edit Mode.

**Expected shortcut changes:** `E` no longer invokes Blender's default extrude action, and `Ctrl+E` no longer opens the Edge Menu while the industry-key option is on. The Edge Menu moves to `Ctrl+Shift+E`. `Q` also replaces Quick Favorites in the affected 3D Viewport context. Disable the option to restore Blender's underlying shortcuts.

Enable **Edit Mesh RMB + WASD/QE fly** to navigate while editing a mesh in perspective view:

| Input while RMB is held | Action |
| --- | --- |
| Mouse movement | Look around |
| `W` / `S` | Forward / backward |
| `A` / `D` | Left / right |
| `Q` / `E` | Descend / ascend along world Z |
| Mouse wheel | Adjust the shared flight-speed multiplier |
| Release RMB / `Esc` | End / cancel flight |

Diagonal/composite flight input is speed-normalized in **Mesh Edit Mode**. `R` and `F` do not control flight in this mode. The separate Alt + mouse navigation feature is **not** applied to Mesh Edit Mode. While RMB flight owns input, movement keys are consumed by the navigation operator rather than acting on mesh geometry; outside that session, the current Blender/extension keymap applies.

### Configuration

Use **3D Viewport → `N` → UE Interaction** or the extension's preferences.

| Setting | Default | Range |
| --- | --- | --- |
| Fly base speed | `5.0` world units/s | `0.05–100.0` |
| Fly speed multiplier | `1.0×` | `1.0×–20.0×` |
| Mouse-look sensitivity | `0.25` degrees/pixel | `0.01–3.0` |
| Invert vertical look | Off | On / Off |
| RMB drag threshold | `5` pixels | `0–50` |
| RMB click timeout | `250` ms | `50–1000` |

The flight-speed multiplier is shared between Object Mode and Mesh Edit Mode. Mouse-wheel adjustments during either flight mode update that shared value.

### Safety and diagnostics

- **Scoped keymaps:** the extension creates bindings in Blender's add-on key configuration. It does not directly write to the user or default key configurations or invoke `save_userpref`.
- **Cleanup:** disabling or unregistering the extension removes its owned keymap items and requests cancellation of active navigation operators.
- **Viewport-only navigation:** RMB flight updates viewport state (`RegionView3D`); it does not intentionally transform objects, edit mesh geometry, or move the scene camera.
- **Self Test:** runs built-in math and keymap-lifecycle checks; results are reported in Blender and printed to its console.
- **Audit Keymaps:** examines installed bindings and potential native-keymap conflicts without changing keyboard mappings.

These diagnostic tools are not substitutes for hands-on regression testing in each Blender version and key configuration.

### Known limitations

1. **RMB context menu:** a click must be released within the configured timeout (default 250 ms) without exceeding the drag threshold (default 5 px) to be forwarded to Blender's native context menu. A longer stationary press may not open it.
2. **Shortcut conflicts are intentional when enabled:** Object Mode `R` replaces the native rotate operation; Object Mode `G` replaces Grab with overlay toggle. Mesh Edit Mode industry keys replace native `E` and `Ctrl+E`, and `Q` takes precedence over Quick Favorites within the affected viewport context.
3. **Game View approximation:** `G` only toggles Blender viewport overlays; it is not Unreal Engine's Game View and does not affect render output.
4. **Mode/view restrictions:** RMB flight works only in perspective view; Edit Mode RMB flight is limited to mesh editing. Alt + mouse navigation is limited to Object Mode and excludes camera view.
5. **Edit Mode navigation:** `R/F` are not vertical-flight keys; Alt + mouse navigation is not implemented for Edit Mode.
6. **Multi-viewport behavior:** split/multiple 3D Viewport interaction has not been fully verified.
7. **Version coverage:** Blender 5.2 is the target version; Blender 5.3 has not been verified. The manifest specifies a minimum of 5.2.0, not a guarantee for all later releases.
8. **Keyboard automation:** synthetic keyboard events may not reproduce physical keyboard input in Blender's GHOST/Raw Input path; test real shortcuts interactively.

### Project layout

The source layout used to build the extension is:

```text
blender_manifest.toml
__init__.py
preferences.py
keymaps.py
operators.py
navigation.py
diagnostics.py
ui.py
README.md
LICENSE
```


### License

**GNU General Public License v3.0 or later (`GPL-3.0-or-later`)** — see [LICENSE](LICENSE).

Copyright © 2026 Chiken_Monster.
