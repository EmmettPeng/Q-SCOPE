# QSCN 更新日志

本项目从 `demo v0.1` 起记录所有可识别的版本变化。版本条目描述用户可见行为、分析规则、数据兼容性和验证结果；尚未发布的修改先写入“未发布”。

## 未发布

- 暂无。

## QSCN v0.3.2 — 2026-08-10

### Windows/macOS 封装与发布

- 新增基于 Docker Desktop 的 Windows x64、Intel Mac 与 Apple Silicon Mac 发布包；两个平台均提供启动、停止、状态、日志、更新、备份与确认恢复入口。
- 修正 Debian 软件包锁定方式：固定 HMMER 3.4 与 Prodigal 2.6.3，但不再绑定 amd64/arm64 各自不同的构建后缀。
- 新增 GHCR 发布 Compose，镜像仅绑定 localhost，使用固定的 v0.3 数据卷名称；发布安装包将镜像锁定到多架构 manifest digest，更新不删除用户数据。
- 新增 GitHub Actions：前后端检查、`linux/amd64`/`linux/arm64` 真实容器构建与测试、PowerShell 语法检查、GHCR 发布、构建证明、漏洞扫描和 GitHub Release 安装包。
- CI 仅在 `main` push 或 pull request 上运行，避免功能分支 push 与 PR 事件重复执行同一套多架构构建。
- QSP 与 KEGG QS 两个预设数据库继续随镜像提供；每个目标架构均使用镜像内 HMMER 重新 `hmmpress`，不发布仓库中本机生成的 `.h3*`。
- 项目负责人于 2026-08-10 确认随 QSCN 分发当前 QSP/KEGG 数据副本；第三方数据仍不属于 Apache-2.0，未确认的上游版本、构建链和适用条款继续如实标注。
- 本次封装不改变 schema `3`、hit/capability/scope 规则 `1.0`/`2.0`/`1.0`、数据库内容、阈值或分析推断语义，既有 v0.3 run 无需重扫。

### 自定义数据库导入

- 自定义数据库主入口改为分别选择一个 HMM 库和一个 UTF-8、制表符分隔的 TSV/TXT Pathway 表；导入弹窗收集名称、版本、来源、原生分类和 GA/E-value 阈值，不再要求用户手写 JSON。
- 新增带五列表头和两行 QSP 示例的 TSV 模板下载。多 profile 与 reference 使用分号分隔；后端提供表头、行号、profile 映射、阈值和版本冲突的稳定校验错误。
- 原始 HMM 与表格作为不可变资产保留，QSCN 生成规范化 manifest、记录校验和/provenance 并以 bundled HMMER 重建索引。旧 ZIP + `manifest.json` API 导入继续兼容。
- schema 仍为 `3`，hit/capability/scope 规则版本仍为 `1.0`/`2.0`/`1.0`；既有数据库和 run 无需迁移、重解释或重扫。

### 约定

- 后续每次版本改动都必须在这里记录。
- 生物学规则、阈值或数据库变化必须注明对既有结果的影响，并同步更新测试。
- 修复若改变分析结果，必须说明是否需要重新运行 HMMER，或只需创建新的 interpretation。

## QSCN v0.3.1 — 2026-08-07

### 导出与运行进度

- 修正 Cytoscape SIF：Pathway ID 采用可逆百分号编码的 interaction type，保留 Pathway 多重边、自连接和孤立节点，并确定性输出、去除完全重复边；网络 JSON/TSV 与生物学结果不变。
- Genome Worker 改为先完成全部 Prodigal、再执行全部 hmmscan；总进度不再回退，Run API 新增只读 `progress_detail`，失败时保留最后真实阶段与百分比。

### Interpretation 与能力表

- Pathway 页用统一的 Interpretation settings 弹窗替代三个同级操作；scope/rules 使用草稿，一次 Apply 创建一个 interpretation，取消不修改当前结果。
- Pathway Capabilities 增加全文搜索、Sample/Pathway/Role/Call 筛选、六列排序、清空操作和结果计数；这些交互不改变 interpretation 或 TSV 导出。

### 文案与证据边界

- 完成 264 项用户可见文本审阅：统一使用 sample、Pathway evidence、criteria met、no qualifying evidence detected 和 potential communication 等 evidence-first 表述，避免把规则达标或网络边写成已验证生物学能力。
- 上传、样本计数和网络节点不再一律称为 genome/microorganism；蛋白与核酸样本分别显示 amino acids 和 nucleotides，进度优先显示样本名称及 `n/N`。
- 为项目状态、角色、规则策略、证据分类、网络模式和数据库再分发状态增加展示映射；API/TSV/JSON/SIF 的机器字段与枚举保持不变。
- 错误消息统一补充可执行的恢复建议；浏览器语言改为英文，页面标题按负责人定稿更新为 `Quorum Sensing Communication Network Analysis`。

