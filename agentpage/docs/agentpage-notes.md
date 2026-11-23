# Agentpage 模块开发与后端联调笔记

## 1. 从项目入口读起

这个项目是中国矿业大学（北京）智能教学系统的 Vue 3 前端。建议按 `src/main.js` → `src/App.vue` → `src/router/index.js` → 对应 `src/views/*/index.vue` 的顺序读代码。

目录和组件写法参考《Vue3 小兔鲜》配套笔记中的 `3. 项目起步.md`、`4. Layout页.md`、`5. Home页.md`、`9. 登录页.md`，以及课程 `03-code/vue-rabbit/src` 的同类模块。这里沿用课程 `src/` 下的分层。页面入口使用 `views/模块名/index.vue`，专属组件放在页面的 `components/`，可复用的请求、状态、组合式函数和指令各有自己的目录。`@/` 指向 `src/`。页面使用 Vue 单文件组件、`<script setup>`、普通 JavaScript 和 CSS。

```text
src/
├─ main.js                             注册 Pinia、Router、指令并引入全局样式
├─ App.vue                             将当前路由页面放进公共布局
├─ apis/
│  ├─ user.js                          演示账号匹配与登录会话接口
│  ├─ analysis.js                      教师分析、学生学情、建议和错题接口
│  ├─ agent.js                         Agent 对话、配置和历史接口
│  └─ uploads.js                       导入批次、进度、试跑和发布接口
├─ composables/useChat.js               对话草稿、消息列表和发送逻辑
├─ directives/index.js                 注册打开文件选择器的 v-open-file
├─ router/index.js                     路径、路由名和演示角色守卫
├─ stores/userStore.js                 用 Pinia 管理当前角色与登录动作
├─ styles/common.css                   全局字号、按钮、表单和页面基础样式
├─ utils/
│  ├─ demoSession.js                   读写当前浏览器标签页的角色
│  └─ http.js                          共用的 HTTP 请求封装
├─ components/
│  ├─ AgentChat.vue                    三个入口共用的对话面板
│  └─ TeacherBackLink.vue              教师子页共用的返回链接
└─ views/
   ├─ Layout/
   │  ├─ index.vue                     公共页面外壳与页脚
   │  └─ components/LayoutHeader.vue   学校名称、导航与高亮
   ├─ Login/index.vue                  登录页
   ├─ Teacher/
   │  ├─ index.vue                     教师首页、分析占位与对话
   │  └─ components/TeacherActions.vue 导入与两个教师子页入口
   ├─ AgentConfig/
   │  ├─ index.vue                     学号选择与学生对话面板
   │  └─ components/AgentSettings.vue 语气、AI Key、自动打印表单
   ├─ DataAnalysis/index.vue           教师数据详情页
   └─ Student/
      ├─ index.vue                     组合学生端各个区域
      ├─ components/StudentResults.vue 成绩与错题分析占位
      └─ components/LearningReport.vue 章节掌握与个性化建议
```

`main.js` 负责挂载，`App.vue` 把 `<RouterView />` 传给 `Layout/index.vue` 的默认 `<slot />`。切换路由时中间页面更换，页头和页脚沿用同一个布局。`LayoutHeader.vue` 用 `<RouterLink>` 跳转，并用 `$route.path.startsWith('/teacher')` 保持教师子页的导航高亮。每个路由页使用 `index.vue` 作为模块入口，通过 `defineOptions({ name: '…' })` 声明清晰的组件名，方便在 Vue DevTools 中识别，也符合项目的组件命名检查。

## 2. 路由、页面入口与登录

| 路径 | 路由名 | 页面入口 | 演示角色限制 |
| --- | --- | --- | --- |
| `/` | `login` | `views/Login/index.vue` | 无 |
| `/teacher` | `teacher` | `views/Teacher/index.vue` | `teacher` |
| `/teacher/agent-config` | `agent-config` | `views/AgentConfig/index.vue` | `teacher` |
| `/teacher/data-analysis` | `data-analysis` | `views/DataAnalysis/index.vue` | `teacher` |
| `/student` | `student` | `views/Student/index.vue` | `student` |

