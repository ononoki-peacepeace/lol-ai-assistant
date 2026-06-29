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




































2026-06-29

Devlog - LOL AI Assistant

今日主题：BP 后端闭环完成，开始进入产品化包装阶段

今天主要完成了 LOL AI Assistant 的 BP Assistant 后端闭环，并开始把项目从“脚本工具”整理成一个更像产品的形态。

---

1. BP 后端链路基本成型

目前 BP 功能已经形成完整 MVP 链路：

客户端截图
→ 识别 BP 槽位
→ 获取我方 / 敌方 picks 和 bans
→ 推断敌方位置与可能对线敌人
→ ChampionRecommender 推荐英雄
→ AICommentator 生成自然语言解释
→ 异步 RAG 生成搜索任务
→ 搜索结果进入 candidates
→ 人工 approve
→ merge 到正式知识库
→ 下次推荐读取正式知识库

这意味着 BP 不再只是临时脚本，而是已经具备了“识别、推荐、解释、学习、沉淀”的完整产品闭环。

---

2. 修正了选人界面左右逻辑

今天确认了一个重要事实：

无论实际是红方还是蓝方，客户端里我方选人始终显示在左边，敌方始终显示在右边。

因此后续逻辑应以：

左侧 = ally / 我方
右侧 = enemy / 敌方

而不是用真实蓝红方来反转。

这会影响后续 UI 和识别命名。短期可以继续沿用 "blue_picks / red_picks" 字段，但语义上应当视为 "left_picks / right_picks"。

---

3. Ban 位坐标和裁剪调试

今天新增了独立调试脚本：

debug_bp_slots.py

用于保存当前 BP 界面的槽位截图，包括：

full_frame.png
overlay_slots.png
blue_bans/
red_bans/
blue_picks/
red_picks/

通过截图确认了之前 Ban 位坐标偏差较大，并根据实际红框位置调整了 ban 位坐标。

同时确认 ban 位裁剪尺寸可通过：

BAN_TEMPLATE_SIZE

在 "config.py" 中统一控制。

当前建议值大约为：

BAN_TEMPLATE_SIZE = 48

后续可以根据 debug 图继续微调。

---

4. 推荐器接入正式知识库

今天确认并修正了推荐器逻辑，使 "ChampionRecommender" 能够真正读取正式知识库：

knowledge/bp/counters.json
knowledge/bp/champion_strength.json
knowledge/bp/team_combos.json

推荐器现在支持：

counter 正向 / 反向关系
team_combo list 格式
champion_strength 当前版本强度
多候选对线敌人加权
ban / 已选英雄过滤
推荐理由输出给 AICommentator

同时解决了推荐器本身正常，但 main.py / AICommentator 衔接字段不一致的问题。

---

5. 多位置英雄推断优化

之前多位置英雄容易导致：

预计对线敌人：未知

今天将逻辑改为：

根据敌方整体阵容进行位置分配
如果存在多个合理结果，就返回多个候选对线敌人

例如：

预计对线敌人：Yone，置信度：ambiguous，候选：Yone / Tristana

推荐器会将最可能的对线敌人给予更高 counter 权重，其他候选也会作为参考。

---

6. AI 输出推荐数量优化

今天排查了 AI 解释只讲少量推荐的问题。

最终确认需要同时检查：

main.py 是否传入完整 recommendations
ai_commentator.py 是否格式化时截断
prompt 是否明确要求输出多个推荐
max_tokens 是否足够

调整后，AICommentator 的职责进一步明确：

ChampionRecommender：决定推荐谁
AICommentator：决定怎么解释、以什么角色语气解释

因此 "ai_commentator.py" 不应删除，后续它会成为角色卡和二次元产品感的核心。

---

7. Candidate 审核与正式库合并

今天确认了 review app 的行为：

点 approve 只是把 candidate 标记为 approved
不会自动进入 knowledge/bp 正式库

因此补充了合并流程：

