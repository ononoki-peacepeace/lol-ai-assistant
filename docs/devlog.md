2026-06-27

1.虚拟环境

cd /d D:\lol_ai_assistant
.\.venv\Scripts\activate

---

2. Riot API 与国服账号不适配

一开始计划通过 Riot API 获取玩家最近 20 局常用英雄，但后来发现目标用户是国服玩家，而国服 WeGame / QQ 账号和 Riot Developer Portal 的账号体系不一致。

因此决定暂时不把 Riot API 作为核心依赖，优先做基于屏幕截图的 BP 识别模块。

---

3. 固定坐标不适配问题

最初使用写死的 Ban/Pick 区域坐标，但不同窗口大小、分辨率、客户端位置都会导致截图裁剪不准。

为了解决这个问题，加入了 "calibration.py" 校准工具，让用户手动点击 Ban/Pick 位置，并把坐标保存到：

data/layout.json

---

4. 校准工具 UI 遮挡问题

"calibration.py" 最初加入了左上角提示文字和右侧 "Selected" 黑色面板，但这些提示层会遮挡游戏 BP 界面，影响点位校准。

后面删除了：

- 右侧 "Selected" 黑框
- 左上角黄色提示文字
- 顶部半透明提示背景

只保留点击后的绿色圆圈、编号和终端输出反馈。

---

5. 英雄头像资源下载问题

为了避免手动截图英雄头像，改为从 Riot Data Dragon 下载英雄头像。

中途遇到问题：

下载英雄头像时出现 SSL 报错：

SSLError: EOF occurred in violation of protocol

解决方式是给下载脚本加入：

- 已存在文件跳过
- 下载失败重试
- 下载失败不让整个脚本崩溃

---

6. Data Dragon 方形头像与国服 BP 圆形头像不匹配

Data Dragon 下载的是标准方形英雄头像，但国服 BP 界面里的头像是圆形头像，并带有金色边框和黑色背景, 且用户手动校准坐标可能有偏差。

最初使用 "cv2.matchTemplate" 做整图模板匹配，效果不稳定。
后续改进思路是：

- 只比较头像中心区域
- 尽量忽略边框和背景
- 使用灰度结构特征和 HSV 颜色直方图综合打分

*待改进*

---

7. 空 Ban / 空 Pick 被误识别成英雄

实时运行 "watch-bp" 时，空位有时会被识别成 "Nunu"、"Sona"、"MissFortune" 等英雄。

原因是程序只知道英雄头像，不知道“空位”长什么样，所以会强行在英雄库里找最像的一个。

解决思路是加入：

assets/empty_slots/

把空 Ban / 空 Pick 位作为负样本。识别时先判断是不是空位，如果像空位就返回 "None"。

测试中发现，英雄如果能正常识别，通常是正确的，如果是未识别，则错误很大，连本来的英雄都无法出现在识别前三中

*识别算法应该要改进很多*

---



8. "watch-bp" 实时识别仍不完全稳定

"watch-bp" 已经可以实时监听 BP 状态，但识别结果仍然可能出现：

- 少量未识别
- 偶发误识别
- 空位误判

当前策略是：优先避免误识别，允许少量 "暂无 / Unknown"。
后续可以继续加入连续多帧确认、置信度差距判断和更多空位样本。

---

9. Git 使用问题

第一次使用 Git 上传项目，出了很多问题

如网络问题

第一次执行：

git push -u origin main

出现：

Recv failure: Connection was reset

原因是命令行 Git 没有走 Clash 代理。

后面通过设置 Git 代理解决：

git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890


等

---



总结

今天主要完成了 BP 识别模块的基础工程化流程，包括：

- 项目环境搭建
- BP 坐标校准
- 英雄头像资源下载
- OpenCV 英雄识别
- 空位负样本识别
- 实时 "watch-bp" 监听
- GitHub 仓库上传

当前项目还不完善，但已经从本地实验代码推进成了一个可持续迭代的 GitHub 项目。






























































2026-06-27
Devlog：LOL AI Assistant 上单 MVP 与知识库方向调整

今日进展

今天主要围绕 LOL AI Assistant 的 BP 推荐系统继续推进，重点从“自动化 RAG 大量生成知识库”转向“先构建可稳定演示的上单 MVP”。

前面已经跑通了 AI-generated knowledge proposal 的基本链路：
Tavily 搜索网页 → 清洗网页内容 → DeepSeek 抽取结构化 JSON → schema 校验 → 写入 proposals。
在测试 Aatrox、Darius 等上单数据时，确认系统已经可以从 OP.GG 等数据源中生成 counter / champion strength / team combo 候选数据。

不过进一步思考后，发现如果项目一开始完全依赖 RAG 或多人共享知识库，容易出现几个问题：

1. 初始状态下本地知识库为空，项目演示效果不稳定。
2. Web/RAG 抽取受网页结构影响较大，部分站点正文会被图片、导航、广告污染。
3. 如果没有用户使用，多人共享学习机制暂时无法形成价值。
4. 只靠 AI 动态分析，推荐结果可能不稳定，也不方便调试。

因此今天确定了新的 MVP 路线：
先做上单 BP Assistant。

当前产品方向调整

原先的方向偏向：

- 全位置 BP 识别
- 全英雄 counter 数据
- 多人共享知识库
- 按需 RAG 自动补全
- 后续云端共享与网站审核

今天调整为更现实的分阶段路线：

1. 先完成本地上单 MVP。
2. 只维护上单相关的 counter、强势英雄、阵容配合。
3. 本地规则库保证项目一打开就能用。
4. RAG 暂时作为后续增强工具，用于补缺和更新。
5. 等本地版稳定后，再考虑在线共享、多人反馈和云端知识库。

