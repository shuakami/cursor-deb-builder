# Cursor DEB 构建器

本项目使用 Github Actions 自动为最新 Linux 版本的 Cursor 编辑器构建 Debian (`.deb`) 软件包。

## 工作原理

1.  一个计划好的 Github Action 每天运行（或可手动触发）。
2.  它使用 Python 脚本（带有 Playwright 的 `main.py`）抓取 Cursor 官方下载页面，以获取最新的 Linux AppImage 版本和 URL。
3.  它检查该版本的 Github Release 是否已存在。
4.  如果版本是新的：
    *   下载 AppImage 文件。
    *   使用 `make-deb.sh` 脚本将 AppImage 打包成 `.deb` 文件。
    *   创建一个以版本号标记的新 Github Release，并将 `.deb` 文件作为附件上传。
    *   将 `.deb` 文件推送到 Cloudsmith APT 仓库。

## 使用方法

请检查 [Releases 页面](https://github.com/shuakami/cursor-deb-builder/releases) 获取最新的 `.deb` 软件包。

## 安装

### 通过 APT (适用于 Debian/Ubuntu/Zorin 及其衍生版)

1.  **设置仓库:**
    运行以下命令将 Cloudsmith 仓库及其 GPG 密钥添加到您的系统。您可能需要先安装 `curl` (`sudo apt install curl`)。
    ```bash
    curl -1sLf \
      'https://dl.cloudsmith.io/QhHWEwzA2fBaF9VC/shuakami/cursor-linux/setup.deb.sh' \
      | sudo -E bash
    ```

2.  **安装 Cursor:**
    设置好仓库后，更新您的软件包列表并安装 Cursor：
    ```bash
    sudo apt-get update
    sudo apt-get install cursor
    ```
    这将安装可用的最新版本。

    *(可选) 安装特定版本 (例如, 0.48):*
    ```bash
    # sudo apt-get install cursor=0.48
    ``` 