review_app.py
→ review_status = approved
→ merge_approved_proposals.py
→ knowledge/bp/*.json

并新增了启动脚本：

merge_approved.bat

用于 dry-run 预览后再正式合并 approved candidates。

---

8. 异步 RAG 队列统一

今天将之前的 RAG 任务结构整理为统一队列：

knowledge/search/bp_search_jobs.json

并新增：

tools/knowledge/search_job_queue.py

用于：

追加搜索任务
生成 job_key
去重
区分 jobs / completed_jobs / failed_jobs

同时给 "run_search_jobs.py" 增加了：

--loop
--idle-sleep

让它可以作为后台 worker 持续监听队列。

现在异步 RAG 流程为：

main.py 当前 BP
→ build_jobs_from_bp()
→ append_jobs()
→ bp_search_jobs.json
→ run_search_jobs.py --loop
→ generate_proposal_from_sources.py
→ proposals candidates

---

9. 异步 RAG 搜索内容优化

今天调整了异步 RAG 的搜索方向。

不再只搜索：

推荐英雄 vs 对线敌人

而是改为更合理的组合：

谁 counter 对线敌人
推荐英雄当前版本强度
推荐英雄与我方队友的配合
对线敌人当前版本强度

例如：

Who counters Darius 上单
Vladimir 上单 current patch strength
Vladimir synergy with allies
Darius 上单 current patch strength

其中 strength 类任务使用：

kind = strength

但实际仍会写入：

knowledge/proposals/champion_strength_candidates.json

---

10. .env 与 API Key 加载

今天发现 ".env" 文件不会自动成为系统环境变量，Python 脚本必须主动加载。

因此调整了相关脚本，使它们 import "config" 来加载 ".env"：

run_search_jobs.py
generate_proposal_from_sources.py
generate_proposal_from_text.py

并修复了 "ROOT_DIR" 使用前未定义的问题。

后续产品化方向是：

setup_keys.bat
→ 用户输入 DEEPSEEK_API_KEY / TAVILY_API_KEY
→ 写入 .env
→ Python 启动时自动加载

---

11. 启动脚本与产品化包装

今天新增了一组 bat 启动脚本：

start_bp.bat
start_rag_worker.bat
start_review.bat
merge_approved.bat
setup_keys.bat

这些脚本让项目从“每次手敲命令”变成了可双击启动的小产品雏形。

当前阶段还不适合直接打包 exe，因为项目仍在快速迭代，而且涉及：

OpenCV
mss
Streamlit
DeepSeek API
Tavily
本地 JSON 知识库
多个后台进程

因此当前包装路线确定为：

先 bat 启动器
再配置 / 角色卡
再前端壳
最后再考虑 exe

---

12. Git 清理与提交

今天整理了 ".gitignore"，将运行数据和敏感数据排除出版本控制：

.env
knowledge/raw/
knowledge/proposals/*_candidates.json
knowledge/proposals/merge_state.json
knowledge/search/bp_search_jobs.json
debug_output/
*.bak.*

并提交了：

Add launch scripts and debug tools

提交内容包括：

debug_bp_slots.py
bat 启动脚本
.env / RAG env 加载相关修复
停止追踪 proposals candidates 和 raw web snapshots

这让仓库更干净，运行数据不再污染 Git。

---

当前项目状态

目前可以认为：

BP Assistant 后端 MVP 基本完成

已经具备：

BP 识别
推荐系统
AI 解释
知识库
RAG 补全
候选审核
正式库合并
启动脚本
debug 工具

但还不是最终产品，因为还缺：

角色卡系统强化
统一后端输出结构
前端 UI
智能启动器
更完善的配置页面

---

明日计划

下一步建议优先做：

1. 增加 BP 有效性判断，避免不在 BP 界面时调用 AI / RAG
2. 设计 smart_launcher.py，检测到进入 BP 后再启动 BP Assistant
3. 补强角色卡后端
4. 统一 BP 后端输出 JSON，方便前端读取
5. 开始做 Streamlit / PySide6 前端壳

重点是继续从“功能可用”推进到“产品可用”。

---

今日总结

今天最大的进展是：

LOL AI Assistant 的 BP 后端闭环已经基本完成。

项目已经不只是一个识别 + 推荐脚本，而是具备了：

可运行
可解释
可学习
可审核
可沉淀
可启动

的 BP Agent 产品雏形。

下一阶段的核心不是继续堆算法功能，而是开始做产品包装：

角色卡
前端
智能启动
用户配置
更好的交互体验