### 兼容性

- 内部版本为 `0.3.1`，展示名为 `QSCN v0.3.1`。schema 仍为 `3`，hit/capability/scope 规则版本保持 `1.0`/`2.0`/`1.0`；现有 v0.3 数据无需迁移，已有 HMM 结果无需重扫。
- v0.3 的冻结口径修订为：允许不改变分析语义、数据库和 schema 的兼容补丁；新分析能力仍留待后续大版本。
- 本次文案修订不改变 schema、数据库、HMM 命中、capability 判定、scope 或既有导出内容，无需迁移、重解释或重扫。

## QSCN v0.3 RC1 — 2026-08-06

### 发布边界与兼容性

- 内部版本统一为 `0.3.0-rc.1`，展示名为 `QSCN v0.3 RC1`；冻结 hit rule `1.0`、capability rule `2.0` 与 analysis scope `1.0`。v0.3 后冻结功能，只接受发布阻断修复，下一大版本为 v1.0。
- 数据 schema 升级为 `3`，应用和 Redis 均使用新的 Compose volume。v0.2 SQLite/Redis 数据不自动迁移或删除；手工挂载旧 SQLite 时启动会明确拒绝，并提示先用 v0.2.2 导出。
- 项目代码采用 Apache-2.0；QSP/KEGG 数据的来源、构建与再分发状态独立记录。尚未确认的许可字段标记为 `unconfirmed`，不宣称已获 KEGG 授权。

### 安全、证据链与可靠性

- ZIP 解包采用流式实际字节计量，并限制上传、解压字节、文件数、深度、样本数、总序列、总残基和 `100:1` 压缩比；拒绝加密、特殊文件、路径穿越、重复路径、大小写冲突与规范化样本重名。
- FASTA 样本内 ID 必须唯一；跨样本同名 ID 合法。蛋白输入若完全属于核酸字母表会返回 `ambiguous_sequence_alphabet`。
- 外部命令使用参数数组、独立进程组、资源限制、超时和取消清理；运行前检查磁盘余量，运行后限制产物大小。
- genome 分析解析 Prodigal FAA/CDS/GFF，新增可逆的 `predicted_genes.json/tsv`，并把 contig、坐标、链和 partial 标记带入命中与完整导出。
- 新增轻量 liveness 与 SQLite/Redis/Worker/数据库索引 readiness；重启只将真正失联的运行标记为 `analysis_interrupted`。
- 镜像在构建时复制原始 HMM 到只读 runtime 目录并重新 `hmmpress`；Compose 仅绑定 localhost，使用非 root、只读根文件系统、临时 `/tmp`、最小 capability 与资源边界。

### 发布材料与验证

- 新增数据库 provenance、Apache-2.0 `LICENSE`、第三方软件/数据说明、研究用途免责声明、升级/备份说明、发布检查表和锁定依赖。
- 新增合成 genome/真实 Prodigal、微型 HMM/真实 HMMER、完整 Worker/API/导出以及 Playwright Web E2E 测试。
- 7 菌株、21,918 蛋白全量基准已分别完成 QSP 38 profiles 与 KEGG 281 profiles，结果记录于 `benchmarks/v0.3-rc1.json`；本版本未改变既有命中阈值或网络规则。

## demo v0.2.2 — 2026-08-05

### 网络视图与导出

- 网络增加默认的极简模式、按 signal 合并模式和逐 Pathway 模式。极简模式将同一样本对的全部 Pathway 证据聚合为至多一条连接，并在悬浮标签中分别汇总两个单向方向、双向 Pathway、自身通信及其 signal 数量。
- 修复同信号箭头合并后 inspector 丢失逐通路对应关系的问题。所有聚合模式均保留底层 Pathway evidence edges，显示箭头不改变后端网络、统计或机器可读导出。
- 同一样本对在同一 Pathway 上同时存在两个相反方向时折叠为一条双向箭头；两个底层有向 evidence edges 继续独立计数和导出。
- 节点 inspector 增加入度、出度、总度、唯一邻居和自身边；关闭 self-communication 后与统计卡片、节点大小及指标表同步重算。
- 增加当前网络视口 PDF 下载，保留拖动位置、缩放、平移、显示模式和 self-edge 状态。PDF 由浏览器原生 Canvas 与锁定版本的 `pdf-lib 1.17.1` 生成，不依赖远程服务，也不进入结果 ZIP。

