# 电子印章服务

一个本地运行的 PDF/Word 电子盖章工具。用户可以上传合同和印章图片，在指定页面添加普通印章或骑缝章，自由调整位置、大小、旋转角度和透明度，确认后导出新的 PDF 文件。

> 本项目默认仅在本机运行，合同和印章不会主动上传到第三方服务。

## 功能

- 上传 PDF 合同并逐页预览
- 上传 `.docx` / `.doc` 合同并转换为 PDF
- 上传 PNG、JPG、JPEG 印章图片
- 自动去除与图片边缘相连的白色背景
- 将印章统一按真实宽度 **4 cm** 处理
- 在当前选中的页面添加普通印章
- 拖动印章自由调整位置
- 使用滚轮或按钮缩放印章
- 以 45° 为步进旋转印章
- 调整印章透明度
- 双击复制普通印章
- 选择连续页码范围添加骑缝章
- 根据所选页数自动切分骑缝章
- 拖动任意骑缝章切片时同步调整所有页面
- 导出保留原合同内容和页面尺寸的 PDF

## 界面流程

1. 上传 PDF 合同，或上传 Word 合同并等待转换。
2. 上传一张或多张印章图片。
3. 选择要使用的印章和合同页面。
4. 普通盖章：在当前页面空白处点击，然后拖动到目标位置。
5. 骑缝章：填写起始页和结束页，开启“骑缝章模式”，在页面点击需要的垂直高度。
6. 检查所有页面，输入导出文件名并点击“导出 PDF”。

印章缩放为 `100%` 时，导出到 PDF 中的真实宽度为 4 cm。缩放操作会以此尺寸为基准。

## 技术栈

- Python 3
- Flask
- Pillow
- pypdf
- ReportLab
- PDF.js
- Microsoft Word COM（仅用于 Windows 下的 Word 转 PDF）

前端不依赖构建工具，PDF.js 文件已放在 `static/` 目录中。

## 环境要求

### PDF 功能

- Python 3.10 或更高版本
- Windows、macOS 或 Linux

### Word 功能

当前 Word 转 PDF 使用 Microsoft Word COM，因此需要：

- Windows
- 已安装桌面版 Microsoft Word
- Python 包 `comtypes`

没有安装 Microsoft Word 时，PDF 上传和盖章功能仍可正常使用，但不能直接转换 `.doc` / `.docx`。

## 安装

```bash
git clone <你的仓库地址>
cd <仓库目录>
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux：

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## 启动

```bash
python app.py
```

浏览器访问：

```text
http://127.0.0.1:8765/
```

可以通过环境变量修改端口：

Windows PowerShell：

```powershell
$env:PORT=9000
python app.py
```

macOS / Linux：

```bash
PORT=9000 python app.py
```

## 项目结构

```text
.
├── app.py                    # Flask 服务、文件处理和 PDF 导出
├── templates/
│   └── index.html            # 页面与全部前端交互
├── static/
│   ├── pdf.min.mjs           # PDF.js
│   └── pdf.worker.min.mjs
├── files/                    # 运行时合同和导出文件，不应提交
├── seals/                    # 运行时印章文件，不应提交
├── tools/                    # 测试辅助脚本
└── requirements.txt
```

`files/`、`seals/`、日志和缓存目录已加入 `.gitignore`。发布代码前仍建议手动确认其中没有真实合同、印章或其他敏感资料。

## 主要接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | 主页面 |
| `POST` | `/api/pdf` | 上传 PDF |
| `POST` | `/api/word2pdf` | 上传 Word 并转换为 PDF |
| `POST` | `/api/seal` | 上传并处理印章图片 |
| `POST` | `/api/sample` | 生成示例合同 |
| `POST` | `/api/sample-seal` | 生成示例印章 |
| `POST` | `/api/export` | 合成印章并导出 PDF |

## 4 cm 印章与骑缝章实现

普通印章在 PDF 中以 `4 / 2.54 × 72` point 作为 100% 宽度，避免因浏览器显示比例或屏幕 DPI 不同造成导出尺寸变化。

骑缝章会按照用户选择的连续页数把完整印章横向等分。每页在右边缘放置一个切片，各页切片按照页码顺序组合成完整印章。属于同一组的切片会同步移动、缩放、调整透明度或删除。

## 部署建议

`python app.py` 启动的是 Flask 开发服务器，适合个人本地使用和开发调试，不建议直接暴露到公网。

如需部署为多人服务，至少应补充：

- 使用 Waitress、Gunicorn 等生产级 WSGI 服务
- 用户认证和权限隔离
- 上传文件类型、大小和内容安全检查
- 每个用户独立的文件存储空间
- 文件过期和自动清理机制
- HTTPS
- CSRF、防滥用和访问频率限制
- 操作日志与隐私策略

印章图片和合同通常属于敏感资料。多人部署时，不应继续使用当前的共享 `files/`、`seals/` 目录作为无隔离存储。

## 法律与合规说明

本项目实现的是“在 PDF 页面上叠加印章图片”，不等同于基于数字证书的电子签名，也不自动具备身份认证、防篡改、可信时间戳或签名验签能力。

请仅在获得授权并符合当地法律、合同约定及组织内部制度的情况下使用。不得使用本项目伪造印章、冒用身份或处理未经授权的文件。项目作者不对违法使用或不当使用承担责任。

若业务需要具有更强法律效力的电子签署能力，应接入合规的 CA 数字证书、可信时间戳、签名验签及审计体系。

## 开发与测试

后端基础测试：

```bash
python -m py_compile app.py
python tools/test_rotop.py
```

建议提交代码前人工验证以下流程：

1. PDF 上传、预览和翻页。
2. Word 上传与转换。
3. PNG/JPG 印章去背景。
4. 普通章添加、拖动、缩放、旋转和透明度。
5. 两页及多页骑缝章。
6. 导出 PDF 后逐页检查印章位置和透明背景。

## 参与贡献

欢迎提交 Issue 和 Pull Request。提交前请避免附带真实合同、真实印章、个人信息或其他敏感文件。

建议在 Pull Request 中说明：

- 修改目的
- 测试方式
- 对 PDF 页面尺寸或坐标换算的影响
- 是否影响 Word、普通章或骑缝章功能

## 开源许可证

仓库当前尚未指定开源许可证。正式发布前请根据你的使用和贡献政策添加 `LICENSE` 文件，例如 MIT、Apache-2.0 或 GPL-3.0。

在许可证明确之前，默认版权仍归代码作者所有。