登录表单把账号和密码分别用 `v-model` 写进 `account`、`password`。`@submit.prevent="login"` 用同一个函数处理点击登录和回车提交。页面的 `login()` 将原样输入交给 `useUserStore().loginWithDemo()`，由它调用 `apis/user.js` 的 `loginDemoAPI()` 做匹配。演示账号为教师 `123 / 123`、学生 `456 / 456`，输入多余的空格会影响匹配。

匹配失败时，`error` 触发 `v-if` 渲染原有错误提示。成功时，`userStore` 通过 `setDemoRole()` 写入当前标签页的 `sessionStorage['demo-role']`，并更新自己的 `role`。页面清空错误并跳到对应路由。「记住密码」是原有的表单复选框，本地登录只保存角色。

`router/index.js` 通过 `createWebHistory(import.meta.env.BASE_URL)` 建立历史路由，并用 `meta.role` 声明角色。刷新或直接访问受限页面时，`restoreRole()` 读取会话中的角色。角色与目标不符时返回登录页。`main.js` 先安装 Pinia，再安装路由，确保守卫执行时可访问 `userStore`。

```js
router.beforeEach((to) => {
  if (!to.meta.role) return
  const userStore = useUserStore()
  if (userStore.restoreRole() !== to.meta.role) return { name: 'login' }
})
```

## 3. 教师端与数据详情

- `views/Teacher/index.vue` 负责原有的左右布局。左侧组合操作区和「数据分析」容器，右侧放入 `<AgentChat>`，通过 props 指定教师端标题、输入框 ID 和空态文案。
- `TeacherActions.vue` 用 `v-open-file="'teacher-data-file'"` 把「导入数据」按钮和同 ID 的隐藏文件输入框关联起来。`main.js` 安装 `filePickerPlugin`。`directives/index.js` 在按钮的 `mounted` 阶段设置点击处理函数，按 ID 找到输入框并调用 `click()`。按钮卸载前清理处理函数。当前流程结束于浏览器原生单文件选择器。
- 两个 `<RouterLink>` 分别跳到 `/teacher/agent-config` 和 `/teacher/data-analysis`。后者由 `DataAnalysis/index.vue` 渲染「暂无数据详情」，供接入班级数据后替换占位区。
- `TeacherBackLink.vue` 封装教师子页共用的「← 返回教师端」。从子页返回会重新挂载教师首页，其对话从空态开始。

## 4. 学生端

- `views/Student/index.vue` 按页面顺序组合标题、`StudentResults`、`LearningReport` 和 `AgentChat`。查看某个功能时，可直接从这里定位子组件。
- `StudentResults.vue` 包含「成绩展示与错题分析」和独立的空白展示区。后续成绩、错题列表可以渲染在此处。
- `LearningReport.vue` 包含「各章节掌握情况」和「个性化建议」。`showAdvice` 初始为 `false`。按钮点击把它改为 `true`，`v-if` 随即渲染原有的缺数据提示。浏览器通过 `role="status"` 宣读提示。离开路由后组件销毁，重新进入时复位。
- 「Agent 老师答疑」复用 `AgentChat.vue`，页面为它传入学生端标题、说明、输入标签和占位文字。学生只看到本次页面中自己提交的消息。

## 5. Agent 配置与按学号查看对话

`AgentSettings.vue` 管理三个单独的 `ref`，通过 `v-model` 绑定表单。语气初始为空，可选 `gentle`、`serious`、`concise`。AI Key 是初始为空的密码输入框。自动打印初始为空，可选 `yes` 或 `no`。`<form @submit.prevent>` 拦截浏览器默认提交。三个值保留在表单实例内，离开路由或刷新后重置。

`AgentConfig/index.vue` 使用两个状态。`studentInput` 是文本框里正在编辑的学号，`selectedStudent` 是按「确定」后采用的学号。`selectStudent()` 用 `trim()` 去掉首尾空白并忽略空值，学号始终是字符串，`001` 的前导零会保留。它把确认后的学号传给对话面板。