### 解释范围

- 新增 analysis scope rule `1.0`，支持全部 Pathway、指定 Pathway 或按数据库原生 signal 选择 Pathway；共享 signal 会展开到该数据库内的全部对应 Pathway。
- HMMER 始终扫描完整数据库并保留全部 hits。scope 只限制 capability、network 及 interpretation 工件，完成后修改 scope 可复用 hits 创建新 interpretation，无需重新运行 HMMER。
- run、interpretation、results JSON 与 run manifest 保存用户选择和解析后的 Pathway ID；SQLite 采用增量加列，缺少 scope 的 v0.2/v0.2.1 记录按全部 Pathway 读取。
- Hit evidence 默认显示 scope 相关 profile 的候选，并可切换查看完整扫描 hits；完整导出始终保留全部原始命中。

### 版本与验证

- 内部版本升级为 `0.2.2`，发布标签为 `demo v0.2.2`；hit rule 仍为 `1.0`，capability rule 仍为 `2.0`。
- 前后端增加极简方向聚合、节点指标、PDF 编码、scope 校验、共享 signal、旧 SQLite 迁移和 scoped reinterpretation 测试。
- 将 Vite 升级到 `6.4.3`、React 插件升级到 `4.7.0`；`npm audit` 从既有的 moderate/high 问题降为零漏洞。


## demo v0.2.1 — 2026-08-04

### HMM 命中规则

- 新增 hit rule `1.0`。QSP 继续使用逐 profile 的 sequence/domain GA bit-score cutoff；KEGG 与 E-value 型自定义库默认同时要求 full-sequence E-value 和 domain i-Evalue 不高于 `1e-5`。
- c-Evalue、full/domain bit score、实际阈值、pass/failure reason 和规则版本进入 JSON、TSV、API 与 run manifest。capability 只消费通过的候选 domain。
- 旧自定义 manifest 的 `default_evalue` 兼容映射到两个新阈值；旧 `sequence_evalue_override` API 参数暂时兼容。阈值变化必须重跑 HMMER，不能通过新 interpretation 改变。
- SQLite 采用增量加列迁移；旧 v0.2 结果继续读取和导出并标记为 legacy hit rule，不自动删除数据卷。
- 修复从保留的 v0.1 SQLite 数据卷创建新 run 时，遗留的非空 `completeness_mode` 列导致写入失败；该兼容修复本身不改变分析结果。

### 网络与界面

- 网络节点缩小为约 26–44 px；新增默认关闭的同信号箭头合并视图，按有向样本对和 signal 聚合，保留原 pathway edges 与全部导出。
- 网络同时报告 Evidence edges 与 Displayed arrows；普通和合并边均提供 pathway 悬停标签及完整 inspector 证据。
- 所有 Web 用户文案集中到带类型的英文词典；已知 API/Worker 错误改为稳定错误码，技术诊断不再直接显示在网页。

### 版本与验证

- 内部版本升级为 `0.2.1`，发布标签为 `demo v0.2.1`。
- 后端新增 GA/E+i、失败候选过滤、旧 manifest/API/SQLite 兼容测试；前端新增网络聚合与文案错误映射测试。

## demo v0.2 — 2026-08-04

### 分析规则

- 将核酸输入统一为 `Genomes (nucleotide sequences)`，所有新核酸任务显式使用 Prodigal `single`；该变化会改变原 MAG `meta` 任务的基因预测结果，必须重新运行完整分析。
- 删除旧的较宽松和非常宽松完整度模式，改为版本化的逐 Pathway、逐发送/接收角色规则：严格全部命中、最低命中数或指定必需 profile。
- 单组件角色强制严格；新增“允许缺失一个”批量设置。修改规则可复用已保存的 HMM hits 创建新 interpretation，无需重跑 HMMER。
- Capability 结果继续保留 supporting hit IDs 以追溯原始证据，网络模型和网络导出不再暴露该内部字段。

### 网络、导出与界面

