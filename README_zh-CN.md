# mineru-converter

使用 MinerU 将文档转换为 Markdown。可用作 opencode 技能，也可作为独立 CLI 工具。

## 功能

- 将 PDF、DOCX、PPTX、XLSX 和图片转换为 Markdown
- 增量转换 — 跳过已转换的文件
- 提取并整理图片，兼容 Obsidian
- 支持扫描件 OCR 识别
- 自动检测 MinerU 安装状态并提供安装引导

## 支持的格式

PDF、DOCX、PPTX、XLSX、PNG、JPG、JPEG、BMP、TIFF

## 安装

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 MinerU

使用前需要安装 MinerU。转换器会自动检测 MinerU 是否可用，如果未安装会提示安装。

检查 MinerU 是否已安装：

```bash
mineru --version
```

如果 MinerU 未安装，转换器提供以下选项：
- **自动安装**：在技能目录下创建 `.mineru_venv/` 虚拟环境
- **手动安装**：提供手动安装命令

### 3. 配置

```bash
cp config.template.yaml config.yaml
# 根据需要编辑 config.yaml
```

## 如何使用

将文档放入 `inbox/` 目录，然后通过自然语言调用转换器。以下是典型场景：

### 场景 1：批量转换整个文件夹

当有多个文件需要全部转换时：

> "把 inbox 文件夹里的所有文档转成 Markdown。"
> "批量转换 inbox 目录。"
> "转换 inbox/ 下的所有文件。"

转换器会处理目录下所有支持的格式，跳过已转换的文件。

### 场景 2：转换 PDF 的指定页面

当只需要 PDF 中的部分页面时：

> "把这份 PDF 的第 3 到第 5 页转成 Markdown。"
> "转换这份文档第 18 页到第 28 页。"
> "只提取这个 PDF 的第 10 页。"

仅对 PDF 文件有效，其他格式会完整转换。

### 场景 3：对扫描件使用 OCR

当处理扫描件或图像型 PDF，需要文字识别时：

> "用 OCR 转换这份扫描版 PDF。"
> "这份文档是图片型的，请用 OCR 识别。"
> "这是扫描件，帮我识别文字。"

OCR 可以提取图片和扫描件中的文字内容。

### 场景 4：转换不同语言的文档

当文档不是中文，希望提高识别精度时：

> "转换这份英文文档。"
> "把这份日文 PDF 转成 Markdown。"
> "处理这个英文 PDF。"

转换器支持中文（默认）、英文、日文、韩文等多种语言。

### 场景 5：重新转换文件

当之前的转换结果不理想或文件已更新时：

> "重新转换这个文件。"
> "这个转错了，帮我再转一次。"
> "强制重新转换。"

### 场景 6：查看转换计划

当想看哪些文件待转换、哪些已完成时：

> "看看有哪些文件可以转换？"
> "查看转换计划。"
> "哪些文件已经转过了？"

### 场景 7：并行加速转换

当文件很多，想要加快转换速度时：

> "用 2 个线程批量转换 inbox 文件夹。"
> "并发处理文件。"

### 场景 8：批量转换并统一应用 OCR

当批量转换一批文件且都需要 OCR 时：

> "批量转换 inbox 文件夹，使用 OCR。"
> "inbox 下的所有文件都用 OCR 方法转换。"

## 输出位置

转换后的 Markdown 文件和提取的图片保存在 `raw/` 目录：

```
<项目>/
├── inbox/                     # 放置文档的位置
│   ├── paper.pdf
│   └── notes.docx
├── raw/                       # 转换输出
│   ├── paper.md
│   ├── notes.md
│   ├── attachments/
│   │   └── <hash8>/          # 按文件哈希分组的图片
│   └── manifest.json         # 转换记录
```

## 配置

编辑 `config.yaml` 修改默认值：

```yaml
mineru:
  command: "mineru"          # 或虚拟环境 bin 目录的绝对路径
  args:
    backend: "pipeline"
    model: "auto"
    language: "ch"           # 默认语言
    method: "auto"           # 默认解析方法 (auto/txt/ocr)
```

## 架构概览

- **MinerU 自动检测** — 转换前检测可用性，未安装时引导安装
- **原子写入** — manifest 更新使用单锁 read-modify-save 保证并发安全
- **独立临时目录** — 每个工作线程使用独立的 `.tmp_mineru_{uuid}` 避免竞争
- **文件锁** — `manifest.json` 使用 `fcntl.flock` 安全访问

## 测试

```bash
python3 -m pytest tests/ -v
```

72 个测试覆盖 MinerU 调用、页码解析、CLI 参数处理、安装引导、文件整理和 manifest 管理。