```vue
<AgentChat
  class="config-chat"
  title="学生与 Agent 对话"
  title-id="chat-title"
  input-id="chat-input"
  :empty-text="selectedStudent ? '暂无对话内容' : '确认学号后开始对话'"
  :disabled="!selectedStudent"
  :conversation-key="selectedStudent"
/>
```

未确认学号时，输入框和发送按钮禁用。`useChat()` 用 `watch` 监听 `conversationKey`，仅当确认后的学号变化时清空对话面板显示的本地消息列表。再次确认同一学号时列表保持原样，换学号时已输入且未发送的草稿仍在。这是原来的配置页行为。

## 6. 公共对话组件与样式

`src/components/AgentChat.vue` 同时用于教师首页、学生首页和 Agent 配置页。各入口各有一份 `messageInput` 与 `messages`，都随组件挂载和卸载。`title`、`titleId`、`subtitle`、`emptyText`、`inputId`、`inputLabel`、`placeholder` 用于呈现各入口的文案和原有标签。配置页额外使用 `disabled` 和 `conversationKey`。

对话状态和提交函数放在 `src/composables/useChat.js`。每次调用 `useChat(props)` 时创建新的响应式变量，所以不同页面的聊天实例各自保存消息。输入框的 `v-model` 更新 `messageInput`，`computed` 根据草稿和 `disabled` 计算 `canSend`。发送按钮与提交函数使用同一个条件。发送时把去除首尾空白的文本追加到列表，`v-for` 渲染气泡，再清空输入框。消息区保留 `role="log"` 和 `aria-live="polite"`。

```js
const canSend = computed(() => !props.disabled && messageInput.value.trim() !== '')

function sendMessage() {
  if (!canSend.value) return
  messages.value.push(messageInput.value.trim())
  messageInput.value = ''
}
```

`styles/common.css` 由 `main.js` 引入，负责跨页面复用的基础样式。页面和组件独有的布局写在各自的 `<style scoped>`，对话组件内的 `teacher-chat`、`student-chat`、`config-chat` 样式类保留三个入口原有的高度和间距。`850px`、`700px`、`520px` 的布局规则随相关组件迁移。

## 7. 后端接口联调

### 当前前端的接口状态

本地 `agentpage` 的五条路由都在浏览器内运行。登录写入 `sessionStorage['demo-role']`，三个聊天区域在本地追加消息，导入按钮只打开文件选择器，成绩、建议、数据分析和 Agent 配置尚未读写远端数据。页面沿用这些行为。`src/apis/` 已整理了可供后续联调调用的请求函数。

本地 Git 的 `origin/main`（`a303a9d`）留有两套后端参考代码。根目录的 `src/` 是 Python 数据流水线，`智慧学伴-后端代码.zip` 是 FastAPI 服务，`agent-main/agent/server.py` 是独立 Agent 演示服务。这个 Git 引用中的 `agentpage/` 与原本本地检出的 `agentpage/` 一致。下文的已有后端接口根据该引用的源码核对，当前网页尚未接入，服务也未做运行联调。

### FastAPI 接口与页面的对应关系

以下路径均以 `/api` 开头，成功时直接返回业务 JSON。表内列出的字段是页面适用的字段摘要。