- 网络改为仅含微生物节点的有向多重图；同一 Pathway 的发送者到接收者形成潜在通信边，保留孤立节点、自身通信和不同 Pathway 的平行边。
- 通信边增加 signal、数据库来源、参考文献以及发送/接收组件摘要；增加按 signal 着色的动态图例、动画布局和交互检查器。
- 增加网络汇总、节点入度/出度/总度、唯一邻居和自身边统计，并提供 capability TSV、Cytoscape SIF、节点/边和统计 TSV 的独立下载。
- 自定义数据库入口增加通用 HMM 合并、ZIP 结构和 manifest 模板说明；仍由 QSCN 运行 `hmmpress` 并拒绝上传 `.h3*`。
- 全部内置 UI 文案改为英语，视觉主题改为浅米黄色与鼠尾草绿色。

### API、兼容性与版本

- `InputKind` 改为 `protein | genome`；Run/interpretation API 接受 `capability_rules[]`，数据库 API 公开每个角色的 profile 列表。
- Results 网络结构改为 `nodes / edges / summary / node_metrics / legend`，并新增白名单式 interpretation artifact 下载 API。
- 内部版本统一升级为 `0.2.0`，发布标签为 `demo v0.2`。
- v0.1 run/interpretation 结果不保证兼容；应用不会自动删除旧 Docker 数据卷，升级者须在备份后显式重建。

### 验证

- 后端测试扩展到规则策略、单组件约束、大于十组件角色、统一 Prodigal 模式、微生物网络、统计、SIF/TSV 工件和 interpretation 复用 hits。
- 前端 TypeScript/Vite 生产构建通过；Docker 镜像、Compose 服务和健康检查均完成验证。

## demo v0.1 — 2026-08-03

### 新增

- 提供 Docker Compose 驱动的单用户本地 Web 应用，由 React/TypeScript 前端、FastAPI API、Redis/RQ Worker 和 SQLite WAL 组成。
- 支持 ZIP 项目上传与安全预检；一个 FASTA 文件对应一个基因组，支持蛋白组、参考基因组和 MAG 三类输入。
- 蛋白输入直接进入 HMM 扫描；参考基因组使用 Prodigal `single`，MAG 使用 Prodigal `meta`。
- 内置 QSP 与 KEGG 数据库适配器，并支持带 manifest 的 GA/E-value 型自定义 HMM 数据库导入及 `hmmpress` 索引生成。
- 实现 HMMER 命中解析、原始输出保存、命中证据表、工具版本和输入/数据库校验和记录。
- 实现严格、较宽松和非常宽松三种 Pathway 完整度模式；发送与接收能力独立计算，重复基因拷贝不增加完整度。
- 支持从既有 HMM 命中创建新 interpretation，无需重新扫描即可切换完整度模式。
- 构建 `Genome -> Signal/Pathway -> Genome` 潜在通信网络，保留 Pathway 边界并支持自身通信显示/隐藏。
- 提供项目、任务、数据库、结果、导出、取消和失败重试相关 API，以及预检、能力表、命中表和 Cytoscape.js 网络界面。
- 结果包包含运行清单、命中、能力、通信、网络节点/边、原始 HMMER 输出，以及核酸任务的 Prodigal 产物。

### 数据与规则

- QSP 数据库包含 38 个 profile，全部具有 GA 阈值；QSP 任务固定使用 `--cut_ga`。
- KEGG 数据库包含 281 个 profile，不含 GA 阈值；默认采用 full-sequence E-value `1e-5`，任务级可调整。
- `K07680` 已在源 JSON 中直接修复，并通过数据库一致性测试验证，不再依赖加载时静默改写。
- QSP 与 KEGG 保留各自的数据来源和原生分类，不跨库拼接 Pathway 或网络。

### 验证

- 14 项核心单元测试通过，覆盖版本一致性、数据库 profile/GA 一致性、K07680 映射、完整度边界、单组件最低证据、角色独立性、ZIP/FASTA 安全、Prodigal 模式、domtblout 解析和 Pathway 范围网络。
- Docker Desktop 环境中已完成镜像构建、API/Worker/Redis 启动、API 健康检查，以及 Worker 内 Prodigal 2.6.3 和 HMMER 3.4 可执行性验证。

### 已知限制

- 当前是演示版本，尚未完成全部计划中的端到端、安全、性能和生物学基准验收。
- 前端依赖审计报告 1 个 moderate 和 1 个 high 等级问题，发布用户版前必须升级并回归测试。
- 数据库来源、版本构建过程、许可与可再分发范围仍需项目负责人确认。
- KEGG 阈值尚未使用独立基准集完成生物学校准；覆盖度目前仅报告，不作为硬过滤条件。
- 当前演示数据只覆盖蛋白输入，缺少核酸参考基因组、破碎 MAG、partial gene 和资源超限的端到端 fixture。
