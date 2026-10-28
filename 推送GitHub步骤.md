# 纯网页操作：不用命令行，上传 + 部署 + 分享

全程在 GitHub 网页上点鼠标，**不需要 git、不需要敲命令**。

---

## 准备：下载「上传包」

用 **GitHub上传包.zip**（约 490 KB，38 个文件），这是**全量包**，解压后全选拖拽即可。

区别：

| 包 | 大小 | 用途 |
|---|---|---|
| **`GitHub上传包.zip`** | **约 490 KB** | ✅ **全量上传包**，38 个文件（已排除敏感 txt 与两个大 zip） |
| `lottery-app.zip` | 9.7 MB | 完整工程（含 Serverless 依赖、部署 zip），本地开发用 |

完整包里有 `third_party/`（9.7 MB）和两个部署 zip（6.4 MB），
**这些不需要上传**——CI 里用 `pip install` 装，zip 可随时重新生成。
所以单独给你打了个精简包。

---

## 第 1 步：建仓库

1. 打开 https://github.com/new
2. Repository name: **`lottery-app`**
3. **选 Public** ⚠️

   > 必须 Public，否则 GitHub Pages 免费版不可用（私有仓库要付费 Pro）。
   > 关于"Public 仓库 60 天无活动会禁用定时任务"的问题——
   > 我已在工作流里加了**心跳提交**自动解决，见文末说明。

4. 勾选 **Add a README file**（让仓库非空，后面操作更顺）
5. 点 **Create repository**

> 如果又遇到 `Something went wrong!`：那是页面停留太久表单令牌过期，
> **刷新页面重新填，填完立刻点创建**。

---

## 第 2 步：上传文件（拖拽，不用敲命令）

1. 解压 `GitHub上传包.zip`，得到一个 `GitHub上传包` 文件夹
2. 打开文件夹，**全选里面所有内容**（`Ctrl+A`）
3. 回到 GitHub 仓库页面 → **Add file** → **Upload files**
4. 把选中的东西**拖到虚线框里**

   > 也可以点 `choose your files`，但**选文件夹不如拖拽可靠**，
   > 因为要保留 `.github/workflows/` 和 `dist/` 的目录结构。

5. 等文件列表出来，**往下翻确认能看到这两个**：

   ```
   .github/workflows/refresh-data.yml
   .github/workflows/deploy-pages.yml
   ```

   > Windows 上 `.github` 是普通文件夹，拖拽没问题。
   > **如果列表里没有它**，见文末「备选方案」。

6. 底部 Commit changes：
   - 第一框填 `feat: 彩票统计工具`
   - 保持 **Commit directly to the main branch**
   - 点绿色 **Commit changes**

上传内容：30 个文件，636 KB，几秒完成。

> GitHub 网页上传上限：单次 100 个文件、单文件 100 MB。我们 38 个 / 最大约 900 KB，远低于限制。
> 包内已排除 `管理员账号.txt`、`授权码名单.txt`（含明文口令）和 `dist/*.zip`（3.3 MB 构建产物）。

---

## 第 3 步：开启 GitHub Pages

1. 仓库页面顶部 → **Settings**
2. 左侧菜单 → **Pages**
3. **Source** 下拉 → 选 **GitHub Actions**

**选完就生效，没有要点的 Save 按钮。**

> ⚠️ 页面上确实有个 Save 按钮，但它是 **Custom domain（自定义域名）**
> 输入框的配套按钮——我们没填域名，所以它是灰的、点不了，**不用管**。
> Source 下拉选完自动保存，看它显示 `GitHub Actions` 就是成功了。

### 两件事千万别做

**① 不要点页面中间的 `Configure` 按钮**

```
GitHub Pages Jekyll    [Configure]   ← 别点
Static HTML            [Configure]   ← 别点
```

这是 GitHub 的官方模板，点了会新建 workflow 文件，跟我们自带的
`deploy-pages.yml` 抢同一个站点，互相覆盖报冲突。
**我们自己的部署工作流已经写好了。**

**② 不要用 "Deploy from a branch"**

Source 必须选 **GitHub Actions**。选 branch 那套是老式发布，
不认我们的 workflow，部署会静默不生效。

### 顺带确认仓库是 Public

页面底部如果出现 **「Start free for 30 days」**，说明仓库可能是 Private
（Pages 免费版只对 Public 开放）。检查仓库名旁边有没有 **Public** 徽章：

- 有 → 继续下一步
- 显示 Private → Settings → General → 最底部 Danger Zone
  → Change visibility → 改 Public

---

## 第 4 步：手动跑一次验证

### ① 跑数据刷新

**进 Actions 页面（唯一确定入口，直接在地址栏输入）**：

```
https://github.com/YuYuan7/lottery-app/actions
```

> 注意是 `/actions` 结尾。进去后看到的是**工作流列表**（All workflows），
> 左侧列着「定时刷新彩票数据」「部署到 GitHub Pages」。
>
> ⚠️ 左侧如果只看到 General / Runners / Policies / OIDC，
> 那是 **Actions 的设置页**，走错了——用上面这个网址重进。

1. 左侧点 **「定时刷新彩票数据」**
2. 右上 **Run workflow** → 下拉保持 `12` → 绿色 **Run workflow**
3. 等 1~2 分钟，点进去看日志

预期看到：