| 页面或交互 | 已有接口 | 参数及页面读取的字段 |
| --- | --- | --- |
| 教师端学情概览和班级选择 | `GET /api/students`、`GET /api/classes?class_id=DC01` | 学生索引含 `students`、`student_count`、`quality`、`build_id`。班级接口返回按学生汇总的行数组，`class_id` 可省略。 |
| 教师端班级数据详情 | `GET /api/analysis/classes/{class_id}` | 班级编码如 `DC01`，也可用 `全年级`。响应字段含 `student_count`、`themes`、`weak_indicators`、`common_lost_points`、`evidence_distribution`、`data_version`。明细可取 `GET /api/classes/{class_id}/indicators` 和 `GET /api/classes/{class_id}/themes`。 |
| 教师查看指定学生的数据 | `GET /api/analysis/students/{student_id}` | `student_id` 是字符串，如 `D01`，可选 `exam=N02`。读取 `student`、`overall`、`indicators`、`themes`、`exam_comparison`、`caveats`。 |
| 学生端成绩与章节掌握 | `GET /api/me/analysis?student_id=D01` | 可选 `exam`。成绩读取 `student`、`exam_comparison`，章节读取 `themes`、`indicators`，说明读取 `caveats`。该路由提供学生版数据结构。 |
| 学生端错题详情 | `GET /api/students/{student_id}`、`GET /api/questions/{question_id}` | 单人包的 `question_records` 提供 `exam_id`、`question_id`、`score`、`full_score`、`rubric_scores`。点开一道题时按 `question_id` 取题目详情。学生端可复用这些字段，由 `/api/me/wrong-questions` 返回本人可见记录。 |
| 学生点「生成个性化建议」 | `GET /api/me/plans?student_id=D01` | 读取 `focus`、`steps`、`acceptance`、`fallback`。当前服务生成确定性建议，`placeholder` 为 `true`。缺少证据时可得到 `focus: null` 和 `steps: []`。 |
| 教师、学生和配置页的聊天输入框 | `POST /api/agent/chat` | JSON 必填 `role`（`teacher` 或 `student`）与非空 `message`，可选 `student_id` 字符串。响应为 `{reply, references, placeholder}`，当前是固定占位回复。 |
| 教师端导入数据 | `POST /api/uploads` 及其批次接口 | 发送 multipart 表单，文件字段为可重复的 `files`，`mode` 为 `full` 或 `append`（默认 `append`）。批次接口见下文。 |

`/api/me/*` 在参考实现中依赖请求传入 `student_id`，`/api/agent/chat` 使用请求体传入的 `role`。对接真实学生数据时，应由服务端会话确定用户、角色和学号，并按班级归属校验教师查看指定学生的权限。

聊天接口的请求和现有占位响应示例。

```json
{"role":"student","student_id":"D01","message":"我应该先复习哪一章？"}
```

```json
{"reply":"Agent 尚未接入，此处为占位回复。","references":[],"placeholder":true}
```

普通业务错误格式如下。

```json
{"error":{"code":"DATA_NOT_READY","message":"还没有导入数据，请先在教师端上传成绩数据","detail":null}}
```

| HTTP 状态 | 前端处理方式 |
| --- | --- |
| `400 BAD_REQUEST` | 按提示检查缺失或不合法的字段。 |
| `404` | 提示对象或批次不存在，例如 `STUDENT_NOT_FOUND`。 |
| `409 DATA_NOT_READY` | 展示尚未导入数据的空态。 |
| `409 BUILD_IN_PROGRESS` | 提示已有上传任务在处理，已有批次 ID 时可继续轮询。 |
| `422`（上传体检硬拦） | 试跑或发布可能返回体检清单原文，优先读取清单，不套用普通错误结构。 |
| `500` | 显示通用失败消息，保留当前页面输入，便于用户重试。 |

服务存在数据快照时，响应头含 `X-Data-Version`。展示学情数据时保留原字段口径，`null` 用「—」表示，`0` 表示有记录且得分为零。得分率使用原始 0 到 1 小数，仅在显示时转为百分比。成绩和章节结论使用后端发布的数据。

### 导入数据的批次流程

1. `POST /api/uploads` 返回 HTTP `202` 与 `{"batch_id":"示例批次","job_id":"示例任务","status":"received"}`。同一批文件逐个附加到 multipart 的 `files` 字段。
2. 轮询 `GET /api/uploads/{batch_id}/status`。响应含 `status`、`stages`、`confirm_required`、`build_id`、`message`。阶段项含 `name`、`exit_code`、`log_tail`。由 `received` 经 `ingesting`、`validating` 至 `validated` 或 `failed`。
3. 用 `GET /api/uploads/{batch_id}` 获取已生成的校验清单。对于 `confirm_required: true`，页面展示需要教师确认的条目。失败批次若已有清单，仍可读取清单中的问题。
4. 教师确认后调用 `POST /api/uploads/{batch_id}/trial`。成功返回 `status: "trialed"`、`changes` 和 `diff_markdown`。试跑完成以后，由教师确认调用 `POST /api/uploads/{batch_id}/publish`，使用返回的 `build_id` 重新加载分析数据。服务另有 `DELETE /api/uploads/{batch_id}` 用于丢弃批次，成功返回 `204`。

