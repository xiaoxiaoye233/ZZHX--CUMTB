# 打印模块

一句话：**给一个 PDF 文件路径，静默打到指定打印机，出纸。**

不经过 WPS / Edge / Acrobat，不需要 `.pdf` 的文件关联正确，不弹任何窗口。

---

## 1. 装了哪些依赖

`requirements.txt`：

```
pywin32>=306        # Windows 打印接口（打印机列表、打印队列、GDI 画布）
pypdfium2>=4.0      # PDF 渲染引擎的 Python 封装（wheel 里自带 pdfium.dll）
Pillow>=10.0        # 位图对象与"画到画布"这一步
```

```powershell
& 'D:\AI+\env\python.exe' -m pip install -r requirements.txt
```

说明：

- `pypdfium2` 就是 Chrome / Edge 内置的那个 PDF 引擎（PDFium，BSD 许可），**不必额外下载 PDFium，也不需要 Adobe**。
- 三个包都是纯 pip 安装，没有外部 exe，换台机器照装即可复现。

---

## 2. 打印是怎么走的

```
              ①读文件                ②渲染                    ③打印
   PDF  ──────────────►  每页 -> 位图（300dpi）  ──────►  GDI 画到打印机画布  ──────►  纸
        PDFium 解析          2480 x 3509 px              StretchDIBits
```

用代码说就是四句：

```python
doc = pdfium.PdfDocument(path)                                   # ①
img = doc[i].render(scale=dpi / 72).to_pil()                      # ②
ImageWin.Dib(img).draw(dc.GetSafeHdc(), (x, y, w, h))             # ③
dc.EndDoc()                                                      #   提交
```

几个要点：

- **位图不是"缩略图"**：A4 在 300dpi 下是 2480×3509 像素，按打印机可打印区域等比缩放居中，不裁切。
- **纸张尺寸由打印机驱动决定**（这台默认 A4）。PDF 页面如果比例不同，会等比缩放并居中，留白而不是变形。
- **多页自动分页**：每页一次 `StartPage/EndPage`，最后一次 `EndDoc`。

### 为什么不用系统的"打印"动作

Windows 要把文件交给某个程序去打印，靠的是 `.pdf` 的文件关联。这台机器上 `.pdf` 关联给了 WPS（注册表 `KWPS.PDF.9`），它只登记了两个动作：

| 动作 | 命令 | 结果 |
|---|---|---|
| open | `wps.exe /prometheus /pdf "%1"` | 打开界面 |
| print | `wps.exe /prometheus /pdf /n /p "%1"` | 打到**默认**打印机，且会拉起 WPS 界面 |

没有 `printto`（静默 + 指定打印机）。所以"交给系统打印"这条路在没有任何阅读器配合时走不通 —— 本模块完全绕开它。

---

## 3. 怎么用

```powershell
# 看这台机器上有哪些打印机
python print_pdf_file.py --list-printers

# 只渲染不出纸，确认能读、页数对不对
python print_pdf_file.py test.pdf --dry

# 真打（默认打印机、300dpi）
python print_pdf_file.py test.pdf

# 指定打印机、更清晰的 600dpi、只打第 1 页
python print_pdf_file.py test.pdf --printer "HP LaserJet Professional M1218nfs MFP" --dpi 600 --pages 1
```

参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `pdf` | 必填 | PDF 路径 |
| `--printer` | 环境变量 `PRINTER_NAME`，否则内置的那台 HP | 打印机名字，必须与系统里一字不差 |
| `--dpi` | 300 | 渲染精度；600 更细，每页慢约 2 秒、内存约 100MB |
| `--pages` | 全部 | 只打某几页，如 `1` 或 `1,3` |
| `--copies` | 1 | 份数 |
| `--margin` | 0 | 四周再留白多少毫米 |
| `--dry` | 关 | 只渲染，不出纸 |
| `--list-printers` | — | 列出打印机 |

退出码：`0` 成功，`1` 打印机/发送失败，`2` 参数或文件问题，`3` 依赖缺失。

---

## 4. 放进项目时改哪里

1. **打印机名字**：写进后端 `.env`（`PRINTER_NAME=...`），本脚本读同名环境变量，不写死在代码里。
2. **调用方式**：后端收到"打印"请求后，把 PDF 存到 `data/prints/<学号>-<时间>.pdf`，再 `subprocess.run([sys.executable, "print_pdf_file.py", pdf_path])`。
3. **纸张**：目前依赖打印机驱动的默认纸张（A4）。要强制，得在驱动里设，代码不干预。
4. **失败怎么知道**：脚本用退出码表示成败；更细的状态（缺纸、卡纸）目前只能看打印机面板和打印队列，脚本会给一句提示但不阻塞。

---

## 5. 已知限制

- 只有 Windows 能用（`pywin32` 是 Windows API）；Linux 那边要用 CUPS（`lp -d 打印机 文件`）。
- 打印机名字必须与系统里一致；换机器要改 `.env`。
- 渲染是"整页位图"，PDF 里的可选中文字、超链接在纸上当然没有（本来就是纸）。
- 300dpi 下很小的字（<6pt）边缘会偏软，必要时用 `--dpi 600`。

---

包里还有：

- `print_pdf_file.py` —— 主脚本
- `requirements.txt` —— 三个依赖
- `README.md` —— 本文件
- `test.pdf` —— 一份 2 页 A4 的测试文件，用来验证整条路径是否通