```
[cron] ssq: 非开奖窗口，跳过轮询（今天是周二，开奖21:15）
[cron] ssq: 2081 期，最新 2026123
[cron] 3d: 4791 期，最新 2026286
[cron] pls: 7761 期，最新 26286
[cron] dlt: 2940 期，最新 26122 (2026-10-26)
[cron] 数据变化: 否
CHANGED=no
```

**`数据变化: 否` 就是跑通了**——现在还没到开奖时间，没有新期号属正常。

因为没变化，会自动做一次**心跳提交**，仓库里出现 `chore: heartbeat ...`。

### ② 手动发布一次

1. Actions → 左侧 **「部署到 GitHub Pages」**
2. **Run workflow** → Run workflow
3. 等约 1 分钟

### ③ 拿到网址

部署完成后：

- 该 job 页面上会出现一个 **Visit** 按钮，点它
- 或去 **Settings → Pages** 看网址

网址长这样：

```
https://<你的用户名>.github.io/lottery-app/
```

打开确认：能看到**四个彩种**标签页（双色球/大乐透/福彩3D/排列三），点「开奖记录」有对应期数数据。

---

## 第 5 步：分享给别人

直接把这个网址发出去：

```
https://<你的用户名>.github.io/lottery-app/
```

对方手机浏览器打开就能看。想更方便：**添加到主屏幕**，之后像 App 一样点开。

### ⚠️ 但你得先自己试一件事

**`github.io` 在国内访问不保证稳定**——时快时慢，有时打不开，取决于运营商和时段。

**现在就用手机流量（别连 WiFi）打开一次**：

| 结果 | 下一步 |
|---|---|
| 能打开 | ✅ 就用它，零成本 |
| 打不开 / 很慢 | 换**腾讯云 CloudBase**，见下 |

### 备选：腾讯云 CloudBase（国内节点，更快）

1. https://tcb.cloud.tencent.com/ → 实名认证（身份证 + 手机号，**不要信用卡**）
2. 新建环境 → 免费体验版
3. 左侧 **静态网站托管 → 文件管理 → 上传文件**
4. 上传 **`dist/单文件版/彩票统计.html`**
5. 得到 `https://xxx.tcloudbaseapp.com`

> ⚠️ **必须传单文件版**。腾讯默认域名会给其他请求加下载响应头，
> 如果传 `index.html + data/*.json` 那套，JSON 会被当成下载，
> 页面必然报"数据获取失败"。**单文件版是唯一起得来的。**

访客首次打开会看到一个"仅供开发测试"提示页，**点一下就进**。
CloudBase 免费环境**每 6 个月手动续期一次**（0 元，不会自动扣费）。

---

## 之后全自动，你什么都不用做

```
开奖日 21:37
   ↓
GitHub 自动跑「定时刷新」
   → 轮询等官方出数据（最多等 12 分钟）
   → 生成新的 彩票统计.html
   → 自动 commit
   ↓
自动触发「部署到 GitHub Pages」
   → 发布
   ↓
别人打开网址就是最新数据
```

排期（cron 用 UTC，北京 = UTC+8）：

| 北京时间 | 星期 | 说明 |
|---|---|---|
| 21:37 | 周二、周四、周日 | 双色球，开奖后 22 分 |
| 22:43 | 周二、周四、周日 | 冗余补跑 |
| 20:47 | 周一、周三、周六 | 大乐透，开奖后 17 分 |
| 21:53 | 周一、周三、周六 | 冗余补跑 |
| 09:13 | 每天 | 兜底 + 心跳 |

今晚 21:25 之后可以再去 Run workflow 一次，能看到：

```
[cron] ssq: 官方已出新期 2026123（本地 2026122）
[cron] 数据变化: 是
CHANGED=yes
```

---

## 备选方案：`.github` 没传上去怎么办

如果第 2 步的文件列表里**看不到** `.github/workflows/` 两个文件，手动创建：

1. 仓库首页 → **Add file** → **Create new file**
2. 文件名框**直接输入完整路径**（GitHub 会自动建目录）：

   ```
   .github/workflows/refresh-data.yml
   ```

3. 打开 `GitHub上传包/.github/workflows/refresh-data.yml`（用记事本/VSCode），
   全选复制，粘贴到网页编辑区
4. 底部 **Commit changes**
5. 同样方法创建 `.github/workflows/deploy-pages.yml`

---

## 关于 Public 仓库的 60 天限制

GitHub 规则：**公开仓库 60 天无任何 activity，定时任务自动禁用**（静默失效，不通知）。

我已在 `refresh-data.yml` 里加了心跳逻辑：

- 数据有变化 → 正常提交数据
- 数据没变化 → 提交 `dist/.last-check` 记录时间

**每天至少一个 commit**，仓库永不沉寂。该文件放在 `dist/` 下被 `paths-ignore` 排除，不会造成工作流循环触发（已验证）。

---

## 排错表

| 现象 | 原因 / 解法 |
|---|---|
| Actions 里看不到工作流 | `.github/workflows/*.yml` 没传成功，用上面的备选方案手动建 |
| Pages 部署失败 | Settings → Pages → Source 没选 **GitHub Actions** |
| 部署报权限错 | 仓库 Settings → Actions → General → Workflow permissions 选 **Read and write** |
| 定时任务从不触发 | 工作流必须在 main 分支 |
| 跑成功但数据没变 | 非开奖日或还没开奖，正常 |
| 页面白屏 / 数据获取失败 | 确认发布的是**单文件版**，不是 index.html + json |
| 上传时报错 | 是不是把 `lottery-app.zip` 整个拖进去了？要用 `GitHub上传包.zip` |