当前导入 UI 是单文件选择，未来对接批量资料时再加入多文件选取、校验反馈与发布确认。具体表格模板沿用后端数据流水线。

### 独立 Agent 演示服务的兼容方式

独立演示服务与上面的 FastAPI 是不同进程，源码中的默认端口为 `8787`。可由 FastAPI 保留 `/api/agent/chat` 的浏览器请求形状，在服务端将 `message` 映射到演示服务的 `question`，将 `text` 映射回 `reply`。对话会话和用户身份可在 FastAPI 层关联。

| 演示服务接口 | 已实现的入参和返回 |
| --- | --- |
| `POST /api/ask` | 必填 `question`，去除首尾空白后最多 500 字。可选 `session_id`、`tone`（`gentle`、`serious`、`concise`）。返回 `text`、`citations`、`refused`、`evidence`、`meta` 以及 `session.session_id`、`session.turn`、`session.context_used`。续问传上次得到的 `session_id`。 |
| `GET /api/history/{session_id}` | 返回 `{session_id, turns}`。每轮包含 `question`、`text`、`at`、`refused` 等字段。 |
| `GET /api/advise/{student_id}` | 可选 `limit`、`session_id`、`polish` 等查询参数。返回可用于学生建议的 `items`。 |
| `GET /api/health` | 返回 `ok`、`build_id`、`mode`、`llm_enabled` 等运行信息。 |

上述对话接口均用普通 JSON。演示服务使用 `session_id` 关联对话，AI 密钥由服务端环境变量读取。它未提供账号鉴权。生产对接时，由有鉴权的业务服务代理这些接口。

### 需要后端团队补齐的约定

下表是针对当前页面缺口拟定的接口草案。命名沿用 FastAPI 的 `/api` 前缀和 `snake_case` 字段。

| 功能 | 建议接口 | 请求和返回草案 |
| --- | --- | --- |
| 登录与加载会话 | `POST /api/auth/login`、`GET /api/auth/me` | 登录传 `account`、`password` 字符串和可选 `remember` 布尔值。成功设置会话 Cookie，返回 `{user:{id,role,student_id}}`，教师的 `student_id` 可为 `null`。登录失败或会话过期返回 `401`。`remember` 可用于调整会话有效期。 |
| 读取和保存 Agent 配置 | `GET /api/agent/config`、`PATCH /api/agent/config` | 教师权限。读取返回 `{"tone":"gentle","auto_print":false,"has_ai_key":true}`。保存接受 `tone`（`gentle`、`serious`、`concise`）和 `auto_print` 布尔值，省略字段时保留配置。目前表单的 `yes`、`no` 在调用层转为布尔值。若后端决定让有权限的教师管理员维护 AI Key，可将 `ai_key` 设为仅写字段，缺省时保留原值，响应只提供 `has_ai_key`。现有演示服务使用服务端密钥配置。 |
| 学生本人错题 | `GET /api/me/wrong-questions` | 服务端从会话识别本人。可选查询参数 `exam`。返回 `{items:[{exam_id,question_id,score,full_score,rubric_scores}]}`，无记录时 `items` 为 `[]`。 |
| 按学号读取学生对话 | `GET /api/students/{student_id}/agent/history` | 教师权限，后端按学号查找授权可见会话。返回 `{student_id, conversations:[{session_id, turns:[{question,text,at}]}]}`。没有记录时 `conversations` 为 `[]`，学号不存在返回 `404`，无权访问返回 `403`。 |

