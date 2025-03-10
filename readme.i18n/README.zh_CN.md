
# Cat-Printer

🐱🖨 猫咪打印机：此应用*跨平台地*对一些蓝牙“喵喵机”提供支持！

[![cat-printer-poster](https://repository-images.githubusercontent.com/403563361/ad018f6e-3a6e-4028-84b2-205f7d35c22b)](https://repository-images.githubusercontent.com/403563361/ad018f6e-3a6e-4028-84b2-205f7d35c22b)

## 型号

目前有：

|    |    |
|----|----|
| 支持 | `GB0X, GT01, YT01`  |

\* `X` 表示任意数字

## 特性

*当前仍在继续开发。以后会有更多！*

- 简易！
  - 在网页界面进行操作，
  - 或者获取安卓应用！

- 友好！
  - 语言支持！您可参与翻译！
  - 良好的用户界面，可适应桌面/移动端/明暗主题！
  - 无障碍功能，考虑到每一个人！

- 功能丰富！
  - 网页界面，所有人都可以用！
    - 控制打印机配置
    - 打印照片，或单纯地进行测试
  - 命令行，技术爱好者必备！
    - 使用一些参数控制打印机
    - 简易、简化的图片或文字打印
    - 让程序的每一部分发挥作用
  - 其他一些好东西！
    - 服务器也具有 CUPS/IPP 能力

- 跨平台！
  - 较新的 Windows 10 及以上
  - GNU/Linux
  - MacOS
  - 还有安卓！

- 是[自由软件](https://www.gnu.org/philosophy/free-sw.html)！
  - 不像“原版”专有应用，此作品为在乎*开放思想与计算自由*的人而生！

- 有意思！
  - 做什么都可以！

## 现在开始

### 安卓

获取并安装最新版安卓 apk 包，完成！

应用可能请求“后台位置”权限，您可以拒绝它。  
（前台）位置权限是较新版安卓系统扫描蓝牙设备所需要的。

### Windows

获取名称中有 "windows" 的版本，  
解压并运行 `start.bat`

### GNU/Linux

您可以获取“纯净(pure)”版，解压、在其中打开终端并输入：  
```bash
python3 server.py
```

在 Arch Linux 等发行版您可能需要首先安装 `bluez`  
```bash
sudo pacman -S bluez bluez-utils
```

*以后将有软件包！*

### MacOS

MacOS 用户请首先安装 [Python 3](https://www.python.org/)，  
然后在终端使用 `pip` 安装 `pyobjc` 和 `bleak`：
```bash
pip3 install pyobjc bleak
```

然后获取并使用“单一(bare)”版：  
```bash
python3 server.py
```

当前在 MacOS 浏览器不会自动打开。您可以手动访问 `http://127.0.0.1:8095`，或点击[这里](http://127.0.0.1:8095)


### 值得注意

对于所有支持的平台，  
当已安装 [Python 3](https://www.python.org/) 时，您可以直接获取“纯净(pure)”版，  
或在已使用 `pip` 安装 `bleak` 时使用“单一(bare)”版。

如果您喜欢命令行，安装 [ImageMagick](https://imagemagick.org/) 和 [Ghostscript](https://ghostscript.com/) 会很有帮助。

查看所有[发布版本](https://github.com/NaitLee/Cat-Printer/releases)！

## 有问题？

有想法？用 Issue 或去 Discussion 讨论！

如果能行，Pull Request 也可以！

## 许可证

Copyright © 2021-2022 NaitLee Soft. 保留一些权利。

敬请查看文件 `COPYING`，`LICENSE`，以及在 `www/jslicense.html` 中有关 JavaScript 许可的详细内容。

具体地，`printer.py`，`server.py` 和 `main.js` 以 GNU GPL 3 发布。  
除去来自其他人的贡献（版权可能归贡献者所有）及可能的第三方依赖，所有其余部分在公有领域（CC0）。

--------

## 开发

您可能对翻译工作感兴趣。可于目录 `www/lang` 和 `readme.i18n` 中查看翻译文件！

注：
1. 通常英语与简体中文同时更新。请考虑其他，如繁体中文（需注意在繁体中与简体的用字、技术术语差别）。  
2. 如果（真的）有能力，您也可以纠正/改善某些翻译！

还想写代码？看看 [development.md](development.md)！（英文）

### 鸣谢

- 当然不能没有 Python 和 Web 技术！
- [Bleak](https://bleak.readthedocs.io/en/latest/) 跨平台蓝牙低功耗库，牛！
- [roddeh-i18n](https://github.com/roddeh/i18njs)，当前内置的国际化脚本受此启发
- [python-for-android](https://python-for-android.readthedocs.io/en/latest/)，虽然有些麻烦的地方
- [AdvancedWebView](https://github.com/delight-im/Android-AdvancedWebView) 从 Java 拯救了我的生命
- Stack Overflow 和整个互联网，你们让我从零开始了解了安卓“活动” `Activity`
- ……每个人都是好样的！