当前定位变成：

«一个基于屏幕识别、本地规则库、RAG 补全和 AI 解释的英雄联盟上单 BP 智能推荐助手。»

今日确定的知识库策略

暂时不再追求全量自动录入，而是先人工维护一批可靠的上单基础知识。

主要维护三个 JSON：

knowledge/bp/counters.json
knowledge/bp/champion_strength.json
knowledge/bp/team_combos.json

其中：

- "counters.json"：记录上单英雄之间的 counter 关系。
- "champion_strength.json"：记录当前或基础强度较高的上单英雄。
- "team_combos.json"：记录上单与打野、中单、下路、辅助之间的阵容配合。

暂定优先覆盖 20 个常见上单英雄：

Aatrox
Darius
Garen
Malphite
Ornn
Camille
Fiora
Jax
Renekton
Riven
Gnar
Kennen
Mordekaiser
Gwen
Sion
Poppy
K'Sante
Sett
Teemo
Irelia

今日生成/规划的基础数据

今天先准备了一版上单 MVP 种子库，包括：

1. 部分上单 counter 关系
   例如 Aatrox、Darius、Camille、Malphite、Jax、Fiora、Ornn 等英雄的 good_against / bad_against。

2. 部分上单强势英雄数据
   例如 Aatrox、Jax、Camille、Fiora、Malphite、Ornn、Darius 等英雄的基础强度记录。

3. 部分上单阵容配合
   例如：
   
   - Malphite + Yasuo
   - Camille + Galio
   - Ornn + Jinx
   - Malphite + Miss Fortune
   - Aatrox + Sejuani
   - Jax + Lulu
   - Fiora + Twisted Fate
   - Ornn + Orianna
   - Malphite + Orianna
   - Sion + Senna

这些数据后续会先作为本地 approved seed data 使用，而不是 pending proposals。

今日遇到的问题

1. team_combos.json 数据结构不匹配

当前 "team_combos.json" 是 list 结构：

[
  {
    "id": "combo_malphite_yasuo_001",
    "champions": ["Malphite", "Yasuo"],
    "score": 9
  }
]

但 "champion_recommender.py" 中原本按 dict 读取：

candidate_info = self.team_combo.get(candidate_id, {})

导致报错：

AttributeError: 'list' object has no attribute 'get'

解决方向：
把 "_score_team_combo()" 改为遍历 list，并判断 candidate 是否在 combo 的 "champions" 中，同时检查我方已选英雄是否命中该组合。

2. counter 关系可能没有真正参与评分

当前怀疑推荐英雄一直不变，是因为 counter 关系方向和推荐器读取方向不一致。

例如 JSON 中可能写的是：

"Aatrox": {
  "bad_against": [
    {
      "champion": "Poppy"
    }
  ]
}

这表示 Aatrox 怕 Poppy。

但推荐器如果只查：

self.counters.get(candidate_id, {})

当 candidate 是 Poppy 时，它不会反向查到 Aatrox 的 bad_against，因此不会给 Poppy 加分。

解决方向：
重写 "_score_counters()"，同时支持两种方向：

1. "Poppy.good_against Aatrox"
2. "Aatrox.bad_against Poppy"

这样无论 counter 数据从哪个视角录入，都能正确参与推荐。

3. 敌方位置推断仍然可能 unknown

当前日志里出现：

预计对线敌人：未知，置信度：unknown

这说明 RoleInferer 仍然没有成功推断敌方上单。可能原因包括：

- 敌方英雄没有识别出来。
- "champion_tags.json" 缺少对应英雄位置标签。
- 英雄 ID 不一致，例如 "K'Sante" / "KSante"。
- 敌方阵容不完整，无法确定具体位置。

后续需要继续检查 "enemy_picks" 实际识别结果和 "champion_tags.json" 是否一致。

今日关键决策

今天最大的决策是：
先不要追求云端共享和全量 RAG，先做一个本地可演示、可解释、可稳定运行的上单 MVP。

当前推荐系统的合理分工：

本地程序：
负责识别 BP、检索本地知识、生成候选、粗略打分、判断缺失知识。

本地规则库：
负责提供稳定、可控、可调试的 counter / strength / combo 数据。

AI：
负责根据本地 evidence 做自然语言分析和最终解释。

RAG：
后续用于本地知识缺失时补全，不再作为第一阶段主入口。

这样项目既不会变成纯手写规则库，也不会完全依赖不稳定的 AI 输出。

明日计划

1. 修复 "_score_team_combo()"，让 list 格式的 "team_combos.json" 正常参与评分。
2. 修复 "_score_counters()"，支持正向和反向 counter 关系。
3. 加入 "[SCORE DEBUG]" 输出，查看每个候选英雄的：
   - total_score
   - counter_score
   - team_combo_score
   - strength_score
   - tag/role/comp score
4. 检查为什么敌方上单位置推断为 unknown。
5. 确认推荐结果是否会随着敌方上单变化而变化。
6. 重新测试几个固定 BP 场景：
   - 敌方 Aatrox
   - 敌方 Darius
   - 敌方 Camille
   - 敌方 Malphite
7. 等本地上单推荐稳定后，再恢复 AI explain 输出。

当前阶段总结

今天项目从“想做一个很大的在线共享 BP AI 平台”收缩到了更可落地的版本：

«先做一个本地上单 BP Assistant，基于规则库和少量 AI 解释完成稳定 MVP，后续再用 RAG 和云端共享逐步升级。»

这个方向更现实，也更适合当前开发阶段。
只要上单 MVP 跑通，后续扩展到其他位置、在线共享、社区反馈和自动知识更新都会更自然。