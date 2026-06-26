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