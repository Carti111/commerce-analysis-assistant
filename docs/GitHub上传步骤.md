# 上传到自己的GitHub

项目已整理为独立目录`commerce-analysis-assistant`。在这个目录内操作Git，不要在它的上一级`github`目录初始化仓库，以免把其他项目一起上传。

## 1. 在GitHub建立空仓库

登录自己的GitHub账号，点击右上角“+”→“New repository”。

- Repository name：`commerce-analysis-assistant`。
- Description：`基于 Dify、Python、MySQL 和 ECharts 的电商经营数据问答与可视化个人项目`。
- Public适合在简历中展示；也可以先设为Private。
- 不要勾选生成README、.gitignore或License，因为本地已准备好项目文件。

建立后复制HTTPS地址，形式为`https://github.com/你的用户名/commerce-analysis-assistant.git`。

## 2. 在项目目录配置提交身份

本地已初始化Git仓库和main分支，但没有创建提交或设置作者。下面两项请填写你自己的信息，配置只对当前项目生效：

```powershell
git config --local user.name "你的GitHub用户名或姓名"
git config --local user.email "你的GitHub邮箱"
```

希望不公开个人邮箱时，可以在GitHub Settings → Emails中查看你的GitHub noreply邮箱，并在上面填入该地址。提交身份和网页登录账号是两回事。

## 3. 提交并推送

```powershell
git status --short
git add .
git commit -m "Initial commit: commerce analysis assistant"
git remote add origin https://github.com/你的用户名/commerce-analysis-assistant.git
git push -u origin main
```

地址中的“你的用户名”需要替换。首次推送时若Windows弹出GitHub登录页面，按提示用自己的账号授权；不要把GitHub密码、Token或API密钥写进命令、README或聊天中。

如遇`remote origin already exists`，先用`git remote -v`核对已有地址；不要在未核对的情况下覆盖。

## 4. 发布后检查

- 刷新仓库首页，确认README、演示截图、工作流DSL和database目录都显示正常。
- 后续增加功能后，在项目目录执行`git add .`、`git commit -m "说明本次修改"`、`git push`。
- `.local-db-uri.txt`、`.env`、缓存和临时数据库目录已设置忽略，不应出现在提交中。
- 原Dify应用中的DB_URI和MySQL数据不受项目目录迁移影响；从GitHub下载项目的人仍需自行初始化数据库和配置凭证。

GitHub官方参考：[将本地代码上传到GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)。