联调前需要确定配置页的发送按钮是用于教师试问，还是用于向学生会话追加内容。教师试问可复用 `POST /api/agent/chat` 并使用教师自己的会话。若消息要进入学生会话，则应另行约定写入权限、消息作者和双方的可见范围。自动打印同样需要明确由浏览器还是由其他服务执行，以及触发打印的时机。

来源为本地 Git 引用 `origin/main@a303a9d` 中的 `智慧学伴-后端代码.zip`（`backend/app/api/`、`backend/app/services/`、`backend/app/core/`）、`agent-main/agent/server.py`、`agent-main/agent/chat.py` 和 `team/frontend/README.md`。

## 8. 后续联调时从哪里接入

`src/apis/` 中的函数按业务组织。它们接收页面使用的参数名，把 `studentId` 等值映射为后端字段，再用 `src/utils/http.js` 的 `request({ url, method, params, data })` 发起请求。与课程写法一样，组件可以直接导入一个具名的 `xxxAPI` 函数。

```js
import { getMyAnalysisAPI } from '@/apis/analysis'

const result = await getMyAnalysisAPI({ studentId: 'D01', exam: 'N02' })
```

上例对应 `GET /api/me/analysis?student_id=D01&exam=N02`。`request()` 把查询参数编码到 URL，将对象编码为 JSON，上传 `FormData` 时由浏览器自动填写 multipart 请求头。成功返回接口的 JSON 数据，`204` 无响应体。失败时可从异常读取 `status`、`code` 和 `data`。上传遇到 `422` 时可从 `error.data` 直接读取体检清单。

接口默认请求同源的 `/api`。开发联调可以通过 `.env.local` 的 `VITE_API_BASE_URL=http://127.0.0.1:8000` 指向本地后端，地址末尾留出由接口函数提供的 `/api` 路径。如果前后端分开部署并用会话 Cookie，后端需针对前端来源配置带凭据的 CORS。

| 前端接入点 | 可用的 API 函数 | 返回后如何更新界面 |
| --- | --- | --- |
| `stores/userStore.js` 和路由守卫 | `loginAPI`、`getSessionAPI` | 服务实现后按后端会话角色跳转，刷新时查询会话恢复权限。 |
| `TeacherActions.vue` 的文件选择 | `createUploadAPI`、`getUploadStatusAPI`、`getUploadChecklistAPI` 等 | 从文件输入的 `change` 事件取得文件。展示校验进度，由教师确认试跑和发布。 |
| `Teacher/index.vue`、`DataAnalysis/index.vue` | `getClassesAPI`、`getClassAnalysisAPI` | 用已发布的班级数据渲染分析。 |
| `StudentResults.vue`、`LearningReport.vue` | `getMyAnalysisAPI`、`getMyWrongQuestionsAPI`、`getMyPlansAPI` | 展示成绩、错题、主题掌握情况和建议。缺数据时展示相应空态。 |
| `AgentSettings.vue`、`AgentConfig/index.vue` | `getAgentConfigAPI`、`updateAgentConfigAPI`、`getStudentChatHistoryAPI` | 服务实现后回填和保存配置，确认学号时加载教师有权查看的历史。 |
| `composables/useChat.js` 的 `sendMessage()` | `sendAgentMessageAPI` | 提交后根据响应展示 Agent 回复。失败时保留用户已输入的内容以便重试。 |

## 9. 本地验证记录

使用原始源码和重构后的生产构建进行浏览器对照，覆盖五条路由。验证了演示登录与错误提示、跨角色拦截、刷新后的角色恢复、单文件选择器、各入口本地消息、学生建议提示、同学号保留消息、切换学号清空消息并保留草稿，以及路由重新进入时的状态。桌面与 390px 宽视口下，抽查页面元素的位置、尺寸和样式结果一致。

在项目目录运行 `npm run dev` 可打开本地开发页。代码通过 Vite 生产构建及 ESLint、Oxlint 检查。通过模拟响应核对了请求封装，线上接口与待实现的接口草案均尚未连接运行中的服务。
