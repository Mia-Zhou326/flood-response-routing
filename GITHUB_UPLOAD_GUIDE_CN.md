# 如何上传到你的 GitHub

这是一个全新、独立、使用模拟数据的 portfolio 项目。请不要把老师原来的 notebook、作业题目或地图放进这个仓库。

## 方案一：通过 Terminal（推荐）

1. 解压 ZIP，得到 `flood-response-routing` 文件夹。
2. 在 GitHub 创建一个 **Public** repository，例如 `flood-response-routing`；初始化时不要勾选新建 README、.gitignore、LICENSE，因为项目里已有。
3. 在 Mac Terminal 中 `cd` 到解压后的项目目录，依次运行：

```bash
git init
git add .
git commit -m "Initial commit: risk-aware flood response routing"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/flood-response-routing.git
git push -u origin main
```

将 `YOUR_USERNAME` 换成你自己的 GitHub 用户名。GitHub 推送时需要你自己的登录凭证。

## 方案二：网页上传

创建空仓库 → 选择 **uploading an existing file** → 将**解压后的文件及文件夹**拖入上传区 → Commit changes。不要把整个 ZIP 当作唯一仓库文件上传；那样别人无法直接浏览 notebook 和 README。

## 怎么运行

在项目根目录：

```bash
python -m pip install -r requirements.txt
python run_analysis.py
python -m pytest -q
jupyter lab
```

然后打开 `Flood_Response_Routing.ipynb` → **Run All**。如果安装了 Gurobi 但尚未配置许可证，在 Notebook 中将 `BACKEND = 'auto'` 改为 `BACKEND = 'scipy'`。

## 建议的 GitHub 设置

- **Repository name**：`flood-response-routing`
- **Description**：`Risk-aware emergency routing with mixed-integer optimization, MTZ constraints, road closures, and sensitivity analysis.`
- **Topics**：`python`, `optimization`, `gurobi`, `mixed-integer-programming`, `networkx`, `operations-research`, `data-science`

公开之前检查 README 中作者信息及 AI 辅助声明是否符合你想展示的真实贡献；如果未来把它描述在简历里，务必确保你能解释模型里的每组约束和结果。
